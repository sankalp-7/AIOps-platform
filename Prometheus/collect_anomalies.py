from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import requests


PROMETHEUS_URL = "http://localhost:9090"
POLL_INTERVAL_SECONDS = 30

CURRENT_ANOMALIES_FILE = "current_anomalies.json"
STATE_FILE = "detector_state.json"
EVENTS_FILE = "anomaly_events.jsonl"

# Optional edge-specific baselines. Add entries after observing normal traffic.
# Example: "qotd-web->qotd-quote": 450
EDGE_LATENCY_BASELINE_MS: dict[str, float] = {}

# Destination-based fallback baselines from the existing detector.
LATENCY_BASELINE_MS = {
    "qotd-quote": 225,
    "qotd-web": 450,
    "qotd-pdf": 250,
    "qotd-rating": 225,
    "qotd-author": 250,
    "qotd-image": 250,
    "qotd-engraving": 250,
    "qotd-qrcode": 100,
}

DEFAULT_LATENCY_BASELINE_MS = 300
HIGH_LATENCY_MULTIPLIER = 2
CRITICAL_LATENCY_MULTIPLIER = 4
HIGH_ERROR_RATE = 0.02
CRITICAL_ERROR_RATE = 0.10


# Important change: preserve source_workload and destination_workload.
P95_LATENCY_QUERY = """
histogram_quantile(
  0.95,
  sum by (source_workload, destination_workload, le) (
    rate(
      istio_request_duration_milliseconds_bucket{
        reporter="destination",
        source_workload=~"qotd-.+",
        destination_workload=~"qotd-.+"
      }[1m]
    )
  )
)
"""

# Keep this as a service-level auxiliary signal for now.
ERROR_RATE_QUERY = """
sum(
  rate(
    istio_requests_total{
      reporter="destination",
      destination_workload=~"qotd-.+",
      response_code=~"5.."
    }[1m]
  )
) by (destination_workload)
/
sum(
  rate(
    istio_requests_total{
      reporter="destination",
      destination_workload=~"qotd-.+"
    }[1m]
  )
) by (destination_workload)
"""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(filename: str, default_value):
    if not os.path.exists(filename):
        return default_value
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(filename: str, data) -> None:
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def append_event(event: dict) -> None:
    with open(EVENTS_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")


def query_prometheus(promql_query: str) -> list[dict]:
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": promql_query},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")

    return payload["data"]["result"]


def latency_baseline(source: str, destination: str) -> float:
    edge_id = f"{source}->{destination}"
    return EDGE_LATENCY_BASELINE_MS.get(
        edge_id,
        LATENCY_BASELINE_MS.get(
            destination,
            DEFAULT_LATENCY_BASELINE_MS,
        ),
    )


def get_latency_severity(
    source: str,
    destination: str,
    latency_ms: float,
) -> str | None:
    baseline = latency_baseline(source, destination)

    if latency_ms >= baseline * CRITICAL_LATENCY_MULTIPLIER:
        return "critical"
    if latency_ms >= baseline * HIGH_LATENCY_MULTIPLIER:
        return "high"
    return None


def get_error_rate_severity(error_rate: float) -> str | None:
    if error_rate >= CRITICAL_ERROR_RATE:
        return "critical"
    if error_rate >= HIGH_ERROR_RATE:
        return "high"
    return None


def detect_latency_anomalies() -> list[dict]:
    anomalies: list[dict] = []

    for result in query_prometheus(P95_LATENCY_QUERY):
        metric = result.get("metric", {})
        source = metric.get("source_workload")
        destination = metric.get("destination_workload")
        latency_ms = float(result["value"][1])

        if not source or not destination or latency_ms != latency_ms:
            continue

        severity = get_latency_severity(source, destination, latency_ms)
        if not severity:
            continue

        anomalies.append(
            {
                "source": source,
                "destination": destination,
                "edge_id": f"{source}->{destination}",
                # Retain `service` for compatibility with existing consumers.
                "service": destination,
                "metric": "p95_latency_ms",
                "value": round(latency_ms, 2),
                "baseline": latency_baseline(source, destination),
                "severity": severity,
            }
        )

    return anomalies


def detect_error_rate_anomalies() -> list[dict]:
    anomalies: list[dict] = []

    for result in query_prometheus(ERROR_RATE_QUERY):
        service = result.get("metric", {}).get("destination_workload")
        error_rate = float(result["value"][1])

        if not service or error_rate != error_rate:
            continue

        severity = get_error_rate_severity(error_rate)
        if severity:
            anomalies.append(
                {
                    "service": service,
                    "metric": "5xx_error_rate",
                    "value": round(error_rate, 4),
                    "severity": severity,
                }
            )

    return anomalies


def anomaly_state_key(anomaly: dict) -> str:
    entity = anomaly.get("edge_id") or anomaly["service"]
    return f"{entity}|{anomaly['metric']}"


def enrich_and_save_anomalies(detected_anomalies: list[dict]) -> list[dict]:
    state = load_json(STATE_FILE, {})
    timestamp = now_utc()
    current_anomalies: list[dict] = []
    active_keys: set[str] = set()

    for anomaly in detected_anomalies:
        key = anomaly_state_key(anomaly)
        active_keys.add(key)
        previous = state.get(key)

        anomaly["first_seen"] = previous["first_seen"] if previous else timestamp
        anomaly["last_seen"] = timestamp
        anomaly["status"] = "firing"

        if previous is None:
            append_event(
                {
                    "event_type": "anomaly_started",
                    "timestamp": timestamp,
                    **anomaly,
                }
            )
            print(
                f"NEW: {anomaly.get('edge_id', anomaly['service'])} "
                f"{anomaly['metric']}={anomaly['value']} "
                f"severity={anomaly['severity']}"
            )
        elif previous["severity"] != anomaly["severity"]:
            append_event(
                {
                    "event_type": "severity_changed",
                    "timestamp": timestamp,
                    "previous_severity": previous["severity"],
                    **anomaly,
                }
            )
            print(
                f"UPDATED: {anomaly.get('edge_id', anomaly['service'])} "
                f"{anomaly['metric']} "
                f"{previous['severity']} -> {anomaly['severity']}"
            )

        state[key] = anomaly
        current_anomalies.append(anomaly)

    for key in set(state) - active_keys:
        resolved_anomaly = state[key]
        append_event(
            {
                "event_type": "anomaly_resolved",
                "timestamp": timestamp,
                **resolved_anomaly,
            }
        )
        print(
            f"RESOLVED: "
            f"{resolved_anomaly.get('edge_id', resolved_anomaly['service'])} "
            f"{resolved_anomaly['metric']}"
        )
        del state[key]

    save_json(STATE_FILE, state)
    save_json(CURRENT_ANOMALIES_FILE, current_anomalies)
    return current_anomalies


def run_detector() -> None:
    print(
        "Starting edge-aware Prometheus anomaly detector. "
        f"Polling every {POLL_INTERVAL_SECONDS} seconds."
    )

    while True:
        try:
            anomalies = (
                detect_latency_anomalies()
                + detect_error_rate_anomalies()
            )
            current = enrich_and_save_anomalies(anomalies)
            print(f"{now_utc()} | active anomalies: {len(current)}")
        except requests.RequestException as error:
            print(f"Could not query Prometheus: {error}")
        except Exception as error:
            print(f"Detector error: {error}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_detector()
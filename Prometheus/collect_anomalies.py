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

# only detecting latency and error rate, will add more metrics eventually
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

HIGH_ERROR_RATE = 0.02       # 2%
CRITICAL_ERROR_RATE = 0.10   # 10%

# prom queries
P95_LATENCY_QUERY = """
histogram_quantile(
  0.95,
  sum(
    rate(
      istio_request_duration_milliseconds_bucket{
        destination_workload=~"qotd-.+"
      }[1m]
    )
  ) by (destination_workload, le)
)
"""

ERROR_RATE_QUERY = """
sum(
  rate(
    istio_requests_total{
      destination_workload=~"qotd-.+",
      response_code=~"5.."
    }[1m]
  )
) by (destination_workload)
/
sum(
  rate(
    istio_requests_total{
      destination_workload=~"qotd-.+"
    }[1m]
  )
) by (destination_workload)
"""


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def load_json(filename, default_value):
    if not os.path.exists(filename):
        return default_value

    with open(filename, "r") as file:
        return json.load(file)


def save_json(filename, data):
    with open(filename, "w") as file:
        json.dump(data, file, indent=2)


def append_event(event):
    with open(EVENTS_FILE, "a") as file:
        file.write(json.dumps(event) + "\n")


def query_prometheus(promql_query):
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


def get_latency_severity(service, latency_ms):
    baseline = LATENCY_BASELINE_MS.get(
        service,
        DEFAULT_LATENCY_BASELINE_MS,
    )

    if latency_ms >= baseline * CRITICAL_LATENCY_MULTIPLIER:
        return "critical"

    if latency_ms >= baseline * HIGH_LATENCY_MULTIPLIER:
        return "high"

    return None


def get_error_rate_severity(error_rate):
    if error_rate >= CRITICAL_ERROR_RATE:
        return "critical"

    if error_rate >= HIGH_ERROR_RATE:
        return "high"

    return None


def detect_latency_anomalies():
    anomalies = []
    results = query_prometheus(P95_LATENCY_QUERY)

    for result in results:
        service = result["metric"].get("destination_workload")
        latency_ms = float(result["value"][1])

        if not service or latency_ms != latency_ms:
            continue

        severity = get_latency_severity(service, latency_ms)

        if severity:
            anomalies.append(
                {
                    "service": service,
                    "metric": "p95_latency_ms",
                    "value": round(latency_ms, 2),
                    "severity": severity,
                }
            )

    return anomalies


def detect_error_rate_anomalies():
    anomalies = []
    results = query_prometheus(ERROR_RATE_QUERY)

    for result in results:
        service = result["metric"].get("destination_workload")
        error_rate = float(result["value"][1])

        if not service:
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


def enrich_and_save_anomalies(detected_anomalies):
    state = load_json(STATE_FILE, {})
    timestamp = now_utc()

    current_anomalies = []
    active_keys = set()

    for anomaly in detected_anomalies:
        key = f"{anomaly['service']}|{anomaly['metric']}"
        active_keys.add(key)

        previous = state.get(key)

        anomaly["first_seen"] = (
            previous["first_seen"]
            if previous
            else timestamp
        )
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
                f"NEW: {anomaly['service']} "
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
                f"UPDATED: {anomaly['service']} "
                f"{anomaly['metric']} "
                f"{previous['severity']} → {anomaly['severity']}"
            )

        state[key] = anomaly
        current_anomalies.append(anomaly)

    resolved_keys = set(state) - active_keys

    for key in resolved_keys:
        resolved_anomaly = state[key]

        append_event(
            {
                "event_type": "anomaly_resolved",
                "timestamp": timestamp,
                **resolved_anomaly,
            }
        )

        print(
            f"RESOLVED: {resolved_anomaly['service']} "
            f"{resolved_anomaly['metric']}"
        )

        del state[key]

    save_json(STATE_FILE, state)
    save_json(CURRENT_ANOMALIES_FILE, current_anomalies)

    return current_anomalies


def run_detector():
    print(
        f"Starting Prometheus anomaly detector. "
        f"Polling every {POLL_INTERVAL_SECONDS} seconds."
    )

    while True:
        try:
            latency_anomalies = detect_latency_anomalies()
            error_anomalies = detect_error_rate_anomalies()

            anomalies = latency_anomalies + error_anomalies
            current = enrich_and_save_anomalies(anomalies)

            print(
                f"{now_utc()} | "
                f"active anomalies: {len(current)}"
            )

        except requests.RequestException as error:
            print(f"Could not query Prometheus: {error}")

        except Exception as error:
            print(f"Detector error: {error}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_detector()
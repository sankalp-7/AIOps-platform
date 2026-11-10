from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from datetime import datetime, timezone

import requests


PROMETHEUS_URL = "http://localhost:9090"

POLL_INTERVAL_SECONDS = 60
BASELINE_LEARNING_DURATION_SECONDS = 600
BASELINE_SAMPLE_INTERVAL_SECONDS = 30
MIN_BASELINE_SAMPLES = 5

CURRENT_ANOMALIES_FILE = "current_anomalies.json"
STATE_FILE = "detector_state.json"
EVENTS_FILE = "anomaly_events.jsonl"
BASELINE_FILE = "edge_latency_baselines.json"

HIGH_LATENCY_MULTIPLIER = 5.0
CRITICAL_LATENCY_MULTIPLIER = 10.0
MIN_LATENCY_INCREASE_MS = 20.0

EXCLUDED_WORKLOADS = {
    "unknown",
    "otel-collector-agent",
    "prometheus",
    "grafana",
    "jaeger",
    "opamp-server",
    "telemetry-docs",
    "mcp",
}

# These edges show user-facing symptoms, but a downstream fault also makes
# them slow. Exclude them from internal-service RCA experiments.
EXCLUDED_INGRESS_SOURCES = {"frontend-proxy", "load-generator"}

# Use one Istio reporter. Combining source and destination reporters mixes
# two observations of each request into the same latency distribution.
P95_LATENCY_QUERY = """
histogram_quantile(
  0.95,
  sum by (source_workload, destination_workload, le) (
    rate(
      istio_request_duration_milliseconds_bucket{
        reporter="source",
        source_workload!="unknown",
        destination_workload!="unknown",
        source_workload!="otel-collector-agent",
        destination_workload!="otel-collector-agent",
        source_workload!="flagd",
        destination_workload!="flagd"
      }[5m]
    )
  )
)
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


def valid_business_edge(
    source: str | None,
    destination: str | None,
) -> bool:
    if not source or not destination or source == destination:
        return False

    if source in EXCLUDED_WORKLOADS:
        return False

    if source in EXCLUDED_INGRESS_SOURCES:
        return False

    if destination in EXCLUDED_WORKLOADS:
        return False

    return True


def fetch_current_edge_latencies() -> dict[str, dict]:
    edges: dict[str, dict] = {}

    for result in query_prometheus(P95_LATENCY_QUERY):
        metric = result.get("metric", {})
        source = metric.get("source_workload")
        destination = metric.get("destination_workload")

        if not valid_business_edge(source, destination):
            continue

        try:
            latency_ms = float(result["value"][1])
        except (KeyError, IndexError, TypeError, ValueError):
            continue

        if not math.isfinite(latency_ms):
            continue

        edge_id = f"{source}->{destination}"
        edges[edge_id] = {
            "source": source,
            "destination": destination,
            "p95_ms": latency_ms,
        }

    return edges


def learn_baselines() -> None:
    print(
        "Learning normal p95 latency baselines.\n"
        f"Duration: {BASELINE_LEARNING_DURATION_SECONDS}s\n"
        f"Sample interval: {BASELINE_SAMPLE_INTERVAL_SECONDS}s\n"
    )

    samples: dict[str, list[float]] = {}
    edge_metadata: dict[str, dict] = {}
    end_time = time.time() + BASELINE_LEARNING_DURATION_SECONDS
    sample_number = 0

    while time.time() < end_time:
        sample_number += 1

        try:
            current_edges = fetch_current_edge_latencies()
            print(
                f"{now_utc()} | baseline sample {sample_number} | "
                f"edges={len(current_edges)}"
            )

            for edge_id, edge_data in current_edges.items():
                samples.setdefault(edge_id, []).append(edge_data["p95_ms"])
                edge_metadata[edge_id] = {
                    "source": edge_data["source"],
                    "destination": edge_data["destination"],
                }

        except requests.RequestException as error:
            print(f"Could not query Prometheus: {error}")
        except Exception as error:
            print(f"Baseline collection error: {error}")

        time.sleep(BASELINE_SAMPLE_INTERVAL_SECONDS)

    baselines: dict[str, dict] = {}
    print("\nCalculating baselines...\n")

    for edge_id, values in sorted(samples.items()):
        if len(values) < MIN_BASELINE_SAMPLES:
            print(f"Skipping {edge_id}: only {len(values)} samples")
            continue

        baseline_ms = statistics.median(values)
        metadata = edge_metadata[edge_id]

        baselines[edge_id] = {
            "source": metadata["source"],
            "destination": metadata["destination"],
            "p95_ms": round(baseline_ms, 3),
            "samples": len(values),
            "min_ms": round(min(values), 3),
            "max_ms": round(max(values), 3),
            "mean_ms": round(statistics.mean(values), 3),
        }

        print(
            f"{edge_id:<45} baseline={baseline_ms:.2f} ms "
            f"samples={len(values)}"
        )

    save_json(BASELINE_FILE, baselines)

    # Stop the running detector before relearning. Clear its previous
    # first_seen values and active anomalies for the next experiment.
    save_json(STATE_FILE, {})
    save_json(CURRENT_ANOMALIES_FILE, [])

    print(
        f"\nSaved {len(baselines)} edge baselines "
        f"to {BASELINE_FILE}"
    )


def load_edge_baselines() -> dict[str, dict]:
    baselines = load_json(BASELINE_FILE, {})

    if not baselines:
        raise RuntimeError(
            f"{BASELINE_FILE} is missing or empty. Run "
            "python collect_anomalies_oteldemo.py --learn-baseline "
            "before starting detection."
        )

    return baselines


def latency_baseline(
    source: str,
    destination: str,
    baselines: dict[str, dict],
) -> float | None:
    edge_baseline = baselines.get(f"{source}->{destination}")

    if edge_baseline:
        try:
            value = float(edge_baseline["p95_ms"])
            if math.isfinite(value) and value > 0:
                return value
        except (KeyError, TypeError, ValueError):
            pass

    # Do not invent a 300 ms baseline for an edge that was never learned.
    return None


def get_latency_severity(
    source: str,
    destination: str,
    latency_ms: float,
    baselines: dict[str, dict],
) -> tuple[str | None, float | None]:
    baseline = latency_baseline(source, destination, baselines)

    if baseline is None:
        return None, None

    if latency_ms - baseline <= MIN_LATENCY_INCREASE_MS:
        return None, baseline

    if latency_ms >= baseline * CRITICAL_LATENCY_MULTIPLIER:
        return "critical", baseline

    if latency_ms >= baseline * HIGH_LATENCY_MULTIPLIER:
        return "high", baseline

    return None, baseline


def detect_latency_anomalies(
    baselines: dict[str, dict],
) -> list[dict]:
    anomalies: list[dict] = []
    current_edges = fetch_current_edge_latencies()

    for edge_id, edge_data in current_edges.items():
        source = edge_data["source"]
        destination = edge_data["destination"]
        latency_ms = edge_data["p95_ms"]

        severity, baseline = get_latency_severity(
            source,
            destination,
            latency_ms,
            baselines,
        )

        if not severity:
            continue

        ratio = latency_ms / baseline

        anomalies.append(
            {
                "source": source,
                "destination": destination,
                "edge_id": edge_id,
                "service": destination,
                "metric": "p95_latency_ms",
                "value": round(latency_ms, 3),
                "baseline": round(baseline, 3),
                "ratio_to_baseline": round(ratio, 3),
                "severity": severity,
            }
        )

    return anomalies


def anomaly_state_key(anomaly: dict) -> str:
    return f"{anomaly['edge_id']}|{anomaly['metric']}"


def enrich_and_save_anomalies(
    detected_anomalies: list[dict],
) -> list[dict]:
    state = load_json(STATE_FILE, {})
    timestamp = now_utc()

    current_anomalies: list[dict] = []
    active_keys: set[str] = set()

    for anomaly in detected_anomalies:
        key = anomaly_state_key(anomaly)
        active_keys.add(key)
        previous = state.get(key)

        anomaly["first_seen"] = (
            previous["first_seen"] if previous else timestamp
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
                f"NEW: {anomaly['edge_id']} "
                f"{anomaly['metric']}={anomaly['value']}ms "
                f"baseline={anomaly['baseline']}ms "
                f"ratio={anomaly['ratio_to_baseline']}x "
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
                f"UPDATED: {anomaly['edge_id']} "
                f"{previous['severity']} -> {anomaly['severity']}"
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
            f"RESOLVED: {resolved_anomaly['edge_id']} "
            f"{resolved_anomaly['metric']}"
        )
        del state[key]

    save_json(STATE_FILE, state)
    save_json(CURRENT_ANOMALIES_FILE, current_anomalies)

    return current_anomalies


def run_detector() -> None:
    baselines = load_edge_baselines()

    print("Starting OTEL Demo edge-aware latency anomaly detector.")
    print(f"Prometheus: {PROMETHEUS_URL}")
    print(f"Polling every {POLL_INTERVAL_SECONDS}s")
    print(f"High threshold: {HIGH_LATENCY_MULTIPLIER}x baseline")
    print(f"Critical threshold: {CRITICAL_LATENCY_MULTIPLIER}x baseline\n")

    while True:
        try:
            anomalies = detect_latency_anomalies(baselines)
            current = enrich_and_save_anomalies(anomalies)
            print(f"{now_utc()} | active anomalies: {len(current)}")

        except requests.RequestException as error:
            print(f"Could not query Prometheus: {error}")
        except Exception as error:
            print(f"Detector error: {error}")

        time.sleep(POLL_INTERVAL_SECONDS)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Edge-aware p95 latency anomaly detector for the OpenTelemetry Demo."
    )
    parser.add_argument(
        "--learn-baseline",
        action="store_true",
        help="Observe normal traffic and generate edge_latency_baselines.json.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.learn_baseline:
        learn_baselines()
    else:
        run_detector()


if __name__ == "__main__":
    main()
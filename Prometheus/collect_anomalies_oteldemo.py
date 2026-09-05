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

POLL_INTERVAL_SECONDS = 30

# Baseline learning
BASELINE_LEARNING_DURATION_SECONDS = 600   # 10 minutes
BASELINE_SAMPLE_INTERVAL_SECONDS = 30
MIN_BASELINE_SAMPLES = 5

CURRENT_ANOMALIES_FILE = "current_anomalies.json"
STATE_FILE = "detector_state.json"
EVENTS_FILE = "anomaly_events.jsonl"
BASELINE_FILE = "edge_latency_baselines.json"

# Detection thresholds
HIGH_LATENCY_MULTIPLIER = 2.0
CRITICAL_LATENCY_MULTIPLIER = 4.0

# Safety fallback only.
# Ideally every active business edge should have a learned baseline.
DEFAULT_LATENCY_BASELINE_MS = 300.0

# Do not use these workloads for RCA latency anomalies.
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

P95_LATENCY_QUERY = """
histogram_quantile(
  0.95,
  sum by (source_workload, destination_workload, le) (
    rate(
      istio_request_duration_milliseconds_bucket{
        source_workload!="unknown",
        destination_workload!="unknown",
        source_workload!="otel-collector-agent",
        destination_workload!="otel-collector-agent",
        source_workload!="flagd",
        destination_workload!="flagd"
      }[10m]
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
        raise RuntimeError(
            f"Prometheus query failed: {payload}"
        )

    return payload["data"]["result"]


def valid_business_edge(
    source: str | None,
    destination: str | None,
) -> bool:
    if not source or not destination:
        return False

    if source == destination:
        return False

    if source in EXCLUDED_WORKLOADS:
        return False

    if destination in EXCLUDED_WORKLOADS:
        return False

    return True


# returns latencies of all useful edges
def fetch_current_edge_latencies() -> dict[str, dict]:
    edges: dict[str, dict] = {}

    for result in query_prometheus(P95_LATENCY_QUERY):
        metric = result.get("metric", {}) # example output - {"metric":{"destination_workload":"checkout","source_workload":"frontend"},"value":[1788352283.730,"48.47005468636529"]}

        source = metric.get("source_workload")
        destination = metric.get("destination_workload")

        if not valid_business_edge(source, destination):
            continue

        try:
            latency_ms = float(result["value"][1]) # value[0] is the timestamp of the retrieved metric
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

    end_time = (
        time.time()
        + BASELINE_LEARNING_DURATION_SECONDS
    )

    sample_number = 0

    while time.time() < end_time:
        sample_number += 1

        try:
            current_edges = fetch_current_edge_latencies()

            print(
                f"{now_utc()} | "
                f"baseline sample {sample_number} | "
                f"edges={len(current_edges)}"
            )

            for edge_id, edge_data in current_edges.items():
                latency_ms = edge_data["p95_ms"]

                samples.setdefault(
                    edge_id,
                    [],
                ).append(latency_ms)

                edge_metadata[edge_id] = {
                    "source": edge_data["source"],
                    "destination": edge_data["destination"],
                }

        except requests.RequestException as error:
            print(
                f"Could not query Prometheus: {error}"
            )

        except Exception as error:
            print(
                f"Baseline collection error: {error}"
            )

        time.sleep(
            BASELINE_SAMPLE_INTERVAL_SECONDS
        )

    baselines: dict[str, dict] = {}

    print("\nCalculating baselines...\n")

    for edge_id, values in sorted(samples.items()):
        if len(values) < MIN_BASELINE_SAMPLES:
            print(
                f"Skipping {edge_id}: "
                f"only {len(values)} samples"
            )
            continue

        # Median is less sensitive to occasional spikes
        # during baseline collection.
        baseline_ms = statistics.median(values)

        metadata = edge_metadata[edge_id]

        baselines[edge_id] = {
            "source": metadata["source"],
            "destination": metadata["destination"],
            "p95_ms": round(
                baseline_ms,
                3,
            ),
            "samples": len(values),
            "min_ms": round(
                min(values),
                3,
            ),
            "max_ms": round(
                max(values),
                3,
            ),
            "mean_ms": round(
                statistics.mean(values),
                3,
            ),
        }

        print(
            f"{edge_id:<45} "
            f"baseline={baseline_ms:.2f} ms "
            f"samples={len(values)}"
        )

    save_json(
        BASELINE_FILE,
        baselines,
    )

    print(
        f"\nSaved {len(baselines)} edge baselines "
        f"to {BASELINE_FILE}"
    )


def load_edge_baselines() -> dict[str, dict]:
    baselines = load_json(
        BASELINE_FILE,
        {},
    )

    if not baselines:
        print(
            f"WARNING: {BASELINE_FILE} is empty or missing.\n"
            "Run:\n"
            "python collect_anomalies.py --learn-baseline\n"
            "before starting detection."
        )

    return baselines


def latency_baseline(
    source: str,
    destination: str,
    baselines: dict[str, dict],
) -> float:
    edge_id = f"{source}->{destination}"

    edge_baseline = baselines.get(
        edge_id,
    )

    if edge_baseline:
        try:
            value = float(
                edge_baseline["p95_ms"]
            )

            if math.isfinite(value) and value > 0:
                return value

        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            pass

    return DEFAULT_LATENCY_BASELINE_MS


def get_latency_severity(
    source: str,
    destination: str,
    latency_ms: float,
    baselines: dict[str, dict],
) -> tuple[str | None, float]:
    baseline = latency_baseline(
        source,
        destination,
        baselines,
    )

    if baseline <= 0:
        return None, baseline

    if (
        latency_ms
        >= baseline
        * CRITICAL_LATENCY_MULTIPLIER
    ):
        return "critical", baseline

    if (
        latency_ms
        >= baseline
        * HIGH_LATENCY_MULTIPLIER
    ):
        return "high", baseline

    return None, baseline


def detect_latency_anomalies(
    baselines: dict[str, dict],
) -> list[dict]:
    anomalies: list[dict] = []

    current_edges = (
        fetch_current_edge_latencies()
    )

    for edge_id, edge_data in current_edges.items():
        source = edge_data["source"]
        destination = edge_data["destination"]
        latency_ms = edge_data["p95_ms"]

        severity, baseline = (
            get_latency_severity(
                source,
                destination,
                latency_ms,
                baselines,
            )
        )

        if not severity:
            continue

        ratio = (
            latency_ms / baseline
            if baseline > 0
            else None
        )

        anomalies.append(
            {
                "source": source,
                "destination": destination,
                "edge_id": edge_id,

                # Retained for compatibility with
                # existing RCA consumers.
                "service": destination,

                "metric": "p95_latency_ms",

                "value": round(
                    latency_ms,
                    3,
                ),

                "baseline": round(
                    baseline,
                    3,
                ),

                "ratio_to_baseline": (
                    round(ratio, 3)
                    if ratio is not None
                    else None
                ),

                "severity": severity,
            }
        )

    return anomalies


def anomaly_state_key(
    anomaly: dict,
) -> str:
    return (
        f"{anomaly['edge_id']}|"
        f"{anomaly['metric']}"
    )


def enrich_and_save_anomalies(
    detected_anomalies: list[dict],
) -> list[dict]:
    state = load_json(
        STATE_FILE,
        {},
    )

    timestamp = now_utc()

    current_anomalies: list[dict] = []
    active_keys: set[str] = set()

    for anomaly in detected_anomalies:
        key = anomaly_state_key(
            anomaly
        )

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
                f"NEW: "
                f"{anomaly['edge_id']} "
                f"{anomaly['metric']}="
                f"{anomaly['value']}ms "
                f"baseline="
                f"{anomaly['baseline']}ms "
                f"ratio="
                f"{anomaly['ratio_to_baseline']}x "
                f"severity="
                f"{anomaly['severity']}"
            )

        elif (
            previous["severity"]
            != anomaly["severity"]
        ):
            append_event(
                {
                    "event_type":
                        "severity_changed",
                    "timestamp": timestamp,
                    "previous_severity":
                        previous["severity"],
                    **anomaly,
                }
            )

            print(
                f"UPDATED: "
                f"{anomaly['edge_id']} "
                f"{previous['severity']} -> "
                f"{anomaly['severity']}"
            )

        state[key] = anomaly
        current_anomalies.append(
            anomaly
        )

    resolved_keys = (
        set(state)
        - active_keys
    )

    for key in resolved_keys:
        resolved_anomaly = state[key]

        append_event(
            {
                "event_type":
                    "anomaly_resolved",
                "timestamp": timestamp,
                **resolved_anomaly,
            }
        )

        print(
            f"RESOLVED: "
            f"{resolved_anomaly['edge_id']} "
            f"{resolved_anomaly['metric']}"
        )

        del state[key]

    save_json(
        STATE_FILE,
        state,
    )

    save_json(
        CURRENT_ANOMALIES_FILE,
        current_anomalies,
    )

    return current_anomalies


def run_detector() -> None:
    baselines = load_edge_baselines()

    print(
        "Starting OTEL Demo edge-aware "
        "latency anomaly detector."
    )

    print(
        f"Prometheus: {PROMETHEUS_URL}"
    )

    print(
        f"Polling every "
        f"{POLL_INTERVAL_SECONDS}s"
    )

    print(
        f"High threshold: "
        f"{HIGH_LATENCY_MULTIPLIER}x baseline"
    )

    print(
        f"Critical threshold: "
        f"{CRITICAL_LATENCY_MULTIPLIER}x baseline"
    )

    print()

    while True:
        try:
            anomalies = (
                detect_latency_anomalies(
                    baselines
                )
            )

            current = (
                enrich_and_save_anomalies(
                    anomalies
                )
            )

            print(
                f"{now_utc()} | "
                f"active anomalies: "
                f"{len(current)}"
            )

        except requests.RequestException as error:
            print(
                f"Could not query Prometheus: "
                f"{error}"
            )

        except Exception as error:
            print(
                f"Detector error: {error}"
            )

        time.sleep(
            POLL_INTERVAL_SECONDS
        )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Edge-aware p95 latency anomaly "
            "detector for the OpenTelemetry Demo."
        )
    )

    parser.add_argument(
        "--learn-baseline",
        action="store_true",
        help=(
            "Observe normal traffic and generate "
            "edge_latency_baselines.json."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.learn_baseline:
        learn_baselines()
        return

    run_detector()


if __name__ == "__main__":
    main()
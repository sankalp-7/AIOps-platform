"""Build a weighted MicroRCA-style anomalous subgraph and run PPR.



Inputs expected in the current directory:

  * latest_kiali_graph.json   - saved by the existing Kiali SDG script

  * current_anomalies.json    - active anomalies from an edge-aware detector



The latency anomaly objects must contain:

  {

    "metric": "p95_latency_ms",

    "source": "qotd-web",

    "destination": "qotd-quote",

    ...

  }



Outputs:

  * microrca_subgraph.json

  * rca_ranking.json



Dependencies:

  pip install networkx pandas requests



The host metric queries assume Prometheus exposes a `node` label on cAdvisor

metrics. If that label is unavailable, host edges are retained with zero weight

until node-exporter or another host-metric source is configured.

"""



from __future__ import annotations



import json

import math

import subprocess

import time

from datetime import datetime, timezone

from collections import defaultdict

from pathlib import Path

from typing import Any, Iterable



import networkx as nx

import pandas as pd

import requests


import json
import os
from typesafe_sdk import Choice, Score, Noul,TypeSafeClient


PROMETHEUS_URL = "http://localhost:9090"

NAMESPACE = "otel-demo"

WINDOW_SECONDS = 600

STEP_SECONDS = 60

MIN_CORRELATION_SAMPLES = 8

ANOMALOUS_EDGE_ALPHA = 0.55

PAGERANK_DAMPING = 0.85



KIALI_GRAPH_FILE = Path("latest_kiali_graph.json")

ANOMALIES_FILE = Path("current_anomalies.json")

OUTPUT_GRAPH_FILE = Path("microrca_subgraph.json")

OUTPUT_RANKING_FILE = Path("rca_ranking.json")

JEV_STATE_FILE = Path("jev_incident_state.json")

MAX_LOG_LINES_PER_CONTAINER: int | None = 500





EDGE_P95_QUERY = """

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

      }[5m]

    )

  )

)

"""





def load_json(path: Path) -> Any:

    with path.open("r", encoding="utf-8") as file:

        return json.load(file)





def save_json(path: Path, payload: Any) -> None:

    with path.open("w", encoding="utf-8") as file:

        json.dump(payload, file, indent=2, allow_nan=False)





def build_dependency_graph(kiali_data: dict[str, Any]) -> nx.DiGraph:

    """Rebuild the caller -> callee workload graph from saved Kiali JSON."""

    graph = nx.DiGraph()

    id_to_workload: dict[str, str] = {}



    for node in kiali_data.get("elements", {}).get("nodes", []):

        node_data = node.get("data", {})

        node_id = node_data.get("id")

        workload = node_data.get("workload")

        if not node_id or not workload:

            continue



        id_to_workload[node_id] = workload

        graph.add_node(workload, kind="service")



    for edge in kiali_data.get("elements", {}).get("edges", []):

        edge_data = edge.get("data", {})

        source = id_to_workload.get(edge_data.get("source"))

        destination = id_to_workload.get(edge_data.get("target"))

        if not source or not destination:

            continue

        # Kiali can expose proxy/internal self-loops. They are not useful for
        # service-to-service RCA and can distort graph centrality.
        if source == destination:
            continue



        graph.add_edge(

            source,

            destination,

            edge_type="service_call",

            kiali_response_time=edge_data.get("responseTime"),

            health_status=edge_data.get("healthStatus"),

        )



    return graph





def query_prometheus_range(

    query: str,

    start: float,

    end: float,

    step: int = STEP_SECONDS,

) -> list[dict[str, Any]]:

    response = requests.get(

        f"{PROMETHEUS_URL}/api/v1/query_range",

        params={

            "query": query,

            "start": start,

            "end": end,

            "step": step,

        },

        timeout=30,

    )

    response.raise_for_status()

    payload = response.json()



    if payload.get("status") != "success":

        raise RuntimeError(f"Prometheus range query failed: {payload}")



    return payload["data"]["result"]





def result_to_series(result: dict[str, Any]) -> pd.Series:

    values: dict[float, float] = {}

    for timestamp, raw_value in result.get("values", []):

        value = float(raw_value)

        if math.isfinite(value):

            values[float(timestamp)] = value



    return pd.Series(values, dtype="float64").sort_index()





def sum_results(results: list[dict[str, Any]]) -> pd.Series:

    series = [result_to_series(result) for result in results]

    series = [item for item in series if not item.empty]

    if not series:

        return pd.Series(dtype="float64")



    frame = pd.concat(series, axis=1).sort_index()

    return frame.sum(axis=1, min_count=1)





def fetch_all_edge_response_times(

    start: float,

    end: float,

) -> dict[tuple[str, str], pd.Series]:

    edge_series: dict[tuple[str, str], pd.Series] = {}



    for result in query_prometheus_range(EDGE_P95_QUERY, start, end):

        metric = result.get("metric", {})

        source = metric.get("source_workload")

        destination = metric.get("destination_workload")

        if not source or not destination:

            continue



        series = result_to_series(result)

        if not series.empty:

            edge_series[(source, destination)] = series

    print(edge_series)

    return edge_series





def correlation_with_status(
    first: pd.Series,
    second: pd.Series,
    *,
    absolute: bool = False,
) -> tuple[float, bool]:
    """Return (correlation, usable).

    usable=False means there was not enough valid telemetry to compute a
    correlation. This is intentionally different from a real correlation of
    zero so missing telemetry is not averaged into service edge weights.
    """
    if first.empty or second.empty:
        return 0.0, False

    frame = pd.concat(
        [first.rename("first"), second.rename("second")],
        axis=1,
    ).dropna()

    if len(frame) < MIN_CORRELATION_SAMPLES:
        return 0.0, False

    if frame["first"].nunique() < 2 or frame["second"].nunique() < 2:
        return 0.0, False

    col_first: pd.Series = frame["first"]  # type: ignore[assignment]
    col_second: pd.Series = frame["second"]  # type: ignore[assignment]
    correlation = float(col_first.corr(col_second))

    if not math.isfinite(correlation):
        return 0.0, False

    if absolute:
        correlation = abs(correlation)

    # PageRank edge weights must be non-negative.
    return max(0.0, min(1.0, correlation)), True


def safe_correlation(
    first: pd.Series,
    second: pd.Series,
    *,
    absolute: bool = False,
) -> float:
    correlation, _ = correlation_with_status(
        first,
        second,
        absolute=absolute,
    )
    return correlation



def aligned_mean(series: Iterable[pd.Series]) -> pd.Series:

    usable = [item for item in series if not item.empty]

    if not usable:

        return pd.Series(dtype="float64")



    frame = pd.concat(usable, axis=1).sort_index()

    return frame.mean(axis=1, skipna=True)





def load_anomalous_edges() -> set[tuple[str, str]]:

    anomalies = load_json(ANOMALIES_FILE)

    anomalous_edges: set[tuple[str, str]] = set()



    for anomaly in anomalies:

        if anomaly.get("metric") != "p95_latency_ms":

            continue



        source = anomaly.get("source")

        destination = anomaly.get("destination")

        if not source or not destination:

            raise ValueError(

                "Latency anomalies must contain 'source' and 'destination'. "

                "The current detector is still destination-service based; "

                "change it to detect per-edge latency first."

            )



        anomalous_edges.add((source, destination))



    if not anomalous_edges:

        raise ValueError("No active edge-level p95 latency anomalies were found.")



    return anomalous_edges





def kubectl_pod_inventory(

    known_services: set[str],

) -> tuple[dict[str, list[str]], dict[str, set[str]]]:

    """Map Kiali workload names to their pods and Kubernetes nodes."""

    completed = subprocess.run(

        ["kubectl", "get", "pods", "-n", NAMESPACE, "-o", "json"],

        check=True,

        capture_output=True,

        text=True,

    )

    payload = json.loads(completed.stdout)



    service_to_pods: dict[str, list[str]] = defaultdict(list)

    service_to_hosts: dict[str, set[str]] = defaultdict(set)



    services_by_length = sorted(known_services, key=len, reverse=True)



    for item in payload.get("items", []):

        pod_name = item.get("metadata", {}).get("name", "")

        host = item.get("spec", {}).get("nodeName")

        labels = item.get("metadata", {}).get("labels", {})



        service = next(

            (

                candidate

                for candidate in services_by_length

                if pod_name == candidate or pod_name.startswith(f"{candidate}-")

            ),

            None,

        )



        if service is None:

            label_values = {

                str(value)

                for value in labels.values()

                if isinstance(value, str)

            }

            service = next(

                (candidate for candidate in services_by_length if candidate in label_values),

                None,

            )



        if not service:

            continue



        service_to_pods[service].append(pod_name)

        if host:

            service_to_hosts[service].add(host)



    return dict(service_to_pods), dict(service_to_hosts)





def pod_regex(pods: list[str]) -> str:



    return "(" + "|".join(sorted(set(pods))) + ")"





def fetch_container_metrics(

    service_to_pods: dict[str, list[str]],

    services: set[str],

    start: float,

    end: float,

) -> dict[str, dict[str, pd.Series]]:

    output: dict[str, dict[str, pd.Series]] = {}



    for service in services:

        pods = service_to_pods.get(service, [])

        if not pods:

            output[service] = {}

            continue



        regex = pod_regex(pods)

        selector = (

            f'namespace="{NAMESPACE}",pod=~"{regex}",'

            'container!="POD",container!="",container!="istio-proxy"'

        )



        queries = {

            "cpu": (

                "sum(rate(container_cpu_usage_seconds_total{"

                + selector

                + "}[3m]))"

            ),

            "memory": (

                "sum(container_memory_working_set_bytes{"

                + selector

                + "})"

            ),

            "network": (

                f'sum(rate(container_network_receive_bytes_total{{namespace="{NAMESPACE}",pod=~"{regex}"}}[3m])) '

                "+ "

                f'sum(rate(container_network_transmit_bytes_total{{namespace="{NAMESPACE}",pod=~"{regex}"}}[3m]))'

            ),

        }



        output[service] = {

            name: sum_results(query_prometheus_range(query, start, end))

            for name, query in queries.items()

        }



    return output





def fetch_host_metrics(

    hosts: set[str],

    start: float,

    end: float,

) -> dict[str, dict[str, pd.Series]]:

    """Fetch host-level pressure metrics when cAdvisor has a `node` label."""

    output: dict[str, dict[str, pd.Series]] = {}



    for host in hosts:

        container_selector = (

            f'node="{host}",container!="POD",container!=""'

        )



        queries = {

            "cpu": (

                "sum(rate(container_cpu_usage_seconds_total{"

                + container_selector

                + "}[3m]))"

            ),

            "memory": (

                "sum(container_memory_working_set_bytes{"

                + container_selector

                + "})"

            ),

            "network": (

                f'sum(rate(container_network_receive_bytes_total{{node="{host}"}}[3m])) '

                "+ "

                f'sum(rate(container_network_transmit_bytes_total{{node="{host}"}}[3m]))'

            ),

            "io": (

                "sum(rate(container_fs_reads_bytes_total{"

                + container_selector

                + "}[3m])) + "

                "sum(rate(container_fs_writes_bytes_total{"

                + container_selector

                + "}[3m]))"

            ),

        }



        output[host] = {

            name: sum_results(query_prometheus_range(query, start, end))

            for name, query in queries.items()

        }



    return output





def extract_anomalous_subgraph(

    full_graph: nx.DiGraph,

    anomalous_edges: set[tuple[str, str]],

    service_to_hosts: dict[str, set[str]],

) -> tuple[nx.DiGraph, set[str]]:



    anomalous_services = {

        destination

        for _, destination in anomalous_edges

    }



    subgraph = nx.DiGraph()



    for service in anomalous_services:

        subgraph.add_node(

            service,

            kind="service",

            anomalous=True,

        )



        if service in full_graph:



            for source, destination, data in full_graph.in_edges(

                service,

                data=True,

            ):

                subgraph.add_node(

                    source,

                    kind="service",

                    anomalous=source in anomalous_services,

                )

                subgraph.add_node(

                    destination,

                    kind="service",

                    anomalous=destination in anomalous_services,

                )



                edge_attributes = dict(data)

                edge_attributes["edge_type"] = "service_call"

                edge_attributes["anomalous"] = (

                    source,

                    destination,

                ) in anomalous_edges



                subgraph.add_edge(

                    source,

                    destination,

                    **edge_attributes,

                )





            for source, destination, data in full_graph.out_edges(

                service,

                data=True,

            ):

                subgraph.add_node(

                    source,

                    kind="service",

                    anomalous=source in anomalous_services,

                )

                subgraph.add_node(

                    destination,

                    kind="service",

                    anomalous=destination in anomalous_services,

                )



                edge_attributes = dict(data)

                edge_attributes["edge_type"] = "service_call"

                edge_attributes["anomalous"] = (

                    source,

                    destination,

                ) in anomalous_edges



                subgraph.add_edge(

                    source,

                    destination,

                    **edge_attributes,

                )





        for host in service_to_hosts.get(service, set()):

            host_node = f"host::{host}"



            subgraph.add_node(

                host_node,

                kind="host",

                anomalous=False,

                host_name=host,

            )



            subgraph.add_edge(

                service,

                host_node,

                edge_type="runs_on",

                anomalous=False,

            )





    for source, destination in anomalous_edges:

        subgraph.add_node(

            source,

            kind="service",

            anomalous=source in anomalous_services,

        )

        subgraph.add_node(

            destination,

            kind="service",

            anomalous=True,

        )



        if not subgraph.has_edge(source, destination):

            subgraph.add_edge(

                source,

                destination,

                edge_type="service_call",

                anomalous=True,

            )



    return subgraph, anomalous_services



def build_anomaly_response_times(

    anomalous_services: set[str],

    anomalous_edges: set[tuple[str, str]],

    edge_response_times: dict[tuple[str, str], pd.Series],

) -> dict[str, pd.Series]:

    rt_a: dict[str, pd.Series] = {}



    for service in anomalous_services:

        incoming_anomalous_series = [

            edge_response_times[edge]

            for edge in anomalous_edges

            if edge[1] == service and edge in edge_response_times

        ]

        rt_a[service] = aligned_mean(incoming_anomalous_series)



    return rt_a





def assign_service_edge_weights(
    subgraph: nx.DiGraph,
    anomalous_edges: set[tuple[str, str]],
    anomalous_services: set[str],
    edge_response_times: dict[tuple[str, str], pd.Series],
    rt_a: dict[str, pd.Series],
) -> None:
    for source, destination, data in subgraph.edges(data=True):
        if data.get("edge_type") != "service_call":
            continue

        edge = (source, destination)

        if edge in anomalous_edges:
            weight = ANOMALOUS_EDGE_ALPHA
            correlation = None
            weight_available = True
            reason = "anomaly_detector_confidence"
        else:
            edge_rt = edge_response_times.get(
                edge,
                pd.Series(dtype="float64"),
            )
            references = [
                rt_a[service]
                for service in (source, destination)
                if service in anomalous_services
                and not rt_a.get(service, pd.Series(dtype="float64")).empty
            ]

            correlation_results = [
                correlation_with_status(edge_rt, reference)
                for reference in references
            ]
            usable_correlations = [
                correlation
                for correlation, usable in correlation_results
                if usable
            ]

            if usable_correlations:
                correlation = max(usable_correlations)
                weight = correlation
                weight_available = True
            else:
                correlation = 0.0
                weight = 0.0
                weight_available = False

            reason = "edge_rt_vs_anomalous_service_rt"

        data["weight"] = round(weight, 6)
        data["correlation"] = (
            None if correlation is None else round(correlation, 6)
        )
        data["weight_available"] = weight_available
        data["weight_reason"] = reason



def assign_host_edge_weights(

    subgraph: nx.DiGraph,

    anomalous_services: set[str],

    rt_a: dict[str, pd.Series],

    host_metrics: dict[str, dict[str, pd.Series]],

) -> None:

    for service in anomalous_services:

        incoming_weights = [

            float(data.get("weight", 0.0))

            for _, _, data in subgraph.in_edges(service, data=True)

            if data.get("edge_type") == "service_call"

        ]

        average_incoming_weight = (

            sum(incoming_weights) / len(incoming_weights)

            if incoming_weights

            else 0.0

        )



        for _, host_node, edge_data in subgraph.out_edges(service, data=True):

            if edge_data.get("edge_type") != "runs_on":

                continue



            host_name = subgraph.nodes[host_node].get("host_name")

            metric_correlations = {

                metric: safe_correlation(

                    rt_a.get(service, pd.Series(dtype="float64")),

                    series,

                    absolute=True,

                )

                for metric, series in (

                    host_metrics.get(host_name, {}) if host_name is not None else {}

                ).items()

            }



            strongest_metric, strongest_correlation = max(

                metric_correlations.items(),

                key=lambda item: item[1],

                default=(None, 0.0),

            )



            weight = average_incoming_weight * strongest_correlation

            edge_data["weight"] = round(weight, 6)

            edge_data["correlation"] = round(strongest_correlation, 6)

            edge_data["strongest_metric"] = strongest_metric

            edge_data["average_incoming_weight"] = round(

                average_incoming_weight,

                6,

            )

            edge_data["weight_reason"] = "host_metric_vs_anomalous_service_rt"





def assign_service_anomaly_scores(
    subgraph: nx.DiGraph,
    anomalous_services: set[str],
    rt_a: dict[str, pd.Series],
    container_metrics: dict[str, dict[str, pd.Series]],
) -> None:
    for node in subgraph.nodes:
        subgraph.nodes[node]["as_score"] = 0.0

    for service in anomalous_services:
        service_edge_weights: list[float] = []

        for _, _, data in subgraph.in_edges(service, data=True):
            if (
                data.get("edge_type") == "service_call"
                and data.get("weight_available", True)
            ):
                service_edge_weights.append(float(data.get("weight", 0.0)))

        for _, destination, data in subgraph.out_edges(service, data=True):
            if (
                data.get("edge_type") == "service_call"
                and subgraph.nodes[destination].get("kind") == "service"
                and data.get("weight_available", True)
            ):
                service_edge_weights.append(float(data.get("weight", 0.0)))

        average_edge_weight = (
            sum(service_edge_weights) / len(service_edge_weights)
            if service_edge_weights
            else 0.0
        )

        metric_correlations: dict[str, float] = {}
        for metric, series in container_metrics.get(service, {}).items():
            correlation, usable = correlation_with_status(
                rt_a.get(service, pd.Series(dtype="float64")),
                series,
                absolute=True,
            )
            if usable:
                metric_correlations[metric] = correlation

        strongest_metric, strongest_correlation = max(
            metric_correlations.items(),
            key=lambda item: item[1],
            default=(None, 0.0),
        )

        # Published MicroRCA Eq. (3):
        # AS(service) = average edge weight * strongest container correlation.
        anomaly_score = average_edge_weight * strongest_correlation

        node_data = subgraph.nodes[service]
        node_data["as_score"] = round(anomaly_score, 6)
        node_data["average_service_edge_weight"] = round(
            average_edge_weight,
            6,
        )
        node_data["container_metric_correlation"] = round(
            strongest_correlation,
            6,
        )
        node_data["strongest_container_metric"] = strongest_metric



def run_personalized_pagerank(

    subgraph: nx.DiGraph,

    anomalous_services: set[str],

) -> tuple[nx.DiGraph, dict[str, float], list[dict[str, Any]]]:

    ppr_graph = nx.DiGraph()

    ppr_graph.add_nodes_from(subgraph.nodes(data=True))



    for source, destination, data in subgraph.edges(data=True):

        weight = float(data.get("weight", 0.0))

        if weight <= 0.0:

            continue



        if data.get("edge_type") == "service_call":



            ppr_graph.add_edge(destination, source, weight=weight)

        else:



            ppr_graph.add_edge(source, destination, weight=weight)



    personalization = {

        node: (

            float(subgraph.nodes[node].get("as_score", 0.0))

            if node in anomalous_services

            else 0.0

        )

        for node in ppr_graph.nodes

    }



    if sum(personalization.values()) <= 0.0:



        personalization = {

            node: (1.0 if node in anomalous_services else 0.0)

            for node in ppr_graph.nodes

        }



    scores = nx.pagerank(

        ppr_graph,

        alpha=PAGERANK_DAMPING,

        personalization=personalization,

        dangling=personalization,

        weight="weight",

        max_iter=1000,

        tol=1.0e-10,

    )



    for node, score in scores.items():

        subgraph.nodes[node]["ppr_score"] = round(float(score), 10)



    ranking = [

        {

            "service": node,

            "ppr_score": round(float(score), 10),

            "as_score": float(subgraph.nodes[node].get("as_score", 0.0)),

        }

        for node, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)

        if subgraph.nodes[node].get("kind") == "service"

    ]



    return ppr_graph, scores, ranking





def series_to_points(series: pd.Series) -> list[dict[str, float]]:

    points: list[dict[str, float]] = []

    for timestamp, value in series.items():

        numeric_value = float(value)

        if math.isfinite(numeric_value):

            points.append(

                {

                    "timestamp": float(timestamp),  # type: ignore[arg-type]  # index is always numeric here

                    "value": round(numeric_value, 6),

                }

            )

    return points





def serialize_output(

    subgraph: nx.DiGraph,

    anomalous_edges: set[tuple[str, str]],

    rt_a: dict[str, pd.Series],

    edge_response_times: dict[tuple[str, str], pd.Series],

    container_metrics: dict[str, dict[str, pd.Series]],

    host_metrics: dict[str, dict[str, pd.Series]],

    ranking: list[dict[str, Any]],

    start: float,

    end: float,

) -> dict[str, Any]:

    nodes = []

    for node, data in subgraph.nodes(data=True):

        node_payload = {"id": node, **data}

        if node in rt_a:

            node_payload["rt_a_ms"] = series_to_points(rt_a[node])

        nodes.append(node_payload)



    edges = []

    for source, destination, data in subgraph.edges(data=True):

        edge_payload = {

            "source": source,

            "destination": destination,

            **data,

        }

        if data.get("edge_type") == "service_call":

            edge_payload["rt_ms"] = series_to_points(

                edge_response_times.get(

                    (source, destination),

                    pd.Series(dtype="float64"),

                )

            )

        edges.append(edge_payload)



    return {

        "window": {

            "start_epoch": start,

            "end_epoch": end,

            "step_seconds": STEP_SECONDS,

        },

        "configuration": {

            "anomalous_edge_alpha": ANOMALOUS_EDGE_ALPHA,

            "pagerank_damping": PAGERANK_DAMPING,

            "service_call_direction": "caller_to_callee",

            "ppr_service_edges_reversed": True,

        },

        "anomalous_edges": [

            {"source": source, "destination": destination}

            for source, destination in sorted(anomalous_edges)

        ],

        "nodes": nodes,

        "edges": edges,

        "container_metrics": {

            service: {

                metric: series_to_points(series)

                for metric, series in metrics.items()

            }

            for service, metrics in container_metrics.items()

        },

        "host_metrics": {

            host: {

                metric: series_to_points(series)

                for metric, series in metrics.items()

            }

            for host, metrics in host_metrics.items()

        },

        "ranking": ranking,

    }






def _epoch_to_rfc3339(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def collect_kubernetes_logs(
    service_to_pods: dict[str, list[str]],
    services: set[str],
    start: float,
    *,
    max_lines_per_container: int | None = MAX_LOG_LINES_PER_CONTAINER,
) -> dict[str, list[dict[str, Any]]]:
    """Collect application-container logs for the RCA incident window.

    Istio sidecar logs are excluded intentionally. They are large, and for
    controlled VirtualService delay experiments they may expose experiment
    configuration rather than application evidence.
    """
    pod_list = subprocess.run(
        ["kubectl", "get", "pods", "-n", NAMESPACE, "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    pod_payload = json.loads(pod_list.stdout)

    pod_containers: dict[str, list[str]] = {}
    for item in pod_payload.get("items", []):
        pod_name = item.get("metadata", {}).get("name")
        if not pod_name:
            continue
        pod_containers[pod_name] = [
            container.get("name")
            for container in item.get("spec", {}).get("containers", [])
            if container.get("name")
            and container.get("name") != "istio-proxy"
        ]

    since_time = _epoch_to_rfc3339(start)
    output: dict[str, list[dict[str, Any]]] = {}

    for service in sorted(services):
        records: list[dict[str, Any]] = []

        for pod in service_to_pods.get(service, []):
            for container in pod_containers.get(pod, []):
                completed = subprocess.run(
                    [
                        "kubectl",
                        "logs",
                        "-n",
                        NAMESPACE,
                        pod,
                        "-c",
                        container,
                        f"--since-time={since_time}",
                        "--timestamps=true",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )

                lines = completed.stdout.splitlines()
                truncated = False

                if (
                    max_lines_per_container is not None
                    and len(lines) > max_lines_per_container
                ):
                    lines = lines[-max_lines_per_container:]
                    truncated = True

                record: dict[str, Any] = {
                    "pod": pod,
                    "container": container,
                    "lines": lines,
                    "truncated": truncated,
                }

                if completed.returncode != 0:
                    record["error"] = completed.stderr.strip()

                records.append(record)

        output[service] = records

    return output


def _parse_k8s_timestamp(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).timestamp()
    except ValueError:
        return None


def collect_kubernetes_events(
    start: float,
    end: float,
) -> list[dict[str, Any]]:
    """Collect workload events without leaking the injected fault resource.

    VirtualService/DestinationRule events are excluded because names such as
    aiops-delay-shipping would directly reveal the experimental ground truth.
    """
    completed = subprocess.run(
        ["kubectl", "get", "events", "-n", NAMESPACE, "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    events: list[dict[str, Any]] = []

    for item in payload.get("items", []):
        involved = item.get("involvedObject", {})
        kind = involved.get("kind")
        name = involved.get("name")

        if kind in {"VirtualService", "DestinationRule"}:
            continue
        if isinstance(name, str) and (
            "aiops-delay" in name.lower()
            or "aiops-fault" in name.lower()
        ):
            continue

        candidate_times = [
            item.get("eventTime"),
            (item.get("series") or {}).get("lastObservedTime"),
            item.get("lastTimestamp"),
            item.get("firstTimestamp"),
            item.get("metadata", {}).get("creationTimestamp"),
        ]
        timestamps = [
            parsed
            for parsed in (_parse_k8s_timestamp(value) for value in candidate_times)
            if parsed is not None
        ]

        event_time = max(timestamps) if timestamps else None
        if event_time is not None and not (start <= event_time <= end):
            continue

        events.append(
            {
                "timestamp": event_time,
                "type": item.get("type"),
                "reason": item.get("reason"),
                "message": item.get("message"),
                "count": item.get("count"),
                "involved_object": {
                    "kind": kind,
                    "name": name,
                },
            }
        )

    return events


def build_jev_incident_state(
    full_graph: nx.DiGraph,
    subgraph: nx.DiGraph,
    anomalous_edges: set[tuple[str, str]],
    rt_a: dict[str, pd.Series],
    edge_response_times: dict[tuple[str, str], pd.Series],
    container_metrics: dict[str, dict[str, pd.Series]],
    host_metrics: dict[str, dict[str, pd.Series]],
    service_to_pods: dict[str, list[str]],
    service_to_hosts: dict[str, set[str]],
    start: float,
    end: float,
) -> dict[str, Any]:
    """Build a ground-truth-free incident state suitable for Jev.

    The `same_evidence_as_microrca` section contains only evidence available
    to MicroRCA before its correlation/weight/PageRank calculations.

    Logs and Kubernetes events are placed in a separate section because the
    current MicroRCA implementation does not use them. Feeding that section to
    Jev is therefore an expanded-evidence experiment, not an apples-to-apples
    comparison.
    """
    relevant_services = {
        node
        for node, data in subgraph.nodes(data=True)
        if data.get("kind") == "service"
    }

    subgraph_service_edges = [
        (source, destination, data)
        for source, destination, data in subgraph.edges(data=True)
        if data.get("edge_type") == "service_call"
    ]

    same_evidence = {
        "topology": {
            "direction": "caller_to_callee",
            "nodes": sorted(
                node
                for node, data in full_graph.nodes(data=True)
                if data.get("kind") == "service"
            ),
            "edges": [
                {
                    "source": source,
                    "destination": destination,
                    "kiali_response_time": data.get("kiali_response_time"),
                    "health_status": data.get("health_status"),
                }
                for source, destination, data in full_graph.edges(data=True)
                if data.get("edge_type") == "service_call"
            ],
        },
        "anomalous_edges": [
            {
                "source": source,
                "destination": destination,
            }
            for source, destination in sorted(anomalous_edges)
        ],
        "analysis_scope": {
            "services": sorted(relevant_services),
            "service_edges": [
                {
                    "source": source,
                    "destination": destination,
                    "anomalous": (source, destination) in anomalous_edges,
                }
                for source, destination, _ in subgraph_service_edges
            ],
        },
        "edge_latency_p95_ms": [
            {
                "source": source,
                "destination": destination,
                "series": series_to_points(
                    edge_response_times.get(
                        (source, destination),
                        pd.Series(dtype="float64"),
                    )
                ),
            }
            for source, destination, _ in subgraph_service_edges
        ],
        "anomalous_service_latency_reference_ms": {
            service: series_to_points(series)
            for service, series in rt_a.items()
        },
        "service_resource_metrics": {
            service: {
                metric: series_to_points(series)
                for metric, series in metrics.items()
            }
            for service, metrics in container_metrics.items()
        },
        "host_resource_metrics": {
            host: {
                metric: series_to_points(series)
                for metric, series in metrics.items()
            }
            for host, metrics in host_metrics.items()
        },
        "deployment_mapping": {
            "service_to_pods": {
                service: sorted(pods)
                for service, pods in service_to_pods.items()
                if service in relevant_services
            },
            "service_to_hosts": {
                service: sorted(hosts)
                for service, hosts in service_to_hosts.items()
                if service in relevant_services
            },
        },
    }


    return {
        "schema_version": "1.0",
        "namespace": NAMESPACE,
        "incident_window": {
            "start_epoch": start,
            "end_epoch": end,
            "start_utc": _epoch_to_rfc3339(start),
            "end_utc": _epoch_to_rfc3339(end),
            "window_seconds": WINDOW_SECONDS,
            "step_seconds": STEP_SECONDS,
        },
        "collection_configuration": {
            "edge_p95_query": EDGE_P95_QUERY.strip(),
            "prometheus_url": PROMETHEUS_URL,
        },
        "leakage_guard": {
            "ground_truth_included": False,
            "fault_injection_configuration_included": False,
            "microrca_correlations_weights_scores_or_ranking_included": False,
        },
        "timeseries_evidence": same_evidence,
    }

def run_jev(system_state):
    client = TypeSafeClient()

    response = client.system_one(
        state=system_state,
        questions={
            "RCA": Choice(
                instructions="Which service is the most likely originating root cause of the observed incident, based only on the provided system state?",
                criteria={
                    "ad": "The ad service is the originating root cause.",
                    "cart": "The cart service is the originating root cause.",
                    "checkout": "The checkout service is the originating root cause.",
                    "currency": "The currency service is the originating root cause.",
                    "email": "The email service is the originating root cause.",
                    "frontend": "The frontend service is the originating root cause.",
                    "image_provider": "The image-provider service is the originating root cause.",
                    "payment": "The payment service is the originating root cause.",
                    "product_catalog": "The product-catalog service is the originating root cause.",
                    "quote": "The quote service is the originating root cause.",
                    "recommendation": "The recommendation service is the originating root cause.",
                    "shipping": "The shipping service is the originating root cause."
                },
            ),
        },
    )

    print(response.answers["RCA"].probabilities)

def main() -> None:

    if not KIALI_GRAPH_FILE.exists():

        raise FileNotFoundError(

            f"{KIALI_GRAPH_FILE} does not exist. Run the Kiali SDG script first."

        )



    if not ANOMALIES_FILE.exists():

        raise FileNotFoundError(

            f"{ANOMALIES_FILE} does not exist. Run the anomaly detector first."

        )



    end = time.time()

    start = end - WINDOW_SECONDS



    # builds the graph ds and also a set containing the anomalous edges

    full_graph = build_dependency_graph(load_json(KIALI_GRAPH_FILE))

    anomalous_edges = load_anomalous_edges()



    # gets which pod in the cluster each service is running in and also on which node

    service_to_pods, service_to_hosts = kubectl_pod_inventory(

        set(full_graph.nodes) | {node for edge in anomalous_edges for node in edge}

    )



    subgraph, anomalous_services = extract_anomalous_subgraph(

        full_graph,

        anomalous_edges,

        service_to_hosts,

    )



    edge_response_times = fetch_all_edge_response_times(start, end)

    rt_a = build_anomaly_response_times(

        anomalous_services,

        anomalous_edges,

        edge_response_times,

    )



    missing_rt_a = [service for service, series in rt_a.items() if series.empty]

    if missing_rt_a:

        print(

            "WARNING: no anomalous RT time series found for: "

            + ", ".join(sorted(missing_rt_a))

        )



    container_metrics = fetch_container_metrics(

        service_to_pods,

        anomalous_services,

        start,

        end,

    )



    host_names = {

        host_name

        for _, data in subgraph.nodes(data=True)

        if data.get("kind") == "host" and (host_name := data.get("host_name"))

    }

    host_metrics = fetch_host_metrics(host_names, start, end)



    assign_service_edge_weights(

        subgraph,

        anomalous_edges,

        anomalous_services,

        edge_response_times,

        rt_a,

    )

    assign_host_edge_weights(

        subgraph,

        anomalous_services,

        rt_a,

        host_metrics,

    )

    assign_service_anomaly_scores(

        subgraph,

        anomalous_services,

        rt_a,

        container_metrics,

    )



    _, _, ranking = run_personalized_pagerank(

        subgraph,

        anomalous_services,

    )



    output = serialize_output(

        subgraph,

        anomalous_edges,

        rt_a,

        edge_response_times,

        container_metrics,

        host_metrics,

        ranking,

        start,

        end,

    )

    save_json(OUTPUT_GRAPH_FILE, output)

    save_json(OUTPUT_RANKING_FILE, ranking)

    jev_state = build_jev_incident_state(
        full_graph,
        subgraph,
        anomalous_edges,
        rt_a,
        edge_response_times,
        container_metrics,
        host_metrics,
        service_to_pods,
        service_to_hosts,
        start,
        end,
    )
    save_json(JEV_STATE_FILE, jev_state)



    print("\nMicroRCA ranking:")

    for index, item in enumerate(ranking, start=1):

        print(

            f"{index:>2}. {item['service']:<25} "

            f"PPR={item['ppr_score']:.6f} "

            f"AS={item['as_score']:.6f}"

        )
    print("\nJev ranking:")
    run_jev(jev_state)





if __name__ == "__main__":

    main()
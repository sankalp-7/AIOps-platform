import json
import argparse
import networkx as nx
from typing import Dict, List, Set, Tuple, Any


def load_kiali_graph(graph_json_path: str) -> nx.DiGraph:
    """
    Loads Kiali graph JSON and creates dependency graph.

    Kiali direction:
        service A -> service B means A calls/depends on B

    Example:
        qotd-web -> qotd-quote
    """
    with open(graph_json_path, "r") as f:
        data = json.load(f)

    G = nx.DiGraph()

    id_to_service = {}

    for node in data["elements"]["nodes"]:
        node_data = node["data"]
        node_id = node_data["id"]
        workload = node_data.get("workload") or node_data.get("app") or node_id

        id_to_service[node_id] = workload
        G.add_node(
            workload,
            namespace=node_data.get("namespace"),
            app=node_data.get("app"),
            health=node_data.get("healthData", {})
        )

    for edge in data["elements"]["edges"]:
        edge_data = edge["data"]

        src_id = edge_data["source"]
        dst_id = edge_data["target"]

        if src_id not in id_to_service or dst_id not in id_to_service:
            continue

        src = id_to_service[src_id]
        dst = id_to_service[dst_id]

        G.add_edge(
            src,
            dst,
            response_time=float(edge_data.get("responseTime", 0) or 0),
            health_status=edge_data.get("healthStatus", "Unknown"),
            traffic=edge_data.get("traffic", {})
        )

    return G


def load_anomalies(anomalies_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Expected anomalies.json format:

    [
      {
        "service": "qotd-web",
        "metric": "latency",
        "severity": "high",
        "value": 850,
        "first_seen": "10:04"
      },
      {
        "service": "qotd-quote",
        "metric": "latency",
        "severity": "critical",
        "value": 1200,
        "first_seen": "10:01"
      }
    ]
    """
    with open(anomalies_path, "r") as f:
        anomalies = json.load(f)

    return {a["service"]: a for a in anomalies}


def severity_score(severity: str) -> float:
    scores = {
        "low": 1.0,
        "medium": 2.0,
        "high": 3.0,
        "critical": 4.0
    }
    return scores.get(severity.lower(), 1.0)


def build_failure_propagation_graph(dependency_graph: nx.DiGraph) -> nx.DiGraph:
    """
    Dependency graph direction:
        frontend -> orders -> payment
        means frontend depends on orders, orders depends on payment.

    Failure propagation direction is reverse:
        payment -> orders -> frontend
    """
    return dependency_graph.reverse(copy=True)


def rank_root_causes(
    dependency_graph: nx.DiGraph,
    anomalies: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    RADICE/MicroHECL-inspired simplified ranking:

    Root cause candidate is strong if:
    1. It is anomalous.
    2. It can reach/explain many other anomalous nodes in failure propagation graph.
    3. It has high severity.
    4. It appears earlier than impacted services if timestamps are available.
    """

    anomalous_services: Set[str] = set(anomalies.keys())

    propagation_graph = build_failure_propagation_graph(dependency_graph)

    results = []

    for service in anomalous_services:
        if service not in propagation_graph:
            continue

        reachable = nx.descendants(propagation_graph, service) #all services reachable from service
        impacted_anomalous = reachable.intersection(anomalous_services) #all anomalous services reachable from service

        anomaly = anomalies[service]
        sev = severity_score(anomaly.get("severity", "low"))

        coverage_score = len(impacted_anomalous) * 2.0
        severity_component = sev

        score = coverage_score + severity_component

        results.append({
            "service": service,
            "score": round(score, 3),
            "severity": anomaly.get("severity"),
            "metric": anomaly.get("metric"),
            "value": anomaly.get("value"),
            "first_seen": anomaly.get("first_seen"),
            "explains": sorted(list(impacted_anomalous)),
            "num_explained": len(impacted_anomalous)
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def build_anomalous_subgraph(
    dependency_graph: nx.DiGraph,
    anomalies: Dict[str, Dict[str, Any]]
) -> nx.DiGraph:
    anomalous_services = set(anomalies.keys())

    sub_nodes = set()

    for service in anomalous_services:
        if service not in dependency_graph:
            continue

        sub_nodes.add(service)

        # include direct neighbors for context
        sub_nodes.update(dependency_graph.predecessors(service))
        sub_nodes.update(dependency_graph.successors(service))

    return nx.DiGraph(dependency_graph.subgraph(sub_nodes))


def get_evidence_collection_targets(
    dependency_graph: nx.DiGraph,
    ranked_candidates: List[Dict[str, Any]],
    top_k: int = 3
) -> Dict[str, List[str]]:
    """
    For each top candidate, collect logs/events from:
    - candidate itself
    - direct callers
    - direct dependencies
    """
    targets = {}

    for candidate in ranked_candidates[:top_k]:
        service = candidate["service"]

        if service not in dependency_graph:
            targets[service] = [service]
            continue

        neighbors = set()
        neighbors.add(service)

        # callers/upstream
        neighbors.update(dependency_graph.predecessors(service))

        # dependencies/downstream
        neighbors.update(dependency_graph.successors(service))

        targets[service] = sorted(list(neighbors))

    return targets


def create_llm_context(
    dependency_graph: nx.DiGraph,
    anomalies: Dict[str, Dict[str, Any]],
    ranked_candidates: List[Dict[str, Any]],
    top_k: int = 3
) -> Dict[str, Any]:
    anomalous_subgraph = build_anomalous_subgraph(dependency_graph, anomalies)

    context = {
        "task": "Root Cause Analysis for microservice incident",
        "graph_semantics": {
            "dependency_graph_direction": "A -> B means A depends on/calls B",
            "failure_propagation_direction": "reverse of dependency direction"
        },
        "anomalies": list(anomalies.values()),
        "top_rca_candidates": ranked_candidates[:top_k],
        "affected_subgraph": {
            "nodes": list(anomalous_subgraph.nodes()),
            "edges": list(anomalous_subgraph.edges())
        },
        "evidence_collection_targets": get_evidence_collection_targets(
            dependency_graph,
            ranked_candidates,
            top_k=top_k
        )
    }

    return context


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--graph",
        required=True,
        help="Path to Kiali graph JSON"
    )

    parser.add_argument(
        "--anomalies",
        required=True,
        help="Path to anomalies JSON"
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of RCA candidates to return"
    )

    parser.add_argument(
        "--output",
        default="llm_context.json",
        help="Output JSON file for LLM context"
    )

    args = parser.parse_args()

    dependency_graph = load_kiali_graph(args.graph)
    anomalies = load_anomalies(args.anomalies)

    ranked = rank_root_causes(dependency_graph, anomalies)

    print("\n=== RCA Ranking ===")
    for i, item in enumerate(ranked[:args.top_k], start=1):
        print(f"\nRank {i}: {item['service']}")
        print(f"  Score: {item['score']}")
        print(f"  Severity: {item['severity']}")
        print(f"  Metric: {item['metric']}")
        print(f"  Explains: {item['explains']}")

    context = create_llm_context(
        dependency_graph,
        anomalies,
        ranked,
        top_k=args.top_k
    )

    with open(args.output, "w") as f:
        json.dump(context, f, indent=2)

    print(f"\nLLM context written to: {args.output}")


if __name__ == "__main__":
    main()
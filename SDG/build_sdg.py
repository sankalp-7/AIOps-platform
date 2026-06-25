import json
import sys
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

import networkx as nx
import matplotlib.pyplot as plt


KIALI_GRAPH_URL = (
    "http://localhost:20001/kiali/api/namespaces/graph"
    "?namespaces=qotd"
)
NAMESPACE = "qotd"
GRAPH_TYPE = "workload"
DURATION_SECONDS = 600


def fetch_kiali_graph():
    print(f"Calling Kiali URL: {KIALI_GRAPH_URL}")

    try:
        with urlopen(KIALI_GRAPH_URL, timeout=30) as response:
            raw_response = response.read().decode("utf-8")

        return json.loads(raw_response)

    except HTTPError as err:
        print(f"Kiali returned HTTP {err.code}: {err.reason}")

        error_body = err.read().decode("utf-8", errors="replace")
        print("Kiali response body:")
        print(error_body)

        sys.exit(1)

    except URLError as err:
        print(f"Could not reach Kiali: {err.reason}")
        print(
            "\nEnsure this is running in another terminal:\n"
            "kubectl port-forward -n istio-system svc/kiali 20001:20001"
        )
        sys.exit(1)

    except json.JSONDecodeError as err:
        print("Kiali returned a response, but it was not valid JSON.")
        print(err)
        sys.exit(1)


def build_dependency_graph(data):
    graph = nx.DiGraph()
    id_to_workload = {}

    for node in data.get("elements", {}).get("nodes", []):
        node_data = node.get("data", {})

        node_id = node_data.get("id")
        workload = node_data.get("workload")

        # Ignore nodes that are not actual workloads.
        if not node_id or not workload:
            continue

        id_to_workload[node_id] = workload
        graph.add_node(workload)

    for edge in data.get("elements", {}).get("edges", []):
        edge_data = edge.get("data", {})

        source_id = edge_data.get("source")
        target_id = edge_data.get("target")

        source_workload = id_to_workload.get(source_id)
        target_workload = id_to_workload.get(target_id)

        # Some Kiali edges can point to nodes without workload data.
        if not source_workload or not target_workload:
            continue

        response_time = edge_data.get("responseTime", "unknown")
        health_status = edge_data.get("healthStatus", "unknown")

        graph.add_edge(
            source_workload,
            target_workload,
            response_time=response_time,
            health_status=health_status,
        )

    return graph


def draw_graph(graph):
    plt.figure(figsize=(16, 10))

    pos = nx.spring_layout(graph, seed=42, k=1.2)

    nx.draw_networkx_nodes(
        graph,
        pos,
        node_size=2500,
        node_color="lightblue",
    )

    nx.draw_networkx_edges(
        graph,
        pos,
        arrows=True,
        arrowstyle="->",
        arrowsize=20,
        width=2,
    )

    nx.draw_networkx_labels(
        graph,
        pos,
        font_size=9,
        font_weight="bold",
    )

    edge_labels = {
        (source, target): f"{edge_data.get('response_time', 'unknown')} ms"
        for source, target, edge_data in graph.edges(data=True)
    }

    nx.draw_networkx_edge_labels(
        graph,
        pos,
        edge_labels=edge_labels,
        font_size=7,
    )

    plt.title(
        "QOTD Runtime System Dependency Graph from Kiali",
        fontsize=16,
    )
    plt.axis("off")
    plt.tight_layout()

    plt.savefig("sdg_graph.png", dpi=300)
    plt.show()


def main():
    print("Fetching live graph from Kiali...")

    kiali_data = fetch_kiali_graph()

    with open("latest_kiali_graph.json", "w") as file:
        json.dump(kiali_data, file, indent=2)

    graph = build_dependency_graph(kiali_data)

    print("\nNodes:")
    print(sorted(graph.nodes()))

    print("\nEdges:")
    print(list(graph.edges()))

    if graph.number_of_nodes() == 0:
        print(
            "\nNo workload nodes were returned by Kiali. "
            "Ensure there is recent in-mesh QOTD traffic."
        )
        return

    draw_graph(graph)


if __name__ == "__main__":
    main()
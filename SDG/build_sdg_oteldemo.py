import json
import sys
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

import networkx as nx
import matplotlib.pyplot as plt


KIALI_GRAPH_URL = (
    "http://localhost:20001/kiali/api/namespaces/graph"
    "?namespaces=otel-demo"
)

NAMESPACE = "otel-demo"


# These services are observability/control-plane infrastructure.
# They are real traffic, but they should not participate in the RCA SDG.
EXCLUDED_WORKLOADS = {
    "unknown",
    "prometheus",
    "grafana",
    "jaeger",
    "otel-collector-agent",
    "opamp-server",
    "mcp",
    "telemetry-docs",
}


def fetch_kiali_graph():
    print(f"Calling Kiali URL: {KIALI_GRAPH_URL}")

    try:
        with urlopen(KIALI_GRAPH_URL, timeout=30) as response:
            raw_response = response.read().decode("utf-8")

        return json.loads(raw_response)

    except HTTPError as err:
        print(f"Kiali returned HTTP {err.code}: {err.reason}")
        print(err.read().decode("utf-8", errors="replace"))
        sys.exit(1)

    except URLError as err:
        print(f"Could not reach Kiali: {err.reason}")
        print(
            "\nEnsure this is running:\n"
            "kubectl port-forward -n istio-system svc/kiali 20001:20001"
        )
        sys.exit(1)

    except json.JSONDecodeError as err:
        print("Kiali returned invalid JSON.")
        print(err)
        sys.exit(1)


def should_include_workload(workload):
    if not workload:
        return False

    if workload in EXCLUDED_WORKLOADS:
        return False

    return True


def build_dependency_graph(data):
    graph = nx.DiGraph()
    id_to_workload = {}

    # -------------------------
    # Nodes
    # -------------------------
    for node in data.get("elements", {}).get("nodes", []):
        node_data = node.get("data", {})

        node_id = node_data.get("id")
        workload = node_data.get("workload")

        if not node_id:
            continue

        if not should_include_workload(workload):
            continue

        id_to_workload[node_id] = workload
        graph.add_node(workload)

    # -------------------------
    # Edges
    # -------------------------
    for edge in data.get("elements", {}).get("edges", []):
        edge_data = edge.get("data", {})

        source = id_to_workload.get(edge_data.get("source"))
        target = id_to_workload.get(edge_data.get("target"))

        if not source or not target:
            continue

        # Self-loops don't help our service-level RCA graph.
        if source == target:
            continue

        response_time = edge_data.get("responseTime")

        graph.add_edge(
            source,
            target,
            response_time=response_time,
            health_status=edge_data.get("healthStatus", "unknown"),
        )

    # Remove isolated nodes.
    isolates = list(nx.isolates(graph))
    graph.remove_nodes_from(isolates)

    return graph


def calculate_layers(graph):
    """
    Create an approximate request-flow layout.

    Start from frontend-proxy when available and put dependencies
    progressively further to the right.
    """

    preferred_roots = [
        "frontend-proxy",
        "frontend",
    ]

    root = None

    for candidate in preferred_roots:
        if candidate in graph:
            root = candidate
            break

    if root is None:
        # Fall back to a node with no incoming edges.
        roots = [
            node
            for node in graph.nodes()
            if graph.in_degree(node) == 0
        ]

        if roots:
            root = roots[0]
        else:
            root = next(iter(graph.nodes()))

    distances = nx.single_source_shortest_path_length(graph, root)

    layers = {}

    for node in graph.nodes():
        if node in distances:
            layers[node] = distances[node]
        else:
            # Put disconnected/unreachable components at the end.
            layers[node] = max(distances.values(), default=0) + 1

    return layers


def hierarchical_positions(graph):
    layers = calculate_layers(graph)

    layer_to_nodes = {}

    for node, layer in layers.items():
        layer_to_nodes.setdefault(layer, []).append(node)

    pos = {}

    x_spacing = 4
    y_spacing = 2

    for layer, nodes in sorted(layer_to_nodes.items()):
        nodes = sorted(nodes)

        count = len(nodes)

        for index, node in enumerate(nodes):
            x = layer * x_spacing

            # Center each column vertically.
            y = (
                (index - (count - 1) / 2)
                * y_spacing
            )

            pos[node] = (x, y)

    return pos


def parse_response_time(value):
    """
    Return an integer latency when Kiali provides one.
    Otherwise return None.
    """

    if value is None:
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def draw_graph(graph):
    if graph.number_of_nodes() == 0:
        print("No application dependency nodes found.")
        return

    pos = hierarchical_positions(graph)

    plt.figure(figsize=(22, 12))

    # -------------------------
    # Nodes
    # -------------------------
    nx.draw_networkx_nodes(
        graph,
        pos,
        node_size=3200,
        node_color="lightblue",
        edgecolors="black",
        linewidths=1,
    )

    # -------------------------
    # Edges
    # -------------------------
    nx.draw_networkx_edges(
        graph,
        pos,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=18,
        width=1.5,
        alpha=0.65,
        min_source_margin=25,
        min_target_margin=25,
        connectionstyle="arc3,rad=0.05",
    )

    # -------------------------
    # Node labels
    # -------------------------
    nx.draw_networkx_labels(
        graph,
        pos,
        font_size=9,
        font_weight="bold",
    )

    # -------------------------
    # Only show interesting latency labels
    #
    # Do NOT label every edge.
    # -------------------------
    edge_labels = {}

    for source, target, data in graph.edges(data=True):
        latency = parse_response_time(
            data.get("response_time")
        )

        # Only label noticeably slow dependencies.
        if latency is not None and latency >= 100:
            edge_labels[(source, target)] = f"{latency} ms"

    nx.draw_networkx_edge_labels(
        graph,
        pos,
        edge_labels=edge_labels,
        font_size=7,
        rotate=False,
        bbox={
            "alpha": 0.7,
            "pad": 0.2,
        },
    )

    plt.title(
        "OpenTelemetry Demo Runtime Service Dependency Graph",
        fontsize=18,
        pad=20,
    )

    plt.axis("off")
    plt.tight_layout()

    plt.savefig(
        "sdg_graph.png",
        dpi=300,
        bbox_inches="tight",
    )

    plt.show()


def print_graph_summary(graph):
    print("\n==============================")
    print("Application SDG")
    print("==============================")

    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")

    print("\nServices:")
    for node in sorted(graph.nodes()):
        print(f"  - {node}")

    print("\nDependencies:")

    for source, target in sorted(graph.edges()):
        print(f"  {source} -> {target}")


def save_graph(graph):
    data = {
        "nodes": sorted(graph.nodes()),
        "edges": [],
    }

    for source, target, attributes in graph.edges(data=True):
        data["edges"].append(
            {
                "source": source,
                "target": target,
                "response_time": attributes.get(
                    "response_time"
                ),
                "health_status": attributes.get(
                    "health_status"
                ),
            }
        )

    with open("sdg.json", "w") as file:
        json.dump(data, file, indent=2)


def main():
    print("Fetching live graph from Kiali...")

    kiali_data = fetch_kiali_graph()

    # Preserve raw Kiali response.
    with open("latest_kiali_graph.json", "w") as file:
        json.dump(kiali_data, file, indent=2)

    graph = build_dependency_graph(kiali_data)

    print_graph_summary(graph)

    if graph.number_of_nodes() == 0:
        print(
            "\nNo workload nodes returned. "
            "Make sure recent traffic exists."
        )
        return

    save_graph(graph)
    draw_graph(graph)


if __name__ == "__main__":
    main()
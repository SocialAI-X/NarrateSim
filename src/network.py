import networkx as nx
import numpy as np
from typing import Dict, List, Set


def create_ba_network(n: int = 100, m: int = 3, seed: int = 42) -> nx.Graph:
    """Create a Barabási-Albert scale-free network."""
    return nx.barabasi_albert_graph(n, m, seed=seed)


def get_neighbors(graph: nx.Graph, node_id: int) -> List[int]:
    """Get all neighbors of a node."""
    return list(graph.neighbors(node_id))


def get_top_degree_nodes(graph: nx.Graph, k: int = 3) -> List[int]:
    """Return top-k nodes by degree centrality (for malicious agent placement)."""
    degree_centrality = nx.degree_centrality(graph)
    sorted_nodes = sorted(degree_centrality, key=degree_centrality.get, reverse=True)
    return sorted_nodes[:k]


def get_network_stats(graph: nx.Graph) -> Dict:
    """Compute basic network statistics."""
    degrees = [d for _, d in graph.degree()]
    return {
        "n_nodes": graph.number_of_nodes(),
        "n_edges": graph.number_of_edges(),
        "avg_degree": np.mean(degrees),
        "max_degree": max(degrees),
        "min_degree": min(degrees),
        "clustering_coefficient": nx.average_clustering(graph),
    }

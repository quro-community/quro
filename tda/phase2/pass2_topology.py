"""
Pass 2: Topology Inference

Computes topological properties from distilled features.
"""

from typing import Dict, Set
from .pass1_distill import (
    SparseAdjacencyMatrix,
    SymbolFrequencyMap,
    TauSurvivalTable,
    EdgeTypeDistribution,
)


class TopologyInferenceEngine:
    """Pass 2: Infer topological properties."""

    def __init__(
        self,
        adjacency: SparseAdjacencyMatrix,
        frequency: SymbolFrequencyMap,
        tau_survival: TauSurvivalTable,
        edge_types: EdgeTypeDistribution,
    ):
        self.adjacency = adjacency
        self.frequency = frequency
        self.tau_survival = tau_survival
        self.edge_types = edge_types

        # Computed properties
        self.centrality: Dict[str, float] = {}
        self.betweenness: Dict[str, float] = {}
        self.clustering: Dict[str, float] = {}
        self.roles: Dict[str, str] = {}
        self.role_confidence: Dict[str, float] = {}

    def infer(self) -> None:
        """Compute all topological properties."""
        print("[Phase-2 Pass-2] Computing topology...")

        all_nodes = self.adjacency.all_nodes()

        # Compute centrality for all nodes
        for node in all_nodes:
            self.centrality[node] = self._compute_centrality(node)

        # Normalize centrality to [0,1]
        max_centrality = max(self.centrality.values()) if self.centrality else 1.0
        if max_centrality > 0:
            self.centrality = {k: v / max_centrality for k, v in self.centrality.items()}

        # Compute betweenness (simplified)
        for node in all_nodes:
            self.betweenness[node] = self._compute_betweenness(node)

        # Normalize betweenness
        max_betweenness = max(self.betweenness.values()) if self.betweenness else 1.0
        if max_betweenness > 0:
            self.betweenness = {k: v / max_betweenness for k, v in self.betweenness.items()}

        # Compute clustering coefficient
        for node in all_nodes:
            self.clustering[node] = self._compute_clustering(node)

        # Infer roles
        for node in all_nodes:
            role, confidence = self._infer_role(node)
            self.roles[node] = role
            self.role_confidence[node] = confidence

        print(f"[Phase-2 Pass-2] Computed topology for {len(all_nodes)} nodes")

    def _compute_centrality(self, node: str) -> float:
        """Compute weighted degree centrality."""
        return self.adjacency.get_weighted_out_degree(node)

    def _compute_betweenness(self, node: str) -> float:
        """Compute simplified betweenness centrality.

        True betweenness requires all-pairs shortest paths (expensive).
        We use a proxy: (in_degree * out_degree) / total_degree
        High values indicate bridge-like behavior.
        """
        out_neighbors = self.adjacency.get_neighbors(node)
        in_neighbors = self.adjacency.get_in_neighbors(node)

        out_degree = len(out_neighbors)
        in_degree = len(in_neighbors)
        total_degree = out_degree + in_degree

        if total_degree == 0:
            return 0.0

        # Bridge score: high when both in and out are non-zero
        return (in_degree * out_degree) / total_degree

    def _compute_clustering(self, node: str) -> float:
        """Compute clustering coefficient.

        Measures how connected a node's neighbors are to each other.
        """
        neighbors = set(self.adjacency.get_neighbors(node).keys())

        if len(neighbors) < 2:
            return 0.0

        # Count edges between neighbors
        edges_between_neighbors = 0
        for n1 in neighbors:
            n1_neighbors = set(self.adjacency.get_neighbors(n1).keys())
            edges_between_neighbors += len(neighbors & n1_neighbors)

        # Max possible edges between k neighbors: k * (k - 1)
        max_edges = len(neighbors) * (len(neighbors) - 1)

        return edges_between_neighbors / max_edges if max_edges > 0 else 0.0

    def _infer_role(self, node: str) -> tuple[str, float]:
        """Infer role: hub/bridge/sink/leaf.

        Returns (role, confidence).
        """
        out_degree = self.adjacency.get_out_degree(node)
        in_degree = len(self.adjacency.get_in_neighbors(node))
        centrality = self.centrality.get(node, 0.0)
        betweenness = self.betweenness.get(node, 0.0)
        clustering = self.clustering.get(node, 0.0)

        # Role detection heuristics
        scores = {
            "hub": 0.0,
            "bridge": 0.0,
            "sink": 0.0,
            "leaf": 0.0,
        }

        # Hub: high out-degree, high centrality, low clustering
        if out_degree > 10:
            scores["hub"] += 0.4
        if centrality > 0.7:
            scores["hub"] += 0.3
        if clustering < 0.3:
            scores["hub"] += 0.3

        # Bridge: high betweenness, balanced in/out
        if betweenness > 0.5:
            scores["bridge"] += 0.5
        if in_degree > 0 and out_degree > 0:
            balance = min(in_degree, out_degree) / max(in_degree, out_degree)
            scores["bridge"] += 0.5 * balance

        # Sink: high in-degree, low out-degree
        if in_degree > 5 and out_degree < 3:
            scores["sink"] += 0.6
        if in_degree > out_degree * 2:
            scores["sink"] += 0.4

        # Leaf: low degree overall
        total_degree = in_degree + out_degree
        if total_degree <= 2:
            scores["leaf"] += 0.7
        if out_degree == 0:
            scores["leaf"] += 0.3

        # Select role with highest score
        role = max(scores.items(), key=lambda x: x[1])
        return role[0], role[1]

    def get_statistics(self) -> Dict:
        """Get topology statistics."""
        role_counts = {}
        for role in self.roles.values():
            role_counts[role] = role_counts.get(role, 0) + 1

        return {
            "role_distribution": role_counts,
            "avg_centrality": sum(self.centrality.values()) / len(self.centrality) if self.centrality else 0,
            "avg_betweenness": sum(self.betweenness.values()) / len(self.betweenness) if self.betweenness else 0,
            "avg_clustering": sum(self.clustering.values()) / len(self.clustering) if self.clustering else 0,
        }

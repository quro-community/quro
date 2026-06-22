"""Graph Transformation Passes

@module quro.core.cqe.transforms
@intent Implement graph transformations (Query Rewriting Phase) without modifying Kernel.
"""

import math
from typing import Iterable, Tuple, Protocol, Any
from core.cqe.types import GraphProtocol


class GraphTransform:
    """Base class for graph transformations."""

    @staticmethod
    def transform(graph: GraphProtocol) -> GraphProtocol:
        """Apply transformation and return a new GraphProtocol view."""
        return graph


class HubNormalizer(GraphTransform):
    """
    Applies Hub Normalization via Entropy Suppression.

    Addresses the jittering sensitivity issue by utilizing an offset
    and a min_degree threshold.

    Dynamically wraps a GraphProtocol so the CQEKernel continues
    pure Max-Product execution on mathematically stable weights.
    """

    class _HubNormalizedGraph(GraphProtocol):
        def __init__(self, base: GraphProtocol, min_degree: int = 10, offset: float = 1.0, use_tags: bool = True):
            self.base = base
            self.min_degree = min_degree
            self.offset = offset
            self.use_tags = use_tags

        def neighbors(self, node: str) -> Iterable[Tuple[str, float]]:
            out_degree = self.base.out_degree(node) if hasattr(self.base, "out_degree") else 0
            penalty = 1.0

            # Check if node has high_fanout tag (from enrichers)
            is_hub = False
            if self.use_tags and hasattr(self.base, "edges"):
                # Get node metadata to check for high_fanout tag
                # For now, use degree-based heuristic + category check
                if node.startswith("cat::") and out_degree > self.min_degree:
                    is_hub = True
                elif node.startswith("sym::") and out_degree > 50:
                    # Symbol nodes with >50 edges are marked as hubs by enricher
                    is_hub = True

            if is_hub:
                # Math offset prevents severe jittering at low degree values
                penalty = 1.0 / math.log10(out_degree + self.offset)

            for v, weight in self.base.neighbors(node):
                # Adjust weight dynamically but statically from the Kernel's perspective
                yield v, weight * penalty

        def edges(self, node: str) -> Iterable[Any]:
            if hasattr(self.base, "edges"):
                return self.base.edges(node)
            return []

        def out_degree(self, node: str) -> int:
            if hasattr(self.base, "out_degree"):
                return self.base.out_degree(node)
            return 0

    @staticmethod
    def transform(graph: GraphProtocol, min_degree: int = 10, offset: float = 1.0, use_tags: bool = True) -> GraphProtocol:
        return HubNormalizer._HubNormalizedGraph(graph, min_degree, offset, use_tags)


class TopKPruner(GraphTransform):
    """
    Static Top-K Pruning.

    Enforces graph topological limits statically without state machines.
    If a node (like a Hub) has too many outgoing edges, we only keep the top K
    edges by weight. This prevents infinite unrolling and keeps Kernel pure.
    """

    class _TopKPrunedGraph(GraphProtocol):
        def __init__(self, base: GraphProtocol, max_edges: int = 200):
            self.base = base
            self.max_edges = max_edges

        def neighbors(self, node: str) -> Iterable[Tuple[str, float]]:
            # Retrieve all neighbors
            neighbors = list(self.base.neighbors(node))
            if len(neighbors) > self.max_edges:
                # Sort by weight descending to keep the strongest edges
                neighbors.sort(key=lambda x: x[1], reverse=True)
                neighbors = neighbors[:self.max_edges]
            
            for v, weight in neighbors:
                yield v, weight

        def edges(self, node: str) -> Iterable[Any]:
            return self.base.edges(node) if hasattr(self.base, "edges") else []

        def out_degree(self, node: str) -> int:
            deg = self.base.out_degree(node) if hasattr(self.base, "out_degree") else 0
            return min(self.max_edges, deg)

    @staticmethod
    def transform(graph: GraphProtocol, max_edges: int = 200) -> GraphProtocol:
        return TopKPruner._TopKPrunedGraph(graph, max_edges)
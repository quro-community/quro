"""CQE Observability

@module quro.pipeline.cqe.observability
@intent Path tracing, metrics collection, and debugging for CQE queries
"""

from typing import List, Dict, Optional
from core.cqe.types import CQEResult


class CQEObservability:
    """CQE Observability - Path tracing and metrics.

    Responsible for path tracing, metrics collection, and debugging.
    Does NOT mutate the graph or the result.

    Pure functions:
    - trace_path: Reconstruct path to target node
    - compute_metrics: Calculate query health metrics
    """

    @staticmethod
    def trace_path(result: CQEResult, target_node: str) -> List[str]:
        """Reconstruct the exact path taken to reach the target_node.

        This provides the mathematical proof of why a node was recalled.

        Args:
            result: CQE query result
            target_node: Target node to trace path to

        Returns:
            List of node IDs from start to target (empty if unreachable)
        """
        if target_node not in result.max_weights:
            return []

        path = []
        current: Optional[str] = target_node
        while current is not None:
            path.append(current)
            current = result.predecessors.get(current)

        return path[::-1]  # Reverse to get start -> target

    @staticmethod
    def compute_metrics(result: CQEResult) -> Dict[str, float]:
        """Compute health metrics for a single query execution.

        Args:
            result: CQE query result

        Returns:
            Dict with metrics:
            - subgraph_size: Number of nodes reached
            - max_depth: Maximum path depth
            - average_weight: Average weight of reached nodes
        """
        subgraph_size = len(result.max_weights)

        # Calculate max depth
        max_depth = 0
        for node in result.max_weights:
            depth = 0
            curr = node
            while result.predecessors.get(curr) is not None:
                depth += 1
                curr = result.predecessors[curr]
            if depth > max_depth:
                max_depth = depth

        return {
            "subgraph_size": subgraph_size,
            "max_depth": max_depth,
            "average_weight": (
                sum(result.max_weights.values()) / subgraph_size
                if subgraph_size > 0
                else 0.0
            ),
        }

    @staticmethod
    def get_top_k(result: CQEResult, k: int = 10) -> List[tuple[str, float]]:
        """Get top-k nodes by weight.

        Args:
            result: CQE query result
            k: Number of top nodes to return

        Returns:
            List of (node_id, weight) tuples sorted by weight descending
        """
        sorted_nodes = sorted(
            result.max_weights.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_nodes[:k]

    @staticmethod
    def get_nodes_at_depth(result: CQEResult, depth: int) -> List[str]:
        """Get all nodes at a specific depth.

        Args:
            result: CQE query result
            depth: Target depth (0 = start node)

        Returns:
            List of node IDs at the specified depth
        """
        nodes_at_depth = []
        for node in result.max_weights:
            node_depth = 0
            curr = node
            while result.predecessors.get(curr) is not None:
                node_depth += 1
                curr = result.predecessors[curr]
            if node_depth == depth:
                nodes_at_depth.append(node)
        return nodes_at_depth

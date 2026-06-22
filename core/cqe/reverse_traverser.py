"""Reverse Traverser — Gravity-Constrained Reverse BFS

@module quro.core.cqe.reverse_traverser
@intent Dual of ForwardTraverser. Traverses incoming edges (reverse neighbors)
       with gravity constraints for sink node escape.

       Key constraints:
       - Min gravity filter: only traverse high-gravity nodes (≥0.7)
       - Top-k selection: limit to 5-10 incoming edges per node
       - Escape probability: score = gravity * mi_weight * (1 - noise_ratio)

       Duality property: Mirrors ForwardTraverser structure exactly.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from adapters.graph.protocol import GraphAdapter
from core.cqe.tda_bridge import TDABridge
from core.cqe.traversal_modes import compute_escape_probability

logger = logging.getLogger(__name__)


# Reverse traversal constraints
MIN_GRAVITY = 0.7      # Only traverse high-gravity nodes
MAX_INCOMING = 10      # Top-k limit for incoming edges
DEFAULT_NOISE = 0.1    # Default noise ratio if not available


@dataclass(frozen=True)
class ReverseTraversalResult:
    """Result of reverse traversal from a sink node.

    Attributes:
        start_node: Starting sink node ID
        visited_nodes: Set of visited node IDs
        paths: Dict mapping node_id → (distance, escape_probability, path)
        top_escapes: Top-k escape routes ranked by escape probability
    """
    start_node: str
    visited_nodes: Set[str]
    paths: Dict[str, Tuple[int, float, List[str]]]
    top_escapes: List[Tuple[str, float, List[str]]]


class ReverseTraverser:
    """Reverse BFS traverser with gravity constraints.

    Dual of ForwardTraverser — traverses incoming edges instead of outgoing.
    Used for sink node escape when forward traversal returns empty results.

    Invariant: Only traverses high-gravity nodes (gravity ≥ MIN_GRAVITY).
    """

    def __init__(
        self,
        graph: GraphAdapter,
        tda_bridge: TDABridge,
        mi_scores: Dict[str, float],
        min_gravity: float = MIN_GRAVITY,
        max_incoming: int = MAX_INCOMING,
    ):
        """Initialize reverse traverser.

        Args:
            graph: Graph adapter (must support reverse_neighbors)
            tda_bridge: TDA bridge for gravity scores
            mi_scores: MI scores for each node
            min_gravity: Minimum gravity threshold (default 0.7)
            max_incoming: Max incoming edges per node (default 10)
        """
        self.graph = graph
        self.tda_bridge = tda_bridge
        self.mi_scores = mi_scores
        self.min_gravity = min_gravity
        self.max_incoming = max_incoming

    def traverse(
        self,
        start_node: str,
        max_depth: int = 3,
        top_k: int = 5,
    ) -> ReverseTraversalResult:
        """Traverse reverse (incoming edges) from sink node.

        BFS traversal following incoming edges, constrained by gravity.
        Returns top-k escape routes ranked by escape probability.

        Args:
            start_node: Starting sink node ID
            max_depth: Maximum traversal depth (default 3)
            top_k: Number of top escape routes to return (default 5)

        Returns:
            ReverseTraversalResult with visited nodes and escape routes
        """
        logger.info(
            "Starting reverse traversal from %s (max_depth=%d, top_k=%d)",
            start_node, max_depth, top_k,
        )

        # BFS state
        visited: Set[str] = set()
        queue: List[Tuple[str, int, List[str]]] = [(start_node, 0, [start_node])]
        paths: Dict[str, Tuple[int, float, List[str]]] = {}

        # BFS loop
        while queue:
            current_node, depth, path = queue.pop(0)

            if current_node in visited:
                continue

            visited.add(current_node)

            # Stop at max depth
            if depth >= max_depth:
                continue

            # Get gravity score
            gravity = self.tda_bridge.get_gravity_score(current_node)

            # Skip low-gravity nodes (not stable enough for escape)
            if gravity < self.min_gravity:
                logger.debug(
                    "Skipping %s (gravity=%.2f < %.2f)",
                    current_node, gravity, self.min_gravity,
                )
                continue

            # Get MI score
            mi_weight = self.mi_scores.get(current_node, 0.5)

            # Compute escape probability
            noise_ratio = DEFAULT_NOISE  # TODO: Get from query history
            escape_prob = compute_escape_probability(gravity, mi_weight, noise_ratio)

            # Store path with escape probability
            paths[current_node] = (depth, escape_prob, path)

            # Get reverse neighbors (incoming edges)
            reverse_neighbors = list(self.graph.reverse_neighbors(current_node))

            # Apply top-k selection
            if len(reverse_neighbors) > self.max_incoming:
                # Sort by weight (descending) and take top-k
                reverse_neighbors.sort(key=lambda x: x[1], reverse=True)
                reverse_neighbors = reverse_neighbors[:self.max_incoming]
                logger.debug(
                    "Limited incoming edges for %s: %d → %d",
                    current_node, len(reverse_neighbors), self.max_incoming,
                )

            # Enqueue reverse neighbors
            for neighbor_id, edge_weight in reverse_neighbors:
                if neighbor_id not in visited:
                    new_path = path + [neighbor_id]
                    queue.append((neighbor_id, depth + 1, new_path))

        # Rank escape routes by escape probability
        escape_routes = [
            (node_id, escape_prob, path)
            for node_id, (depth, escape_prob, path) in paths.items()
            if node_id != start_node  # Exclude start node
        ]
        escape_routes.sort(key=lambda x: x[1], reverse=True)
        top_escapes = escape_routes[:top_k]

        logger.info(
            "Reverse traversal complete: visited %d nodes, found %d escape routes",
            len(visited), len(escape_routes),
        )

        return ReverseTraversalResult(
            start_node=start_node,
            visited_nodes=visited,
            paths=paths,
            top_escapes=top_escapes,
        )

    def get_escape_candidates(
        self,
        start_node: str,
        min_escape_prob: float = 0.3,
    ) -> List[Tuple[str, float]]:
        """Get escape candidates from sink node.

        Quick query for nodes reachable via reverse traversal
        with escape probability above threshold.

        Args:
            start_node: Starting sink node ID
            min_escape_prob: Minimum escape probability (default 0.3)

        Returns:
            List of (node_id, escape_probability) tuples
        """
        result = self.traverse(start_node, max_depth=2, top_k=10)

        candidates = [
            (node_id, escape_prob)
            for node_id, escape_prob, _ in result.top_escapes
            if escape_prob >= min_escape_prob
        ]

        return candidates

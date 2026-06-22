"""Graph Adapter Protocol

@module quro.adapters.graph.protocol
@intent Define protocol for graph data access (CQE traversal)
"""

from typing import Protocol, Iterable, Tuple
from adapters.graph.types import GraphNode, GraphEdge


class GraphAdapter(Protocol):
    """Graph data adapter protocol.

    Provides read-only access to graph structure for CQE traversal.
    Implementations handle I/O (SQLite, PostgreSQL, in-memory, etc.).

    Invariant: Read-only, no mutations.
    """

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get node by ID.

        Args:
            node_id: Atom ID

        Returns:
            GraphNode or None if not found
        """
        ...

    def neighbors(self, node_id: str) -> Iterable[Tuple[str, float]]:
        """Get neighbors for CQE kernel traversal.

        This is the primary method used by CQE kernel.
        Returns (neighbor_id, edge_weight) tuples.

        Args:
            node_id: Source atom ID

        Returns:
            Iterable of (neighbor_id, weight) tuples
        """
        ...

    def edges(self, node_id: str) -> Iterable[GraphEdge]:
        """Get outgoing edges from node.

        Args:
            node_id: Source atom ID

        Returns:
            Iterable of GraphEdge objects
        """
        ...

    def out_degree(self, node_id: str) -> int:
        """Get out-degree of node.

        Args:
            node_id: Atom ID

        Returns:
            Number of outgoing edges
        """
        ...

    def tags(self, node_id: str) -> Tuple[str, ...]:
        """Get tags of node.

        Args:
            node_id: Atom ID

        Returns:
            Tuple of tag strings
        """
        ...

    def reverse_neighbors(self, node_id: str) -> Iterable[Tuple[str, float]]:
        """Get reverse neighbors (incoming edges) for reverse traversal.

        This is the dual of neighbors() — returns nodes that point TO this node.
        Used by ReverseTraverser for sink node escape.

        Args:
            node_id: Target atom ID

        Returns:
            Iterable of (source_id, weight) tuples
        """
        ...

    def in_degree(self, node_id: str) -> int:
        """Get in-degree of node (number of incoming edges).

        Args:
            node_id: Atom ID

        Returns:
            Number of incoming edges
        """
        ...

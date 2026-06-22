"""Index Builder v3 - Registry Adapter Protocol

@module quro.index_builder.adapters.protocol
@intent Define interface for registry adapters
@constraint Protocol only - no implementation
"""

from typing import Protocol, List, Optional
from index_builder.types import GraphNode, GraphEdge


class RegistryAdapter(Protocol):
    """Protocol for registry adapters.

    Adapters handle persistence of graph nodes and edges.
    Implementations: memory, SQLite, PostgreSQL, etc.
    """

    def save_node(self, node: GraphNode) -> None:
        """Save a graph node.

        Args:
            node: Graph node to save
        """
        ...

    def save_edge(self, edge: GraphEdge) -> None:
        """Save a graph edge.

        Args:
            edge: Graph edge to save
        """
        ...

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID.

        Args:
            node_id: Node ID to query

        Returns:
            GraphNode or None if not found
        """
        ...

    def get_edges_from(self, node_id: str) -> List[GraphEdge]:
        """Get all edges from a node.

        Args:
            node_id: Source node ID

        Returns:
            List of edges
        """
        ...

    def node_exists(self, node_id: str) -> bool:
        """Check if node exists.

        Args:
            node_id: Node ID to check

        Returns:
            True if node exists
        """
        ...

    def clear(self) -> None:
        """Clear all stored data."""
        ...

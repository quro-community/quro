"""DuckDB Graph Adapter

@module quro.adapters.graph.duckdb
@intent Implement GraphAdapter protocol against DuckDB tables
@role Extension (I/O-bound, no computation)
"""

from pathlib import Path
from typing import Iterable, Tuple, Optional

import duckdb

from adapters.graph.types import GraphNode, GraphEdge

__all__ = ["DuckDBGraphAdapter"]


class DuckDBGraphAdapter:
    """DuckDB graph adapter for CQE traversal.

    Implements GraphAdapter protocol by querying quro_tda.duckdb tables.
    Replaces SQLiteGraphAdapter for TDA-enriched graph access.

    Invariant: Read-only. No caching (DuckDB has internal buffer pool).
    """

    def __init__(self, db_path: Path):
        """Initialize DuckDB graph adapter.

        Args:
            db_path: Path to quro_tda.duckdb
        """
        self.db_path = db_path
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def __enter__(self):
        """Open database connection."""
        self._conn = duckdb.connect(str(self.db_path))
        return self

    def __exit__(self, *args):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _ensure_connection(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            raise RuntimeError(
                "Database connection not open (use context manager)"
            )
        return self._conn

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get node by ID.

        Args:
            node_id: Atom ID

        Returns:
            GraphNode or None if not found
        """
        conn = self._ensure_connection()

        result = conn.execute(
            "SELECT id, type, tags FROM nodes WHERE id = ?",
            (node_id,),
        ).fetchone()

        if result is None:
            return None

        tags_value = result[2]
        if isinstance(tags_value, list):
            tags = tuple(tags_value)
        else:
            tags = ()

        return GraphNode(
            id=result[0],
            type=result[1],
            tags=tags,
        )

    def neighbors(self, node_id: str) -> Iterable[Tuple[str, float]]:
        """Get neighbors for CQE kernel traversal.

        Args:
            node_id: Source atom ID

        Returns:
            Iterable of (neighbor_id, weight) tuples
        """
        conn = self._ensure_connection()

        cursor = conn.execute(
            "SELECT to_id, weight FROM edges_weighted "
            "WHERE from_id = ? ORDER BY weight DESC",
            (node_id,),
        )

        for row in cursor.fetchall():
            yield (row[0], row[1])

    def edges(self, node_id: str) -> Iterable[GraphEdge]:
        """Get outgoing edges from node.

        Args:
            node_id: Source atom ID

        Returns:
            Iterable of GraphEdge objects
        """
        conn = self._ensure_connection()

        cursor = conn.execute(
            "SELECT to_id, kind, weight FROM edges_weighted "
            "WHERE from_id = ? ORDER BY weight DESC",
            (node_id,),
        )

        for row in cursor.fetchall():
            yield GraphEdge(
                src=node_id,
                dst=row[0],
                kind=row[1],
                weight=row[2],
            )

    def out_degree(self, node_id: str) -> int:
        """Get out-degree of node.

        Args:
            node_id: Atom ID

        Returns:
            Number of outgoing edges
        """
        conn = self._ensure_connection()

        result = conn.execute(
            "SELECT COUNT(*) FROM edges_weighted WHERE from_id = ?",
            (node_id,),
        ).fetchone()

        return result[0] if result else 0

    def tags(self, node_id: str) -> Tuple[str, ...]:
        """Get tags of node.

        Args:
            node_id: Atom ID

        Returns:
            Tuple of tag strings
        """
        node = self.get_node(node_id)
        return node.tags if node else ()

    def reverse_neighbors(self, node_id: str) -> Iterable[Tuple[str, float]]:
        """Get reverse neighbors (incoming edges).

        Args:
            node_id: Target atom ID

        Returns:
            Iterable of (source_id, weight) tuples
        """
        conn = self._ensure_connection()

        cursor = conn.execute(
            "SELECT from_id, weight FROM edges_weighted "
            "WHERE to_id = ? ORDER BY weight DESC",
            (node_id,),
        )

        for row in cursor.fetchall():
            yield (row[0], row[1])

    def in_degree(self, node_id: str) -> int:
        """Get in-degree of node.

        Args:
            node_id: Atom ID

        Returns:
            Number of incoming edges
        """
        conn = self._ensure_connection()

        result = conn.execute(
            "SELECT COUNT(*) FROM edges_weighted WHERE to_id = ?",
            (node_id,),
        ).fetchone()

        return result[0] if result else 0

"""SQLite Graph Adapter

@module quro.adapters.graph.sqlite
@intent Load CQE graph from SQLite index (cqe_index.db)
"""

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Tuple, Dict
from adapters.graph.types import GraphNode, GraphEdge


class SQLiteGraphAdapter:
    """SQLite graph adapter for CQE traversal.

    Loads graph data from cqe_index.db (atoms and morphisms tables).
    Implements GraphAdapter protocol.

    Invariant: Read-only, no mutations.
    """

    def __init__(self, db_path: Path):
        """Initialize SQLite graph adapter.

        Args:
            db_path: Path to cqe_index.db
        """
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._node_cache: Dict[str, GraphNode] = {}
        self._out_degree_cache: Dict[str, int] = {}
        self._in_degree_cache: Dict[str, int] = {}

    def __enter__(self):
        """Open database connection."""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, *args):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
        self._node_cache.clear()
        self._out_degree_cache.clear()
        self._in_degree_cache.clear()

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get node by ID.

        Args:
            node_id: Atom ID

        Returns:
            GraphNode or None if not found
        """
        # Check cache
        if node_id in self._node_cache:
            return self._node_cache[node_id]

        if not self._conn:
            raise RuntimeError("Database connection not open (use context manager)")

        cursor = self._conn.execute(
            "SELECT id, type, features_json FROM atoms WHERE id = ?",
            (node_id,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        # Parse tags from features_json
        tags = ()
        if row["features_json"]:
            try:
                features = json.loads(row["features_json"])
                if isinstance(features, list):
                    tags = tuple(features)
            except:
                pass

        node = GraphNode(
            id=row["id"],
            type=row["type"],
            tags=tags,
        )

        # Cache node
        self._node_cache[node_id] = node
        return node

    def neighbors(self, node_id: str) -> Iterable[Tuple[str, float]]:
        """Get neighbors for CQE kernel traversal.

        This is the primary method used by CQE kernel.
        Returns (neighbor_id, edge_weight) tuples.

        Args:
            node_id: Source atom ID

        Returns:
            Iterable of (neighbor_id, weight) tuples
        """
        if not self._conn:
            raise RuntimeError("Database connection not open (use context manager)")

        cursor = self._conn.execute(
            "SELECT to_id, weight FROM morphisms WHERE from_id = ? ORDER BY weight DESC",
            (node_id,)
        )

        for row in cursor:
            yield (row["to_id"], row["weight"])

    def edges(self, node_id: str) -> Iterable[GraphEdge]:
        """Get outgoing edges from node.

        Args:
            node_id: Source atom ID

        Returns:
            Iterable of GraphEdge objects
        """
        if not self._conn:
            raise RuntimeError("Database connection not open (use context manager)")

        cursor = self._conn.execute(
            "SELECT to_id, kind, weight FROM morphisms WHERE from_id = ? ORDER BY weight DESC",
            (node_id,)
        )

        for row in cursor:
            yield GraphEdge(
                src=node_id,
                dst=row["to_id"],
                kind=row["kind"],
                weight=row["weight"],
            )

    def out_degree(self, node_id: str) -> int:
        """Get out-degree of node.

        Args:
            node_id: Atom ID

        Returns:
            Number of outgoing edges
        """
        # Check cache
        if node_id in self._out_degree_cache:
            return self._out_degree_cache[node_id]

        if not self._conn:
            raise RuntimeError("Database connection not open (use context manager)")

        cursor = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM morphisms WHERE from_id = ?",
            (node_id,)
        )
        row = cursor.fetchone()
        degree = row["cnt"] if row else 0

        # Cache degree
        self._out_degree_cache[node_id] = degree
        return degree

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
        """Get reverse neighbors (incoming edges) for reverse traversal.

        This is the dual of neighbors() — returns nodes that point TO this node.
        Used by ReverseTraverser for sink node escape.

        Args:
            node_id: Target atom ID

        Returns:
            Iterable of (source_id, weight) tuples
        """
        if not self._conn:
            raise RuntimeError("Database connection not open (use context manager)")

        # Try incoming_edges table first (optimized for reverse traversal)
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='incoming_edges'"
        )
        has_incoming_edges = cursor.fetchone() is not None

        if has_incoming_edges:
            cursor = self._conn.execute(
                "SELECT from_id, weight FROM incoming_edges WHERE to_id = ? ORDER BY weight DESC",
                (node_id,)
            )
        else:
            # Fallback to morphisms table (backward compatibility)
            cursor = self._conn.execute(
                "SELECT from_id, weight FROM morphisms WHERE to_id = ? ORDER BY weight DESC",
                (node_id,)
            )

        for row in cursor:
            yield (row["from_id"], row["weight"])

    def in_degree(self, node_id: str) -> int:
        """Get in-degree of node (number of incoming edges).

        Args:
            node_id: Atom ID

        Returns:
            Number of incoming edges
        """
        # Check cache
        if node_id in self._in_degree_cache:
            return self._in_degree_cache[node_id]

        if not self._conn:
            raise RuntimeError("Database connection not open (use context manager)")

        # Try incoming_edges table first (optimized)
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='incoming_edges'"
        )
        has_incoming_edges = cursor.fetchone() is not None

        if has_incoming_edges:
            cursor = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM incoming_edges WHERE to_id = ?",
                (node_id,)
            )
        else:
            # Fallback to morphisms table
            cursor = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM morphisms WHERE to_id = ?",
                (node_id,)
            )

        row = cursor.fetchone()
        degree = row["cnt"] if row else 0

        # Cache degree
        self._in_degree_cache[node_id] = degree
        return degree


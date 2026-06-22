"""Index Builder v3 - SQLite Registry Adapter

@module quro.index_builder.adapters.sqlite
@intent SQLite persistent storage adapter
@constraint Uses SQLite for durable storage
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional
from index_builder.types import GraphNode, GraphEdge


class SQLiteRegistryAdapter:
    """SQLite registry adapter.

    Stores graph nodes and edges in SQLite database.
    Provides persistent storage across sessions.
    """

    def __init__(self, db_path: Path):
        """Initialize SQLite adapter.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Nodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                tags TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
        """)

        # Edges table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                src TEXT NOT NULL,
                dst TEXT NOT NULL,
                weight REAL NOT NULL,
                kind TEXT NOT NULL,
                FOREIGN KEY (src) REFERENCES nodes(id),
                FOREIGN KEY (dst) REFERENCES nodes(id)
            )
        """)

        # Aliases table (for duplicate symbol tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aliases (
                symbol_id TEXT NOT NULL,
                path TEXT NOT NULL,
                line INTEGER NOT NULL,
                kind TEXT NOT NULL,
                signature TEXT NOT NULL,
                FOREIGN KEY (symbol_id) REFERENCES nodes(id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_aliases_symbol ON aliases(symbol_id)")

        conn.commit()
        conn.close()

    def save_node(self, node: GraphNode) -> None:
        """Save a graph node.

        Args:
            node: Graph node to save
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if node already exists (for alias tracking)
        cursor.execute("SELECT id, metadata FROM nodes WHERE id = ?", (node.id,))
        existing = cursor.fetchone()

        if existing:
            # Track existing node as alias
            existing_metadata = json.loads(existing[1])
            cursor.execute("""
                INSERT INTO aliases (symbol_id, path, line, kind, signature)
                VALUES (?, ?, ?, ?, ?)
            """, (
                node.id,
                existing_metadata.get("file_path", ""),
                existing_metadata.get("line", 0),
                existing_metadata.get("kind", "unknown"),
                existing_metadata.get("signature", "")
            ))

        # Upsert node
        cursor.execute("""
            INSERT OR REPLACE INTO nodes (id, type, tags, metadata)
            VALUES (?, ?, ?, ?)
        """, (
            node.id,
            node.type,
            json.dumps(list(node.tags)),
            json.dumps(node.metadata)
        ))

        # Also add new node to aliases if it's a duplicate
        if existing:
            cursor.execute("""
                INSERT INTO aliases (symbol_id, path, line, kind, signature)
                VALUES (?, ?, ?, ?, ?)
            """, (
                node.id,
                node.metadata.get("file_path", ""),
                node.metadata.get("line", 0),
                node.metadata.get("kind", "unknown"),
                node.metadata.get("signature", "")
            ))

        conn.commit()
        conn.close()

    def save_edge(self, edge: GraphEdge) -> None:
        """Save a graph edge.

        Args:
            edge: Graph edge to save
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO edges (src, dst, weight, kind)
            VALUES (?, ?, ?, ?)
        """, (edge.src, edge.dst, edge.weight, edge.kind))

        conn.commit()
        conn.close()

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID.

        Args:
            node_id: Node ID to query

        Returns:
            GraphNode or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, type, tags, metadata
            FROM nodes
            WHERE id = ?
        """, (node_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return GraphNode(
            id=row[0],
            type=row[1],
            tags=set(json.loads(row[2])),
            metadata=json.loads(row[3])
        )

    def get_edges_from(self, node_id: str) -> List[GraphEdge]:
        """Get all edges from a node.

        Args:
            node_id: Source node ID

        Returns:
            List of edges
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT src, dst, weight, kind
            FROM edges
            WHERE src = ?
        """, (node_id,))

        rows = cursor.fetchall()
        conn.close()

        return [
            GraphEdge(src=row[0], dst=row[1], weight=row[2], kind=row[3])
            for row in rows
        ]

    def node_exists(self, node_id: str) -> bool:
        """Check if node exists.

        Args:
            node_id: Node ID to check

        Returns:
            True if node exists
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM nodes WHERE id = ? LIMIT 1", (node_id,))
        exists = cursor.fetchone() is not None

        conn.close()
        return exists

    def get_all_nodes(self) -> List[GraphNode]:
        """Get all nodes.

        Returns:
            List of all nodes
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, type, tags, metadata FROM nodes")
        rows = cursor.fetchall()
        conn.close()

        return [
            GraphNode(
                id=row[0],
                type=row[1],
                tags=set(json.loads(row[2])),
                metadata=json.loads(row[3])
            )
            for row in rows
        ]

    def get_all_edges(self) -> List[GraphEdge]:
        """Get all edges.

        Returns:
            List of all edges
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT src, dst, weight, kind FROM edges")
        rows = cursor.fetchall()
        conn.close()

        return [
            GraphEdge(src=row[0], dst=row[1], weight=row[2], kind=row[3])
            for row in rows
        ]

    def clear(self) -> None:
        """Clear all stored data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM edges")
        cursor.execute("DELETE FROM aliases")
        cursor.execute("DELETE FROM nodes")

        conn.commit()
        conn.close()

    def find_symbol_aliases(self, symbol_name: str) -> List[Dict[str, str]]:
        """Find all nodes with the same bare symbol name.

        Args:
            symbol_name: Symbol name to search (e.g., "cqe_query" or "sym::cqe_query")

        Returns:
            List of dicts with alias metadata: [{"path": ..., "line": ..., "kind": ...}]
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # First check aliases table
        cursor.execute("""
            SELECT path, line, kind, signature
            FROM aliases
            WHERE symbol_id = ?
        """, (symbol_name,))

        rows = cursor.fetchall()
        if rows:
            aliases = [
                {
                    "id": symbol_name,
                    "path": row[0],
                    "line": row[1],
                    "kind": row[2],
                    "signature": row[3]
                }
                for row in rows
            ]
            conn.close()
            return self._filter_true_aliases(symbol_name, aliases)

        # Fallback: search by bare name
        bare_name = symbol_name.replace("sym::", "").replace("cat::", "")

        cursor.execute("""
            SELECT id, metadata
            FROM nodes
            WHERE id LIKE ? OR id LIKE ?
        """, (f"%{bare_name}", f"%{bare_name}%"))

        rows = cursor.fetchall()
        conn.close()

        aliases = []
        for row in rows:
            node_id = row[0]
            node_bare = node_id.replace("sym::", "").replace("cat::", "")

            if node_bare == bare_name and node_id != symbol_name:
                metadata = json.loads(row[1])
                aliases.append({
                    "id": node_id,
                    "path": metadata.get("file_path", ""),
                    "line": metadata.get("line", 0),
                    "kind": metadata.get("kind", "unknown"),
                    "signature": metadata.get("signature", "")
                })

        return self._filter_true_aliases(symbol_name, aliases)

    def _filter_true_aliases(self, canonical_id: str, candidates: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Filter candidates to exclude noise (protocols, tests).

        Args:
            canonical_id: The canonical symbol ID
            candidates: List of candidate aliases

        Returns:
            Filtered list (excludes protocols and test files)
        """
        if not candidates:
            return []

        filtered = []
        for candidate in candidates:
            candidate_path = candidate.get("path", "")

            # Skip protocol definitions
            if "protocol.py" in candidate_path.lower():
                continue

            # Skip test files
            if "/tests/" in candidate_path or "/test_" in candidate_path:
                continue

            filtered.append(candidate)

        return filtered

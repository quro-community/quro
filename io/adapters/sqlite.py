"""
SQLite Graph Adapter - Implements GraphProtocol

@module quro.io.adapters.sqlite
@intent Adapt SQLite database to GraphProtocol
@constraint I/O operations allowed here (boundary layer)

This adapter:
1. Loads graph data from SQLite
2. Implements GraphProtocol for kernel consumption
3. Caches data for performance
4. Handles connection lifecycle
"""

import sqlite3
from pathlib import Path
from typing import Iterable, Tuple, Dict, List
from core.cqe.types import GraphProtocol


class SQLiteGraphAdapter:
    """
    SQLite implementation of GraphProtocol.

    Loads graph data from SQLite and provides pure data access.

    INVARIANT: neighbors() is pure after initialization
    - Data is loaded once and cached
    - No mutations after __init__
    - Same node → same neighbors
    """

    def __init__(self, db_path: Path | str):
        """
        Initialize adapter and load graph data.

        Args:
            db_path: Path to SQLite database

        Raises:
            FileNotFoundError: If database doesn't exist
            sqlite3.Error: If database is corrupted
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        # Load graph into memory (immutable after init)
        self._adjacency: Dict[str, List[Tuple[str, float]]] = {}
        self._load_graph()

    def _load_graph(self) -> None:
        """
        Load graph from SQLite into memory.

        Side effects: Reads from database
        Called once during __init__
        """
        conn = sqlite3.connect(str(self.db_path))

        try:
            # Optimize SQLite for read-only access
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory map
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache

            cursor = conn.cursor()

            # Load all morphisms (edges)
            cursor.execute("""
                SELECT from_id, to_id, weight
                FROM morphisms
                WHERE weight > 0
                ORDER BY from_id, weight DESC
            """)

            # Build adjacency list
            for from_id, to_id, weight in cursor.fetchall():
                if from_id not in self._adjacency:
                    self._adjacency[from_id] = []
                self._adjacency[from_id].append((to_id, weight))

        finally:
            conn.close()

    def neighbors(self, node: str) -> Iterable[Tuple[str, float]]:
        """
        Get neighbors of a node (GraphProtocol implementation).

        PURE FUNCTION after initialization:
        - No I/O (data is cached)
        - No mutations
        - Deterministic

        Args:
            node: Node ID

        Returns:
            Iterable of (neighbor_id, edge_weight) tuples
        """
        return self._adjacency.get(node, [])

    def get_stats(self) -> Dict[str, int]:
        """
        Get graph statistics.

        Returns:
            Dict with node_count, edge_count
        """
        edge_count = sum(len(neighbors) for neighbors in self._adjacency.values())
        return {
            "node_count": len(self._adjacency),
            "edge_count": edge_count,
        }


class SQLiteIndexLoader:
    """
    High-level loader for CQE index.

    Provides:
    - GraphProtocol adapter
    - Symbol table loading
    - Alias loading
    - Manifest loading
    """

    def __init__(self, index_path: Path | str):
        """
        Initialize loader.

        Args:
            index_path: Path to SQLite index file
        """
        self.index_path = Path(index_path)
        if not self.index_path.exists():
            raise FileNotFoundError(f"Index not found: {self.index_path}")

    def as_graph_protocol(self) -> GraphProtocol:
        """
        Get GraphProtocol implementation.

        Returns:
            SQLiteGraphAdapter implementing GraphProtocol
        """
        return SQLiteGraphAdapter(self.index_path)

    def get_symbol_table(self) -> List[str]:
        """
        Load symbol table (all valid atom IDs).

        Returns:
            List of atom IDs
        """
        conn = sqlite3.connect(str(self.index_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM atoms ORDER BY id")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_aliases(self) -> Dict[str, List[str]]:
        """
        Load alias mappings.

        Returns:
            Dict of {canonical: [alias1, alias2, ...]}
        """
        conn = sqlite3.connect(str(self.index_path))
        try:
            cursor = conn.cursor()

            # Check if aliases table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='aliases'
            """)
            if not cursor.fetchone():
                return {}

            cursor.execute("SELECT canonical, alias FROM aliases")

            aliases: Dict[str, List[str]] = {}
            for canonical, alias in cursor.fetchall():
                if canonical not in aliases:
                    aliases[canonical] = []
                aliases[canonical].append(alias)

            return aliases
        finally:
            conn.close()

    def get_manifest(self) -> Dict[str, any] | None:
        """
        Load graph manifest (metadata).

        Returns:
            Manifest dict or None if not found
        """
        conn = sqlite3.connect(str(self.index_path))
        try:
            cursor = conn.cursor()

            # Check if manifest table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='manifest'
            """)
            if not cursor.fetchone():
                return None

            cursor.execute("SELECT key, value FROM manifest")

            manifest = {}
            for key, value in cursor.fetchall():
                manifest[key] = value

            return manifest if manifest else None
        finally:
            conn.close()

    def get_index_stats(self) -> Dict[str, any]:
        """
        Get index statistics.

        Returns:
            Dict with atoms_count, morphisms_count, index_size_mb
        """
        conn = sqlite3.connect(str(self.index_path))
        try:
            cursor = conn.cursor()

            # Count atoms
            cursor.execute("SELECT COUNT(*) FROM atoms")
            atoms_count = cursor.fetchone()[0]

            # Count morphisms
            cursor.execute("SELECT COUNT(*) FROM morphisms")
            morphisms_count = cursor.fetchone()[0]

            # Get file size
            index_size_mb = self.index_path.stat().st_size / (1024 * 1024)

            return {
                "atoms_count": atoms_count,
                "morphisms_count": morphisms_count,
                "index_size_mb": round(index_size_mb, 2),
            }
        finally:
            conn.close()

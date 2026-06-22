"""
TDA Index Query Utility

Provides convenient access to TDA index database.
"""

import sqlite3
import json
from typing import List, Optional, Dict
from dataclasses import dataclass


@dataclass
class NodeMetadata:
    """Node metadata from TDA index."""

    symbol_id: str
    in_degree: int
    out_degree: int
    mass_tf: float
    mass_idf: float
    mass_hub_correction: float
    mass_cognitive: float
    calling_modules: int
    total_modules: int
    module_tags: List[str]
    created_at: str
    updated_at: str


class TDAIndexQuery:
    """Query interface for TDA index database."""

    def __init__(self, tda_db_path: str = ".quro_context/tda_index.db"):
        """Initialize query interface.

        Args:
            tda_db_path: Path to TDA index database
        """
        self.tda_db_path = tda_db_path
        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self):
        """Context manager entry."""
        self._conn = sqlite3.connect(self.tda_db_path)
        self._conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def get_metadata(self, symbol_id: str) -> Optional[NodeMetadata]:
        """Get metadata for a specific symbol.

        Args:
            symbol_id: Symbol ID (e.g., "sym::run_mvp_flow")

        Returns:
            NodeMetadata or None if not found
        """
        if not self._conn:
            raise RuntimeError("TDAIndexQuery must be used as context manager")

        cursor = self._conn.execute(
            "SELECT * FROM node_metadata WHERE symbol_id = ?",
            (symbol_id,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_metadata(row)

    def get_top_by_mass(self, limit: int = 10) -> List[NodeMetadata]:
        """Get top symbols by cognitive mass.

        Args:
            limit: Number of symbols to return

        Returns:
            List of NodeMetadata sorted by mass (descending)
        """
        if not self._conn:
            raise RuntimeError("TDAIndexQuery must be used as context manager")

        cursor = self._conn.execute(
            "SELECT * FROM node_metadata ORDER BY mass_cognitive DESC LIMIT ?",
            (limit,)
        )

        return [self._row_to_metadata(row) for row in cursor]

    def get_bottom_by_mass(self, limit: int = 10) -> List[NodeMetadata]:
        """Get bottom symbols by cognitive mass.

        Args:
            limit: Number of symbols to return

        Returns:
            List of NodeMetadata sorted by mass (ascending)
        """
        if not self._conn:
            raise RuntimeError("TDAIndexQuery must be used as context manager")

        cursor = self._conn.execute(
            "SELECT * FROM node_metadata ORDER BY mass_cognitive ASC LIMIT ?",
            (limit,)
        )

        return [self._row_to_metadata(row) for row in cursor]

    def get_by_mass_range(
        self,
        min_mass: float,
        max_mass: float,
        limit: Optional[int] = None
    ) -> List[NodeMetadata]:
        """Get symbols within a mass range.

        Args:
            min_mass: Minimum cognitive mass
            max_mass: Maximum cognitive mass
            limit: Optional limit on results

        Returns:
            List of NodeMetadata in mass range
        """
        if not self._conn:
            raise RuntimeError("TDAIndexQuery must be used as context manager")

        query = """
            SELECT * FROM node_metadata
            WHERE mass_cognitive BETWEEN ? AND ?
            ORDER BY mass_cognitive DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor = self._conn.execute(query, (min_mass, max_mass))

        return [self._row_to_metadata(row) for row in cursor]

    def get_hubs(self, min_out_degree: int = 50, limit: int = 10) -> List[NodeMetadata]:
        """Get hub symbols (high out-degree).

        Args:
            min_out_degree: Minimum out-degree threshold
            limit: Number of symbols to return

        Returns:
            List of NodeMetadata sorted by out-degree (descending)
        """
        if not self._conn:
            raise RuntimeError("TDAIndexQuery must be used as context manager")

        cursor = self._conn.execute("""
            SELECT * FROM node_metadata
            WHERE out_degree >= ?
            ORDER BY out_degree DESC
            LIMIT ?
        """, (min_out_degree, limit))

        return [self._row_to_metadata(row) for row in cursor]

    def get_sinks(self, max_out_degree: int = 0, limit: int = 10) -> List[NodeMetadata]:
        """Get sink symbols (low/zero out-degree).

        Args:
            max_out_degree: Maximum out-degree threshold
            limit: Number of symbols to return

        Returns:
            List of NodeMetadata sorted by in-degree (descending)
        """
        if not self._conn:
            raise RuntimeError("TDAIndexQuery must be used as context manager")

        cursor = self._conn.execute("""
            SELECT * FROM node_metadata
            WHERE out_degree <= ?
            ORDER BY in_degree DESC
            LIMIT ?
        """, (max_out_degree, limit))

        return [self._row_to_metadata(row) for row in cursor]

    def get_statistics(self) -> Dict[str, float]:
        """Get aggregate statistics.

        Returns:
            Dict with statistics (count, avg_mass, max_mass, etc.)
        """
        if not self._conn:
            raise RuntimeError("TDAIndexQuery must be used as context manager")

        cursor = self._conn.execute("""
            SELECT
                COUNT(*) as count,
                AVG(mass_cognitive) as avg_mass,
                MIN(mass_cognitive) as min_mass,
                MAX(mass_cognitive) as max_mass,
                AVG(in_degree) as avg_in_degree,
                AVG(out_degree) as avg_out_degree
            FROM node_metadata
        """)

        row = cursor.fetchone()

        return {
            "count": row["count"],
            "avg_mass": row["avg_mass"],
            "min_mass": row["min_mass"],
            "max_mass": row["max_mass"],
            "avg_in_degree": row["avg_in_degree"],
            "avg_out_degree": row["avg_out_degree"],
        }

    def _row_to_metadata(self, row: sqlite3.Row) -> NodeMetadata:
        """Convert database row to NodeMetadata.

        Args:
            row: SQLite row

        Returns:
            NodeMetadata instance
        """
        return NodeMetadata(
            symbol_id=row["symbol_id"],
            in_degree=row["in_degree"],
            out_degree=row["out_degree"],
            mass_tf=row["mass_tf"],
            mass_idf=row["mass_idf"],
            mass_hub_correction=row["mass_hub_correction"],
            mass_cognitive=row["mass_cognitive"],
            calling_modules=row["calling_modules"],
            total_modules=row["total_modules"],
            module_tags=json.loads(row["module_tags"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

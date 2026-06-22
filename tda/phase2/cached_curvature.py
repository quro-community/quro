"""
Cached Ricci Curvature Calculator

@module quro.tda.phase2.cached_curvature
@intent Read pre-computed curvature from tda_index.db instead of computing on-the-fly
@constraint Read-only operations, no mutations

This is a drop-in replacement for RicciCurvatureCalculator that reads from
the edge_curvature table instead of computing triangles and curvature.

Performance: O(1) lookup vs O(N) triangle counting
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

from .ricci_curvature import RicciCurvatureComponents


@dataclass(frozen=True)
class CachedCurvatureStats:
    """Statistics about cached curvature data."""

    total_edges: int
    avg_curvature: float
    avg_friction: float
    avg_triangles: float


class CachedRicciCurvatureCalculator:
    """Read pre-computed curvature from cache.

    This is a drop-in replacement for RicciCurvatureCalculator that reads
    from the edge_curvature table in tda_index.db.

    Performance improvement: ~1000× faster (O(1) lookup vs O(N) triangle counting)
    """

    def __init__(
        self,
        tda_db_path: Path | str = ".quro_context/tda_index.db",
    ):
        """Initialize cached calculator.

        Args:
            tda_db_path: Path to tda_index.db with edge_curvature table
        """
        self.tda_db_path = Path(tda_db_path)
        if not self.tda_db_path.exists():
            raise FileNotFoundError(f"TDA database not found: {self.tda_db_path}")

        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self):
        """Context manager entry."""
        self._conn = sqlite3.connect(str(self.tda_db_path))
        self._conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def compute_curvature(self, source: str, target: str) -> RicciCurvatureComponents:
        """Get pre-computed curvature for an edge.

        Args:
            source: Source symbol ID
            target: Target symbol ID

        Returns:
            RicciCurvatureComponents with cached values

        Raises:
            ValueError: If edge not found in cache
        """
        if not self._conn:
            raise RuntimeError("CachedRicciCurvatureCalculator must be used as context manager")

        cursor = self._conn.execute("""
            SELECT ricci_norm, friction, triangle_count
            FROM edge_curvature
            WHERE source = ? AND target = ?
        """, (source, target))

        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Edge not found in cache: {source} → {target}")

        ricci_norm = row["ricci_norm"]
        triangle_count = row["triangle_count"]

        # Get degrees from node_metadata
        cursor = self._conn.execute("""
            SELECT in_degree, out_degree
            FROM node_metadata
            WHERE symbol_id = ?
        """, (source,))
        source_row = cursor.fetchone()
        deg_source = (source_row["in_degree"] + source_row["out_degree"]) if source_row else 0

        cursor = self._conn.execute("""
            SELECT in_degree, out_degree
            FROM node_metadata
            WHERE symbol_id = ?
        """, (target,))
        target_row = cursor.fetchone()
        deg_target = (target_row["in_degree"] + target_row["out_degree"]) if target_row else 0

        # Reconstruct raw curvature from normalized
        deg_max = max(deg_source, deg_target)
        ricci_raw = ricci_norm * (1 + deg_max)

        # Boundary detection
        is_boundary = ricci_norm < -0.5

        return RicciCurvatureComponents(
            edge_id=(source, target),
            deg_source=deg_source,
            deg_target=deg_target,
            triangle_count=triangle_count,
            ricci_raw=ricci_raw,
            ricci_norm=ricci_norm,
            is_boundary=is_boundary,
        )

    def compute_curvature_batch(
        self,
        edges: list[Tuple[str, str]]
    ) -> Dict[Tuple[str, str], RicciCurvatureComponents]:
        """Get pre-computed curvature for multiple edges in batch.

        Args:
            edges: List of (source, target) tuples

        Returns:
            Dict mapping edge to RicciCurvatureComponents
        """
        result = {}

        for source, target in edges:
            try:
                result[(source, target)] = self.compute_curvature(source, target)
            except ValueError:
                # Edge not in cache, skip
                continue

        return result

    def get_stats(self) -> CachedCurvatureStats:
        """Get statistics about cached curvature data.

        Returns:
            CachedCurvatureStats with aggregate statistics
        """
        if not self._conn:
            raise RuntimeError("CachedRicciCurvatureCalculator must be used as context manager")

        cursor = self._conn.execute("""
            SELECT
                COUNT(*) as total_edges,
                AVG(ricci_norm) as avg_curvature,
                AVG(friction) as avg_friction,
                AVG(triangle_count) as avg_triangles
            FROM edge_curvature
        """)

        row = cursor.fetchone()

        return CachedCurvatureStats(
            total_edges=row["total_edges"],
            avg_curvature=round(row["avg_curvature"], 2),
            avg_friction=round(row["avg_friction"], 2),
            avg_triangles=round(row["avg_triangles"], 2),
        )

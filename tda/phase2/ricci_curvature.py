"""
Forman-Ricci Curvature Calculator

Implements normalized Forman-Ricci curvature with overflow protection
for Phase 2 of the Riemannian Manifold upgrade.
"""

import sqlite3
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

from .triangle_counter import DirectedTriangleCounter


@dataclass(frozen=True)
class RicciCurvatureComponents:
    """Components of Ricci curvature calculation."""

    edge_id: Tuple[str, str]  # (source, target)

    # Degree information
    deg_source: int  # Total degree (in + out) of source
    deg_target: int  # Total degree (in + out) of target

    # Triangle count
    triangle_count: int  # Directed triangles (transitive + feedback)

    # Curvature components
    ricci_raw: float  # Raw Forman-Ricci curvature
    ricci_norm: float  # Normalized curvature (overflow-safe)

    # Boundary detection
    is_boundary: bool  # True if negative curvature exceeds threshold


class RicciCurvatureCalculator:
    """Calculates Forman-Ricci curvature with normalization."""

    def __init__(
        self,
        registry_db_path: str = ".quro_context/registry.db",
        boundary_threshold: float = -0.5,
    ):
        """Initialize calculator.

        Args:
            registry_db_path: Path to registry.db
            boundary_threshold: Curvature threshold for boundary detection
        """
        self.registry_db_path = registry_db_path
        self.boundary_threshold = boundary_threshold
        self._conn: Optional[sqlite3.Connection] = None
        self._triangle_counter: Optional[DirectedTriangleCounter] = None

    def __enter__(self):
        """Context manager entry."""
        self._conn = sqlite3.connect(self.registry_db_path)
        self._conn.row_factory = sqlite3.Row
        self._triangle_counter = DirectedTriangleCounter(self.registry_db_path).__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._triangle_counter:
            self._triangle_counter.__exit__(exc_type, exc_val, exc_tb)
            self._triangle_counter = None

        if self._conn:
            self._conn.close()
            self._conn = None

    def compute_curvature(self, source: str, target: str) -> RicciCurvatureComponents:
        """Compute Ricci curvature for an edge.

        Args:
            source: Source symbol ID
            target: Target symbol ID

        Returns:
            RicciCurvatureComponents with all computed values
        """
        if not self._conn or not self._triangle_counter:
            raise RuntimeError("RicciCurvatureCalculator must be used as context manager")

        # Get degree information
        deg_source = self._get_total_degree(source)
        deg_target = self._get_total_degree(target)

        # Count directed triangles
        triangle_result = self._triangle_counter.count_triangles(source, target)
        triangle_count = triangle_result.total_count

        # Compute raw Forman-Ricci curvature
        ricci_raw = self._compute_ricci_raw(deg_source, deg_target, triangle_count)

        # Normalize to prevent overflow
        ricci_norm = self._normalize_curvature(ricci_raw, deg_source, deg_target)

        # Detect boundaries
        is_boundary = ricci_norm < self.boundary_threshold

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
        """Compute curvature for multiple edges in batch.

        Args:
            edges: List of (source, target) tuples

        Returns:
            Dict mapping edge to RicciCurvatureComponents
        """
        result = {}

        for source, target in edges:
            result[(source, target)] = self.compute_curvature(source, target)

        return result

    def _get_total_degree(self, node_id: str) -> int:
        """Get total degree (in + out) for a node.

        Args:
            node_id: Node ID

        Returns:
            Total degree
        """
        # In-degree
        cursor = self._conn.execute(
            "SELECT COUNT(*) as count FROM edges WHERE dst = ?",
            (node_id,)
        )
        in_degree = cursor.fetchone()["count"]

        # Out-degree
        cursor = self._conn.execute(
            "SELECT COUNT(*) as count FROM edges WHERE src = ?",
            (node_id,)
        )
        out_degree = cursor.fetchone()["count"]

        return in_degree + out_degree

    def _compute_ricci_raw(
        self,
        deg_source: int,
        deg_target: int,
        triangle_count: int
    ) -> float:
        """Compute raw Forman-Ricci curvature.

        Formula: Ric(e) = 4 - deg(u) - deg(v) + 3 × Δ(e)

        Args:
            deg_source: Total degree of source
            deg_target: Total degree of target
            triangle_count: Number of directed triangles

        Returns:
            Raw Ricci curvature
        """
        return 4 - deg_source - deg_target + 3 * triangle_count

    def _normalize_curvature(
        self,
        ricci_raw: float,
        deg_source: int,
        deg_target: int
    ) -> float:
        """Normalize curvature to prevent overflow.

        Formula: Ric_norm(e) = Ric_raw(e) / (1 + deg_max)

        This bounds curvature in [-deg_max, 4] range.

        Args:
            ricci_raw: Raw Ricci curvature
            deg_source: Total degree of source
            deg_target: Total degree of target

        Returns:
            Normalized Ricci curvature
        """
        deg_max = max(deg_source, deg_target)
        return ricci_raw / (1 + deg_max)

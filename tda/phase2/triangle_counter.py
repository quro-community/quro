"""
Directed Triangle Counter

Counts directed triangles (transitive closures and feedback loops)
for Forman-Ricci curvature calculation.
"""

import sqlite3
from typing import Set, Tuple, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class TriangleCount:
    """Triangle count result for an edge."""

    edge_id: Tuple[str, str]  # (source, target)
    transitive_count: int  # u→v→w, u→w patterns
    feedback_count: int  # u→v→w→u patterns
    total_count: int  # transitive + feedback


class DirectedTriangleCounter:
    """Counts directed triangles in code graph."""

    def __init__(self, registry_db_path: str = ".quro_context/registry.db"):
        """Initialize triangle counter.

        Args:
            registry_db_path: Path to registry.db
        """
        self.registry_db_path = registry_db_path
        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self):
        """Context manager entry."""
        self._conn = sqlite3.connect(self.registry_db_path)
        self._conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def count_triangles(self, source: str, target: str) -> TriangleCount:
        """Count directed triangles for an edge.

        Only counts:
        1. Transitive triangles: u→v→w and u→w (transitive closure)
        2. Feedback loops: u→v→w→u (cyclic dependency)

        Does NOT count:
        - Shared sinks: u→w, v→w (both call same utility)
        - Shared sources: w→u, w→v (both called by same parent)

        Args:
            source: Source symbol ID
            target: Target symbol ID

        Returns:
            TriangleCount with transitive and feedback counts
        """
        if not self._conn:
            raise RuntimeError("DirectedTriangleCounter must be used as context manager")

        # Get successors (outgoing neighbors) of both nodes
        successors_source = self._get_successors(source)
        successors_target = self._get_successors(target)

        # Get predecessors (incoming neighbors) of source
        predecessors_source = self._get_predecessors(source)

        # Type 1: Transitive triangles (u→v→w, u→w)
        # Common successors of source and target
        transitive_count = len(successors_source & successors_target)

        # Type 2: Feedback loops (u→v→w→u)
        # Successors of target that point back to source
        feedback_count = len(successors_target & predecessors_source)

        total_count = transitive_count + feedback_count

        return TriangleCount(
            edge_id=(source, target),
            transitive_count=transitive_count,
            feedback_count=feedback_count,
            total_count=total_count,
        )

    def count_triangles_batch(
        self,
        edges: list[Tuple[str, str]]
    ) -> dict[Tuple[str, str], TriangleCount]:
        """Count triangles for multiple edges in batch.

        Args:
            edges: List of (source, target) tuples

        Returns:
            Dict mapping edge to TriangleCount
        """
        result = {}

        for source, target in edges:
            result[(source, target)] = self.count_triangles(source, target)

        return result

    def _get_successors(self, node_id: str) -> Set[str]:
        """Get successors (outgoing neighbors) of a node.

        Args:
            node_id: Node ID

        Returns:
            Set of successor node IDs
        """
        cursor = self._conn.execute(
            "SELECT dst FROM edges WHERE src = ?",
            (node_id,)
        )

        return {row["dst"] for row in cursor}

    def _get_predecessors(self, node_id: str) -> Set[str]:
        """Get predecessors (incoming neighbors) of a node.

        Args:
            node_id: Node ID

        Returns:
            Set of predecessor node IDs
        """
        cursor = self._conn.execute(
            "SELECT src FROM edges WHERE dst = ?",
            (node_id,)
        )

        return {row["src"] for row in cursor}

    def get_all_edges(self) -> list[Tuple[str, str]]:
        """Get all edges in the graph.

        Returns:
            List of (source, target) tuples
        """
        if not self._conn:
            raise RuntimeError("DirectedTriangleCounter must be used as context manager")

        cursor = self._conn.execute("SELECT src, dst FROM edges")

        return [(row["src"], row["dst"]) for row in cursor]

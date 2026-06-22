"""
TDA-Enhanced SQLite Graph Adapter

@module quro.io.adapters.sqlite_tda
@intent Adapt SQLite + TDA index to GraphProtocol with curvature/friction enrichment
@constraint I/O operations allowed here (boundary layer)

This adapter:
1. Loads graph data from cqe_index.db (morphisms)
2. Loads TDA data from tda_index.db (cognitive mass, cached curvature)
3. Implements GraphProtocol with TDA-enriched edge weights
4. Caches data for performance
"""

import sqlite3
from pathlib import Path
from typing import Iterable, Tuple, Dict, List, Optional
from dataclasses import dataclass

from core.cqe.types import GraphProtocol
from tda.phase2.cached_curvature import CachedRicciCurvatureCalculator
from tda.phase3.friction_mapper import FrictionMapper


@dataclass(frozen=True)
class TDAEdgeMetadata:
    """TDA metadata for an edge."""

    source_mass: float  # Cognitive mass of source node
    target_mass: float  # Cognitive mass of target node
    curvature: float  # Ricci curvature
    friction: float  # Friction cost
    original_weight: float  # Original MI weight


class SQLiteTDAGraphAdapter:
    """
    SQLite + TDA implementation of GraphProtocol.

    Enriches graph edges with:
    - Cognitive mass (from Phase 1)
    - Ricci curvature (from Phase 2)
    - Friction costs (from Phase 3)

    Edge weight computation:
    - Standard mode: weight = original_mi_weight
    - TDA mode: weight = original_mi_weight / friction

    Lower friction → higher weight → preferred path
    """

    def __init__(
        self,
        cqe_db_path: Path | str,
        tda_db_path: Path | str,
        use_friction: bool = True,
        friction_alpha: float = 0.5,
        friction_beta_cap: float = 5.0,
    ):
        """
        Initialize TDA-enhanced adapter.

        Args:
            cqe_db_path: Path to cqe_index.db (morphisms)
            tda_db_path: Path to tda_index.db (cognitive mass + cached curvature)
            use_friction: Use friction costs (True) or original weights (False)
            friction_alpha: Curvature sensitivity
            friction_beta_cap: Exponential cap for friction
        """
        self.cqe_db_path = Path(cqe_db_path)
        self.tda_db_path = Path(tda_db_path)
        self.use_friction = use_friction

        if not self.cqe_db_path.exists():
            raise FileNotFoundError(f"CQE database not found: {self.cqe_db_path}")
        if not self.tda_db_path.exists():
            raise FileNotFoundError(f"TDA database not found: {self.tda_db_path}")

        # Initialize friction mapper
        self._friction_mapper = FrictionMapper(
            alpha=friction_alpha,
            beta_cap=friction_beta_cap
        )

        # Load graph into memory (immutable after init)
        self._adjacency: Dict[str, List[Tuple[str, float]]] = {}
        self._tda_metadata: Dict[Tuple[str, str], TDAEdgeMetadata] = {}
        self._node_masses: Dict[str, float] = {}

        self._load_graph()

    def _load_graph(self) -> None:
        """
        Load graph from SQLite + TDA into memory.

        Side effects: Reads from databases
        Called once during __init__
        """
        # Load cognitive mass
        self._load_cognitive_mass()

        # Load morphisms and compute TDA enrichment
        self._load_morphisms_with_tda()

    def _load_cognitive_mass(self) -> None:
        """Load cognitive mass from tda_index.db."""
        conn = sqlite3.connect(str(self.tda_db_path))
        conn.row_factory = sqlite3.Row

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol_id, mass_cognitive
                FROM node_metadata
            """)

            for row in cursor.fetchall():
                self._node_masses[row["symbol_id"]] = row["mass_cognitive"]

        finally:
            conn.close()

    def _load_morphisms_with_tda(self) -> None:
        """Load morphisms and enrich with TDA data."""
        # Load morphisms
        cqe_conn = sqlite3.connect(str(self.cqe_db_path))

        try:
            cqe_conn.execute("PRAGMA journal_mode=WAL")
            cqe_conn.execute("PRAGMA synchronous=NORMAL")
            cqe_conn.execute("PRAGMA mmap_size=268435456")
            cqe_conn.execute("PRAGMA cache_size=-64000")

            cursor = cqe_conn.cursor()
            cursor.execute("""
                SELECT from_id, to_id, weight
                FROM morphisms
                WHERE weight > 0
                ORDER BY from_id, weight DESC
            """)

            morphisms = cursor.fetchall()

        finally:
            cqe_conn.close()

        # Compute TDA enrichment with cached curvature calculator
        with CachedRicciCurvatureCalculator(str(self.tda_db_path)) as curvature_calc:
            for from_id, to_id, original_weight in morphisms:
                # Get cognitive mass
                source_mass = self._node_masses.get(from_id, 1.0)
                target_mass = self._node_masses.get(to_id, 1.0)

                # Get cached curvature and friction
                try:
                    curvature_result = curvature_calc.compute_curvature(from_id, to_id)
                    friction_result = self._friction_mapper.compute_friction(
                        curvature_result.ricci_norm
                    )
                    curvature = curvature_result.ricci_norm
                    friction = friction_result.friction
                except (ValueError, Exception):
                    # Fallback if curvature not in cache
                    curvature = 0.0
                    friction = 1.0

                # Compute TDA-enriched weight
                if self.use_friction:
                    # Lower friction → higher weight → preferred path
                    tda_weight = original_weight / friction
                else:
                    tda_weight = original_weight

                # Store metadata
                self._tda_metadata[(from_id, to_id)] = TDAEdgeMetadata(
                    source_mass=source_mass,
                    target_mass=target_mass,
                    curvature=curvature,
                    friction=friction,
                    original_weight=original_weight,
                )

                # Build adjacency list
                if from_id not in self._adjacency:
                    self._adjacency[from_id] = []
                self._adjacency[from_id].append((to_id, tda_weight))

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
            Iterable of (neighbor_id, tda_enriched_weight) tuples
        """
        return self._adjacency.get(node, [])

    def get_edge_metadata(self, source: str, target: str) -> Optional[TDAEdgeMetadata]:
        """
        Get TDA metadata for an edge.

        Args:
            source: Source node ID
            target: Target node ID

        Returns:
            TDAEdgeMetadata or None if edge doesn't exist
        """
        return self._tda_metadata.get((source, target))

    def get_node_mass(self, node: str) -> float:
        """
        Get cognitive mass for a node.

        Args:
            node: Node ID

        Returns:
            Cognitive mass (default 1.0 if not found)
        """
        return self._node_masses.get(node, 1.0)

    def get_stats(self) -> Dict[str, any]:
        """
        Get graph statistics.

        Returns:
            Dict with node_count, edge_count, avg_friction, avg_curvature
        """
        edge_count = sum(len(neighbors) for neighbors in self._adjacency.values())

        # Compute TDA statistics
        frictions = [meta.friction for meta in self._tda_metadata.values()]
        curvatures = [meta.curvature for meta in self._tda_metadata.values()]
        masses = list(self._node_masses.values())

        avg_friction = sum(frictions) / len(frictions) if frictions else 0.0
        avg_curvature = sum(curvatures) / len(curvatures) if curvatures else 0.0
        avg_mass = sum(masses) / len(masses) if masses else 0.0

        return {
            "node_count": len(self._adjacency),
            "edge_count": edge_count,
            "nodes_with_mass": len(self._node_masses),
            "avg_friction": round(avg_friction, 2),
            "avg_curvature": round(avg_curvature, 2),
            "avg_mass": round(avg_mass, 2),
            "use_friction": self.use_friction,
        }

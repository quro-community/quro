"""TDA Bridge — Query TDA Phase 2.5 for Node State

@module quro.core.cqe.tda_bridge
@intent Bridge between CQE and TDA Phase 2.5 offline physics.
       Provides gravity scores, field roles, and energy states for node state detection.

       Data source: .quro_context/quro_tda.duckdb (primary, unified source)
       Fallback: .quro_context/tda/phase2/manifold_states.jsonl (backward compatibility)
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, Optional

import duckdb

from core.cqe.node_state import NodeState, NodeRole, FieldRole, classify_node_role

logger = logging.getLogger(__name__)


class TDABridge:
    """Bridge to TDA Phase 2.5 offline physics."""

    def __init__(self, workspace_root: Path):
        """Initialize TDA bridge.

        Args:
            workspace_root: Workspace root directory
        """
        self.workspace_root = workspace_root
        self.duckdb_path = workspace_root / ".quro_context" / "quro_tda.duckdb"
        self.tda_db_path = workspace_root / ".quro_context" / "tda_index.db"
        self.manifold_states_path = (
            workspace_root / ".quro_context" / "tda" / "phase2" / "manifold_states.jsonl"
        )
        self._state_cache: Dict[str, dict] = {}
        self._loaded = False

    def _load_manifold_states(self) -> None:
        """Load manifold states from DuckDB (primary) or JSONL fallback."""
        if self._loaded:
            return

        # Try DuckDB first (primary unified source)
        if self.duckdb_path.exists():
            try:
                self._load_from_duckdb()
                self._loaded = True
                return
            except Exception as e:
                logger.warning(
                    "Failed to load from DuckDB, falling back to JSONL: %s", e
                )

        # Fallback to JSONL (backward compatibility)
        if self.manifold_states_path.exists():
            self._load_from_jsonl()
            self._loaded = True
            return

        logger.warning(
            "Neither quro_tda.duckdb nor manifold_states.jsonl found. "
            "TDA metrics will return default values."
        )
        self._loaded = True

    def _load_from_duckdb(self) -> None:
        """Load manifold states from DuckDB (manifold_states + energy_states)."""
        conn = duckdb.connect(str(self.duckdb_path), read_only=True)

        try:
            cursor = conn.execute("""
                SELECT
                    m.symbol_id AS symbol,
                    COALESCE(e.field_magnitude, 0.0) AS field_magnitude,
                    COALESCE(e.potential, 0.0) AS energy_potential,
                    0.0 AS energy_kinetic,
                    COALESCE(e.energy_total, 0.0) AS energy_total,
                    COALESCE(e.field_role, 'not_critical_point') AS field_role,
                    COALESCE(e.structural_gravity, 0.5) AS gravity,
                    COALESCE(m.centrality, 0.0) AS centrality,
                    COALESCE(m.betweenness, 0.0) AS betweenness,
                    COALESCE(m.clustering_coeff, 0.0) AS clustering_coeff,
                    COALESCE(m.role_type, 'unknown') AS role_type,
                    0.5 AS role_confidence,
                    COALESCE(e.mass, 0.0) AS cognitive_mass
                FROM manifold_states m
                LEFT JOIN energy_states e ON m.symbol_id = e.symbol_id
            """)

            for row in cursor.fetchall():
                self._state_cache[row[0]] = {
                    "field_magnitude": row[1],
                    "energy": {
                        "potential": row[2],
                        "kinetic": row[3],
                        "total": row[4],
                    },
                    "field_role": row[5],
                    "topology": {
                        "gravity": row[6],
                        "centrality": row[7],
                        "betweenness": row[8],
                        "clustering_coeff": row[9],
                    },
                    "role": {
                        "type": row[10],
                        "confidence": row[11],
                    },
                    "cognitive_mass": row[12],
                }

            logger.info("Loaded %d manifold states from DuckDB", len(self._state_cache))

        finally:
            conn.close()

    def _load_from_sqlite(self) -> None:
        """Load manifold states from unified SQLite table."""
        conn = sqlite3.connect(str(self.tda_db_path))
        conn.row_factory = sqlite3.Row

        try:
            cursor = conn.execute("""
                SELECT
                    symbol,
                    field_magnitude,
                    energy_potential,
                    energy_kinetic,
                    energy_total,
                    field_role,
                    gravity,
                    centrality,
                    betweenness,
                    clustering_coeff,
                    role_type,
                    role_confidence,
                    cognitive_mass
                FROM tda_manifold_states
            """)

            for row in cursor:
                self._state_cache[row["symbol"]] = {
                    "field_magnitude": row["field_magnitude"],
                    "energy": {
                        "potential": row["energy_potential"],
                        "kinetic": row["energy_kinetic"],
                        "total": row["energy_total"],
                    },
                    "field_role": row["field_role"],
                    "topology": {
                        "gravity": row["gravity"],
                        "centrality": row["centrality"],
                        "betweenness": row["betweenness"],
                        "clustering_coeff": row["clustering_coeff"],
                    },
                    "role": {
                        "type": row["role_type"],
                        "confidence": row["role_confidence"],
                    },
                    "cognitive_mass": row["cognitive_mass"],
                }

            logger.info("Loaded %d manifold states from SQLite", len(self._state_cache))

        finally:
            conn.close()

    def _load_from_jsonl(self) -> None:
        """Load manifold states from Phase 2 JSONL (fallback)."""
        with open(self.manifold_states_path) as f:
            for line in f:
                if line.strip():
                    state = json.loads(line)
                    symbol = state["symbol"]
                    # JSONL doesn't have field_magnitude or energy - will return 0.0
                    self._state_cache[symbol] = state

        logger.info("Loaded %d manifold states from JSONL", len(self._state_cache))

    def get_gravity_score(self, symbol_id: str) -> float:
        """Get gravity score for a symbol.

        Args:
            symbol_id: Symbol ID (e.g., 'sym::CQEIndexPipeline')

        Returns:
            Gravity score [0, 1], or 0.5 if not found
        """
        self._load_manifold_states()

        state = self._state_cache.get(symbol_id)
        if state is None:
            return 0.5

        # Gravity is stored in topology metrics
        topology = state.get("topology", {})
        return topology.get("gravity", 0.5)

    def get_field_role(self, symbol_id: str) -> FieldRole:
        """Get field role for a symbol.

        Args:
            symbol_id: Symbol ID

        Returns:
            FieldRole enum value
        """
        self._load_manifold_states()

        state = self._state_cache.get(symbol_id)
        if state is None:
            return FieldRole.NOT_CRITICAL_POINT

        field_role_str = state.get("field_role", "not_critical_point")

        # Map string to enum
        role_map = {
            "attractor": FieldRole.ATTRACTOR,
            "repeller": FieldRole.REPELLER,
            "saddle_point": FieldRole.SADDLE_POINT,
            "not_critical_point": FieldRole.NOT_CRITICAL_POINT,
        }

        return role_map.get(field_role_str, FieldRole.NOT_CRITICAL_POINT)

    def get_energy_total(self, symbol_id: str) -> float:
        """Get total energy for a symbol.

        Args:
            symbol_id: Symbol ID

        Returns:
            Total energy [0, 1], or 0.0 if not found
        """
        self._load_manifold_states()

        state = self._state_cache.get(symbol_id)
        if state is None:
            return 0.0

        energy = state.get("energy", {})
        return energy.get("total", 0.0)

    def get_field_magnitude(self, symbol_id: str) -> float:
        """Get field magnitude for a symbol.

        Args:
            symbol_id: Symbol ID

        Returns:
            Field magnitude [0, ∞), or 0.0 if not found
        """
        self._load_manifold_states()

        state = self._state_cache.get(symbol_id)
        if state is None:
            return 0.0

        return state.get("field_magnitude", 0.0)

    def get_node_state(
        self,
        symbol_id: str,
        out_degree: int,
        in_degree: int,
    ) -> NodeState:
        """Get complete node state for a symbol.

        Args:
            symbol_id: Symbol ID
            out_degree: Number of outgoing edges (from graph adapter)
            in_degree: Number of incoming edges (from graph adapter)

        Returns:
            Complete NodeState with TDA enrichment
        """
        self._load_manifold_states()

        # Classify node role based on degree
        node_role = classify_node_role(out_degree, in_degree)

        # Get TDA metrics
        field_role = self.get_field_role(symbol_id)
        gravity_score = self.get_gravity_score(symbol_id)
        energy_total = self.get_energy_total(symbol_id)
        field_magnitude = self.get_field_magnitude(symbol_id)

        return NodeState(
            node_id=symbol_id,
            out_degree=out_degree,
            in_degree=in_degree,
            node_role=node_role,
            field_role=field_role,
            gravity_score=gravity_score,
            energy_total=energy_total,
            field_magnitude=field_magnitude,
        )

    def is_attractor(self, symbol_id: str) -> bool:
        """Check if symbol is an attractor.

        Args:
            symbol_id: Symbol ID

        Returns:
            True if attractor, False otherwise
        """
        return self.get_field_role(symbol_id) == FieldRole.ATTRACTOR

    def is_repeller(self, symbol_id: str) -> bool:
        """Check if symbol is a repeller.

        Args:
            symbol_id: Symbol ID

        Returns:
            True if repeller, False otherwise
        """
        return self.get_field_role(symbol_id) == FieldRole.REPELLER

    def is_saddle_point(self, symbol_id: str) -> bool:
        """Check if symbol is a saddle point.

        Args:
            symbol_id: Symbol ID

        Returns:
            True if saddle point, False otherwise
        """
        return self.get_field_role(symbol_id) == FieldRole.SADDLE_POINT

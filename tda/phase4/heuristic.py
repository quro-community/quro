"""Heuristic Functions for A* Pathfinding (DEPRECATED)

@module quro.tda.phase4.heuristic

IMPORTANT: A* pathfinding is deprecated in Phase 4 v2.
Use ExplorationEngine.explore() in trajectory_planner.py instead.

This module is kept for backward compatibility with the legacy A* planner.
compute_heuristic() is no longer used in Phase 4 v2 decision-making.

Phase 4 v2 uses:
  - _compute_direction() for single-axis direction scoring
  - Feasibility gate for friction/alignment filtering
  - No black hole penalty (handled by feasibility gate instead)
"""

import logging
import sqlite3
import warnings
from pathlib import Path
from typing import List, Optional

import duckdb
import numpy as np

from .energy_model import compute_vector_alignment, manifold_distance, normalize_distance

logger = logging.getLogger(__name__)


# Design 87 Parameters
# CRITICAL: Heuristic weights must be ≤ energy_model weights to ensure admissibility
# energy_model uses: LAMBDA_DISTANCE=0.15, LAMBDA_ALIGN=0.35
# We use lower weights to account for components not in heuristic (uphill, friction, etc.)
HEURISTIC_WEIGHT = 1.3  # Weighted A* multiplier (empirically validated)
W_MANIFOLD = 0.15       # Match LAMBDA_DISTANCE (was 0.7 - inadmissible!)
W_DIRECTION = 0.30      # Slightly below LAMBDA_ALIGN=0.35 for safety

# Phase 2: Black Hole Gravity Field Parameters
MASS_THRESHOLD = 5.0       # Nodes with mass < 5 are considered "low mass"
FRICTION_THRESHOLD = 0.5   # Nodes with friction > 0.5 are "high friction"
GRAVITY_CONSTANT = 3.0     # Exponential penalty multiplier


class BlackHoleDetector:
    """Detect and cache black hole nodes (low mass + high friction)."""

    def __init__(self, tda_db_path: Optional[Path] = None):
        """Initialize black hole detector.

        Args:
            tda_db_path: Path to tda_index.db (optional)
        """
        self.tda_db_path = tda_db_path or Path(".quro_context/tda_index.db")
        self.duckdb_path = self.tda_db_path.parent / "quro_tda.duckdb"
        self._mass_cache = {}
        self._load_mass_data()

    def _load_mass_data(self):
        """Load cognitive mass from DuckDB (primary) or SQLite (fallback)."""
        if self.duckdb_path.exists():
            self._load_mass_from_duckdb()
        elif self.tda_db_path.exists():
            self._load_mass_from_sqlite()
        else:
            logger.warning("No mass data source found (DuckDB: %s, SQLite: %s), "
                          "black hole detection disabled",
                          self.duckdb_path.exists(), self.tda_db_path.exists())

    def _load_mass_from_duckdb(self):
        """Load cognitive mass from DuckDB energy_states table."""
        try:
            conn = duckdb.connect(str(self.duckdb_path), read_only=True)
            rows = conn.execute(
                "SELECT symbol_id, mass FROM energy_states WHERE mass IS NOT NULL"
            ).fetchall()
            conn.close()

            for symbol_id, mass in rows:
                self._mass_cache[symbol_id] = float(mass) if mass else 0.0

            logger.info("Loaded cognitive mass for %d symbols from DuckDB",
                       len(self._mass_cache))
        except Exception as e:
            logger.warning("Failed to load mass from DuckDB: %s", e)

    def _load_mass_from_sqlite(self):
        """Load cognitive mass from SQLite tda_index.db (fallback)."""
        try:
            conn = sqlite3.connect(str(self.tda_db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT symbol_id, mass_cognitive FROM node_metadata")
            for symbol_id, mass in cursor.fetchall():
                self._mass_cache[symbol_id] = mass
            conn.close()
            logger.info("Loaded cognitive mass for %d symbols from SQLite",
                       len(self._mass_cache))
        except Exception as e:
            logger.warning("Failed to load mass from SQLite: %s", e)

    def is_black_hole(self, symbol: str, friction: float) -> bool:
        """Check if a symbol is a black hole.

        A black hole is defined as:
        - Low cognitive mass (< MASS_THRESHOLD)
        - High friction (> FRICTION_THRESHOLD)

        These are typically bottom-layer libraries (logging, threading, etc.)
        that should be avoided in semantic navigation.

        Args:
            symbol: Symbol ID
            friction: Node friction value

        Returns:
            True if symbol is a black hole
        """
        if symbol not in self._mass_cache:
            return False

        mass = self._mass_cache[symbol]
        return mass < MASS_THRESHOLD and friction > FRICTION_THRESHOLD

    def compute_gravity_penalty(self, symbol: str, friction: float) -> float:
        """Compute gravitational repulsion penalty.

        Formula: exp(friction × GRAVITY_CONSTANT) if black hole, else 1.0

        Args:
            symbol: Symbol ID
            friction: Node friction value

        Returns:
            Gravity penalty multiplier (≥ 1.0)
        """
        if not self.is_black_hole(symbol, friction):
            return 1.0

        # Exponential penalty: higher friction = stronger repulsion
        penalty = np.exp(friction * GRAVITY_CONSTANT)
        return penalty


def compute_heuristic(
    node_state: dict,
    goal_state: dict,
    w_manifold: float = W_MANIFOLD,
    w_direction: float = W_DIRECTION,
    weighted: bool = True,
    black_hole_detector: Optional[BlackHoleDetector] = None,
    node_symbol: Optional[str] = None,
) -> float:
    """DEPRECATED: Use ExplorationEngine._compute_direction() instead.

    Compute A* heuristic (estimated cost to goal).

    Phase 4 v2 uses Beam Search with single-axis intent alignment instead.
    This function is kept for backward compatibility with A* planner.

    Returns:
        Estimated cost to goal (non-negative)
    """
    warnings.warn(
        "compute_heuristic is deprecated in Phase 4 v2. "
        "Use ExplorationEngine.explore() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Manifold distance (geometric) - MUST be normalized to match energy_model
    manifold_dist_raw = manifold_distance(
        node_state["position"],
        goal_state["position"]
    )
    manifold_dist_norm = normalize_distance(manifold_dist_raw, max_distance=10.0)

    # Direction difference (semantic)
    alignment = compute_vector_alignment(
        node_state["direction"],
        goal_state["direction"]
    )
    direction_diff = 1.0 - alignment

    # Weighted combination
    h = (
        w_manifold * manifold_dist_norm +  # FIXED: Use normalized distance
        w_direction * direction_diff
    )

    # Apply weighted A* multiplier if enabled (Design 87)
    if weighted:
        h *= HEURISTIC_WEIGHT

    # Apply black hole gravity penalty (Phase 2)
    if black_hole_detector and node_symbol:
        friction = node_state.get("friction", 0.0)
        gravity_penalty = black_hole_detector.compute_gravity_penalty(node_symbol, friction)

        if gravity_penalty > 1.0:
            logger.debug("Black hole detected: %s (friction=%.2f, penalty=%.2fx)",
                        node_symbol, friction, gravity_penalty)

        h *= gravity_penalty

    return max(0.0, h)  # Ensure non-negative

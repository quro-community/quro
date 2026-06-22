"""Escape Mechanism for Trajectory Planning

@module quro.tda.phase4.escape_mechanism
@intent Provide sink escape using upstream navigation when A* gets stuck.
"""

import json
import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import duckdb

logger = logging.getLogger(__name__)


class EscapeMechanism:
    """Escape mechanism for sink nodes using upstream navigation."""

    def __init__(self, field_data_path: Path):
        """Initialize escape mechanism.

        Args:
            field_data_path: Path to .quro_context/tda/ directory
        """
        self.field_data_path = field_data_path
        self.anisotropic_fields: Dict[str, dict] = {}
        self._incoming_edges_cache: Dict[str, List[Tuple[str, float]]] = {}
        self._load_anisotropic_fields()
        self._load_incoming_edges_cache()

    def _load_incoming_edges_cache(self) -> None:
        """Pre-load all incoming edges into memory for fast lookup.

        Uses pickle cache for ~10× faster loading on subsequent runs.
        Reads from DuckDB events table (primary) or JSONL fallback.
        """
        db_path = self.field_data_path.parent / "quro_tda.duckdb"
        jsonl_path = self.field_data_path / "phase1" / "graph_events.jsonl"
        cache_path = self.field_data_path / "incoming_edges_cache.pkl"

        source_path = db_path if db_path.exists() else jsonl_path
        if not source_path.exists():
            logger.warning("Graph events not found (DuckDB: %s, JSONL: %s)",
                          db_path.exists(), jsonl_path.exists())
            return

        # Try to load from pickle cache first
        if cache_path.exists():
            source_mtime = source_path.stat().st_mtime
            cache_mtime = cache_path.stat().st_mtime

            if cache_mtime >= source_mtime:
                try:
                    logger.info("Loading incoming edges from pickle cache: %s", cache_path)
                    with open(cache_path, "rb") as f:
                        self._incoming_edges_cache = pickle.load(f)
                    logger.info("Loaded incoming edges for %d symbols from cache",
                               len(self._incoming_edges_cache))
                    return
                except Exception as e:
                    logger.warning("Failed to load pickle cache: %s. Rebuilding...", e)

        # Build cache from DuckDB or JSONL
        if db_path.exists():
            self._load_incoming_edges_from_duckdb(db_path)
        elif jsonl_path.exists():
            self._load_incoming_edges_from_jsonl(jsonl_path)

        logger.info("Loaded incoming edges for %d symbols", len(self._incoming_edges_cache))

        # Save to pickle cache for next time
        try:
            logger.info("Saving incoming edges cache to %s", cache_path)
            with open(cache_path, "wb") as f:
                pickle.dump(self._incoming_edges_cache, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info("Cache saved successfully")
        except Exception as e:
            logger.warning("Failed to save pickle cache: %s", e)

    def _load_incoming_edges_from_duckdb(self, db_path: Path) -> None:
        """Load incoming edges from DuckDB events table."""
        logger.info("Building incoming edges cache from DuckDB: %s", db_path)
        try:
            conn = duckdb.connect(str(db_path), read_only=True)
            rows = conn.execute(
                "SELECT dst, src, weight FROM events "
                "WHERE event_type = 'EDGE_TRAVERSE' "
                "AND src LIKE 'sym::%' AND dst IS NOT NULL "
                "ORDER BY dst"
            ).fetchall()
            conn.close()

            for dst, src, weight in rows:
                if dst not in self._incoming_edges_cache:
                    self._incoming_edges_cache[dst] = []
                w = float(weight) if weight is not None else 1.0
                self._incoming_edges_cache[dst].append((src, w))

            logger.info("DuckDB: loaded %d incoming edges for %d symbols",
                       len(rows), len(self._incoming_edges_cache))
        except Exception as e:
            logger.warning("Failed to load incoming edges from DuckDB: %s", e)

    def _load_incoming_edges_from_jsonl(self, jsonl_path: Path) -> None:
        """Load incoming edges from JSONL file (fallback)."""
        logger.info("Building incoming edges cache from JSONL: %s", jsonl_path)
        with open(jsonl_path) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if event.get("event_type") == "EDGE_TRAVERSE":
                        edge = event.get("edge", {})
                        src = edge.get("src")
                        dst = edge.get("dst")
                        weight = edge.get("weight", 1.0)
                        if dst and src and src.startswith("sym::"):
                            if dst not in self._incoming_edges_cache:
                                self._incoming_edges_cache[dst] = []
                            self._incoming_edges_cache[dst].append((src, weight))
                    elif event.get("dst"):
                        src = event.get("src")
                        dst = event.get("dst")
                        weight = event.get("frequency", 1.0)
                        if src and dst:
                            if dst not in self._incoming_edges_cache:
                                self._incoming_edges_cache[dst] = []
                            self._incoming_edges_cache[dst].append((src, weight))
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed JSON line in graph events")
                    continue

    def _load_anisotropic_fields(self) -> None:
        """Load anisotropic fields from Phase 2.5 Pass 5."""
        anisotropic_path = (
            self.field_data_path / "phase2_5" / "anisotropic_fields.jsonl"
        )

        if not anisotropic_path.exists():
            logger.warning(
                "Anisotropic fields not found at %s. "
                "Escape mechanism will be disabled.",
                anisotropic_path
            )
            return

        with open(anisotropic_path) as f:
            for line in f:
                if line.strip():
                    field = json.loads(line)
                    symbol = field["symbol"]
                    self.anisotropic_fields[symbol] = field

        logger.info("Loaded %d anisotropic fields", len(self.anisotropic_fields))

    def is_sink(self, symbol: str, neighbors: List[str]) -> bool:
        """Check if a symbol is a sink node.

        A sink is a node with:
        - No outgoing neighbors (dead end)
        - OR high backward tension (strong upstream pull)

        Args:
            symbol: Symbol ID
            neighbors: List of neighbor symbols

        Returns:
            True if symbol is a sink
        """
        # No neighbors = dead end sink
        if not neighbors:
            return True

        # Check backward tension
        if symbol in self.anisotropic_fields:
            field = self.anisotropic_fields[symbol]
            backward_tension = field.get("backward_tension", 0.0)
            forward_magnitude = field.get("forward_magnitude", 0.0)

            # High backward tension + low forward magnitude = sink
            if backward_tension > 0.7 and forward_magnitude < 0.3:
                return True

        return False

    def find_escape_target(
        self,
        symbol: str,
        intent_vector: Optional[List[float]] = None,
        top_k: int = 3
    ) -> Optional[str]:
        """Find best escape target from sink node.

        Strategy:
        1. Get upstream sources (incoming edges)
        2. Rank by backward tension × source diversity
        3. Filter by intent alignment (if provided)
        4. Return top candidate

        Args:
            symbol: Sink symbol ID
            intent_vector: User intent vector (optional)
            top_k: Number of candidates to consider

        Returns:
            Best escape target symbol, or None if no escape possible
        """
        if symbol not in self.anisotropic_fields:
            return None

        field = self.anisotropic_fields[symbol]

        # Get incoming edges from registry
        incoming_sources = self._get_incoming_sources(symbol)

        if not incoming_sources:
            return None

        # Rank sources by escape score
        candidates = []
        for src, edge_weight in incoming_sources:
            if src not in self.anisotropic_fields:
                continue

            src_field = self.anisotropic_fields[src]

            # Escape score = backward_tension × source_diversity × edge_weight
            escape_score = (
                field["backward_tension"] *
                src_field.get("source_diversity", 0.5) *
                edge_weight
            )

            # Intent alignment bonus (if provided)
            if intent_vector is not None:
                src_direction = src_field.get("forward_direction", [])
                if src_direction:
                    alignment = self._compute_alignment(src_direction, intent_vector)
                    escape_score *= (1.0 + alignment)

            candidates.append((src, escape_score))

        # Sort by escape score (descending)
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Return top candidate
        if candidates:
            return candidates[0][0]

        return None

    def _get_incoming_sources(self, symbol: str) -> List[Tuple[str, float]]:
        """Get incoming sources from cache.

        Args:
            symbol: Target symbol ID

        Returns:
            List of (source_symbol, edge_weight) tuples
        """
        return self._incoming_edges_cache.get(symbol, [])

    def _compute_alignment(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """Compute cosine similarity between vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Alignment score in [0, 1]
        """
        if not vec1 or not vec2:
            return 0.0

        # Simple dot product (vectors should be normalized)
        dot = sum(a * b for a, b in zip(vec1, vec2))

        # Clamp to [0, 1]
        return max(0.0, min(1.0, (dot + 1.0) / 2.0))

"""MI Adjuster - Morphism weight adjustment based on query history

@module quro.pipeline.cqe.mi_adjuster
@intent Compute per-atom MI scores from CQE reflection logs and adjust
       morphism edge weights so that historically useful atoms have stronger
       signal in the graph.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReflectionEvent:
    """Parsed reflection log entry."""
    event: str
    timestamp: str
    query: str
    query_success: bool
    resolved_token: str | None = None
    original_token: str | None = None
    confidence: float | None = None
    raw: Dict[str, Any] | None = None


@dataclass(frozen=True)
class AtomMIScore:
    """Per-atom MI score derived from reflection history.

    Attributes:
        atom_id: The atom identifier (e.g., 'cat::async', 'sym::AsyncLock')
        mi_score: Normalized MI score in [0, 1]
        query_count: Number of queries involving this atom
        success_count: Number of successful queries involving this atom
    """
    atom_id: str
    mi_score: float
    query_count: int
    success_count: int


def load_reflection_log(log_path: Path) -> List[ReflectionEvent]:
    """Load and parse CQE reflection log.

    Args:
        log_path: Path to .quro_context/cqe_reflections.jsonl

    Returns:
        List of parsed ReflectionEvent entries
    """
    if not log_path.exists():
        logger.debug("No reflection log at %s", log_path)
        return []

    events: List[ReflectionEvent] = []
    skipped_lines = 0
    try:
        with open(log_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    events.append(ReflectionEvent(
                        event=data.get("event", "unknown"),
                        timestamp=data.get("timestamp", ""),
                        query=data.get("query", ""),
                        query_success=data.get("query_success", False),
                        resolved_token=data.get("resolved_token"),
                        original_token=data.get("original_token"),
                        confidence=data.get("confidence"),
                        raw=data,
                    ))
                except json.JSONDecodeError:
                    skipped_lines += 1
                    logger.debug(
                        "Skipping malformed line %d in %s",
                        line_num, log_path,
                    )
                    continue
    except OSError as e:
        logger.warning("Failed to read reflection log: %s", e)

    logger.info("Loaded %d reflection events from %s", len(events), log_path)
    if skipped_lines > 0:
        logger.warning(
            "Skipped %d malformed lines in %s", skipped_lines, log_path,
        )
    return events


def compute_atom_mi_scores(
    events: List[ReflectionEvent],
) -> Dict[str, AtomMIScore]:
    """Compute per-atom MI scores from reflection events.

    MI score = payload delivery rate (success_count / query_count).
    Atoms with no queries get mi_score = 0.0 (neutral floor applied later).

    Args:
        events: Parsed reflection events

    Returns:
        Dict mapping atom_id → AtomMIScore
    """
    atom_stats: Dict[str, Dict[str, int]] = {}

    for event in events:
        # Extract atom IDs from resolved_token
        atom_id = event.resolved_token
        if not atom_id:
            continue

        if atom_id not in atom_stats:
            atom_stats[atom_id] = {"total": 0, "success": 0}

        atom_stats[atom_id]["total"] += 1
        if event.query_success:
            atom_stats[atom_id]["success"] += 1

    scores: Dict[str, AtomMIScore] = {}
    for atom_id, stats in atom_stats.items():
        total = stats["total"]
        success = stats["success"]
        mi_score = success / total if total > 0 else 0.0
        scores[atom_id] = AtomMIScore(
            atom_id=atom_id,
            mi_score=mi_score,
            query_count=total,
            success_count=success,
        )

    logger.info(
        "Computed MI scores for %d atoms from %d events",
        len(scores), len(events),
    )
    return scores


class MorphismMIAdjuster:
    """Adjust morphism weights based on per-atom MI scores.

    Formula: adjusted_weight = base_weight * (0.5 + 0.5 * avg(mi_from, mi_to))

    Where avg(mi_from, mi_to) is the mean of source and target atom MI scores.
    For atoms with no MI data, mi_score defaults to 0.5 (neutral).

    This ensures:
      - High-MI edges (both endpoints useful) → weight amplified
      - Low-MI edges (one or both endpoints unused) → weight attenuated
      - No-MI edges (cold start) → neutral adjustment (× 0.75)

    Cold-start behavior:
      - No reflection data → all atoms get mi_score=0.5 (neutral)
      - Formula: weight * (0.5 + 0.5 * 0.5) = weight * 0.75
      - This prevents zero-MI atoms from being penalized before any queries run

    Hybrid Mode (TDA + History):
      MI_final = ω · MI_tda + (1-ω) · MI_history
      where ω = max(0.1, 1.0 - query_count / 100)

      - query_count < 10: ω ≈ 0.9 (TDA-dominant)
      - query_count = 50: ω = 0.5 (balanced)
      - query_count ≥ 100: ω = 0.1 (history-dominant)
    """

    DEFAULT_MI_SCORE = 0.5
    MI_WEIGHT_RANGE = (0.3, 1.0)  # Clamp factor to [0.3, 1.0]

    def __init__(
        self,
        mi_scores: Dict[str, AtomMIScore],
        tda_scores: Dict[str, float] | None = None,
    ) -> None:
        """Initialize MI adjuster.

        Args:
            mi_scores: Dict mapping atom_id → AtomMIScore (from query history)
            tda_scores: Optional dict mapping atom_id → TDA-derived MI score
        """
        self._mi_scores = mi_scores
        self._tda_scores = tda_scores or {}

    def get_mi_score(self, atom_id: str) -> float:
        """Get MI score for an atom using hybrid TDA + history.

        Hybrid formula:
        MI_final = ω · MI_tda + (1-ω) · MI_history
        where ω = max(0.1, 1.0 - query_count / 100)

        Returns default for unknown atoms.
        """
        # Get history-based MI
        history_entry = self._mi_scores.get(atom_id)
        history_mi = history_entry.mi_score if history_entry else None
        query_count = history_entry.query_count if history_entry else 0

        # Get TDA-based MI
        tda_mi = self._tda_scores.get(atom_id)

        # Hybrid blending
        if history_mi is not None and tda_mi is not None:
            # Compute dynamic weight: ω decreases as query_count increases
            omega = max(0.1, 1.0 - query_count / 100.0)
            final_mi = omega * tda_mi + (1.0 - omega) * history_mi
            return final_mi
        elif history_mi is not None:
            # Only history available
            return history_mi
        elif tda_mi is not None:
            # Only TDA available (cold start with TDA floor)
            return tda_mi
        else:
            # No data at all
            return self.DEFAULT_MI_SCORE

    def compute_adjustment_factor(
        self, from_id: str, to_id: str,
    ) -> float:
        """Compute MI adjustment factor for an edge.

        Factor = 0.5 + 0.5 * avg(mi_from, mi_to)
        Clamped to [0.3, 1.0].

        Args:
            from_id: Source atom ID
            to_id: Target atom ID

        Returns:
            Adjustment factor in [0.3, 1.0]
        """
        mi_from = self.get_mi_score(from_id)
        mi_to = self.get_mi_score(to_id)
        avg_mi = (mi_from + mi_to) / 2.0
        factor = 0.5 + 0.5 * avg_mi

        # Clamp to valid range
        lo, hi = self.MI_WEIGHT_RANGE
        return max(lo, min(hi, factor))

    def adjust_morphisms(
        self, morphisms: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Apply MI-weighted adjustment to morphism list.

        Immutable: Returns new list, never mutates input.

        Args:
            morphisms: Original morphism list (not mutated)

        Returns:
            Tuple of (new_morphisms, stats_dict)
        """
        if not self._mi_scores:
            logger.info("No MI scores available, skipping adjustment")
            return list(morphisms), {"adjusted": 0, "total": len(morphisms)}

        new_morphisms = []
        adjusted_count = 0
        total_delta = 0.0

        for m in morphisms:
            from_id = m["from_id"] if isinstance(m, dict) else m[0]
            to_id = m["to_id"] if isinstance(m, dict) else m[1]
            base_weight = m["weight"] if isinstance(m, dict) else m[3]

            factor = self.compute_adjustment_factor(from_id, to_id)
            new_weight = round(base_weight * factor, 4)

            if abs(new_weight - base_weight) > 1e-6:
                adjusted_count += 1
                total_delta += abs(new_weight - base_weight)

            new_m = dict(m) if isinstance(m, dict) else {
                "from_id": m[0], "to_id": m[1], "kind": m[2], "weight": m[3],
            }
            new_m["weight"] = new_weight
            new_morphisms.append(new_m)

        stats = {
            "adjusted": adjusted_count,
            "total": len(morphisms),
            "atoms_with_mi": len(self._mi_scores),
            "avg_delta": round(total_delta / max(adjusted_count, 1), 6),
        }

        logger.info(
            "MI adjustment: %d/%d morphisms adjusted (avg delta=%.6f)",
            adjusted_count, len(morphisms), stats["avg_delta"],
        )
        return new_morphisms, stats

    @classmethod
    def from_reflection_log(
        cls, log_path: Path,
        tda_scores_path: Path | None = None,
    ) -> Tuple["MorphismMIAdjuster", Dict[str, Any]]:
        """Factory: build adjuster directly from reflection log.

        Args:
            log_path: Path to .quro_context/cqe_reflections.jsonl
            tda_scores_path: Optional path to TDA MI scores JSON

        Returns:
            Tuple of (MorphismMIAdjuster, loading_stats)
        """
        events = load_reflection_log(log_path)
        mi_scores = compute_atom_mi_scores(events)

        # Load TDA scores if available
        tda_scores: Dict[str, float] = {}
        if tda_scores_path and tda_scores_path.exists():
            with open(tda_scores_path) as f:
                tda_data = json.load(f)
                for atom_id, score_data in tda_data.get("scores", {}).items():
                    tda_scores[atom_id] = score_data["mi_score"]
            logger.info("Loaded %d TDA MI scores from %s", len(tda_scores), tda_scores_path)

        adjuster = cls(mi_scores, tda_scores)

        loading_stats = {
            "events_loaded": len(events),
            "atoms_with_mi": len(mi_scores),
            "atoms_with_tda": len(tda_scores),
            "high_mi_atoms": sum(
                1 for s in mi_scores.values() if s.mi_score >= 0.8
            ),
            "low_mi_atoms": sum(
                1 for s in mi_scores.values() if s.mi_score < 0.3
            ),
        }
        return adjuster, loading_stats

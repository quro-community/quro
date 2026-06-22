"""TDA-to-MI Warm-up: Generate initial MI scores from TDA Phase 2 analysis

@module quro.tda.mi_warmup
@intent Convert TDA manifold states (field_role, energy, mass, field_magnitude)
       into initial MI scores to bootstrap CQE navigation before any queries run.

       Hybrid Protocol:
       MI_final = ω · MI_tda + (1-ω) · MI_history
       where ω decreases as query_count increases.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TDAMIScore:
    """MI score derived from TDA Phase 2 analysis.

    Attributes:
        atom_id: Symbol ID (e.g., 'sym::LlmGuard')
        mi_score: Derived MI score in [0, 1]
        field_role: TDA field role (attractor, saddle_point, repeller)
        energy_total: Total energy from TDA
        mass: Symbol mass (centrality)
        field_magnitude: Field gradient strength
        confidence: Confidence in this score [0, 1]
    """
    atom_id: str
    mi_score: float
    field_role: str
    energy_total: float
    mass: float
    field_magnitude: float
    confidence: float


def load_manifold_states(manifold_path: Path) -> List[Dict]:
    """Load TDA Phase 2 manifold states.

    Args:
        manifold_path: Path to .quro_context/tda/phase2/manifold_states.jsonl

    Returns:
        List of manifold state dicts
    """
    if not manifold_path.exists():
        logger.warning("Manifold states not found at %s", manifold_path)
        return []

    states = []
    with open(manifold_path) as f:
        for line in f:
            if line.strip():
                states.append(json.loads(line))

    logger.info("Loaded %d manifold states from %s", len(states), manifold_path)
    return states


def compute_tda_mi_score(state: Dict) -> TDAMIScore:
    """Compute MI score from TDA manifold state.

    Formula:
    1. Base MI from field_role:
       - attractor: 0.8 (stable, high-value endpoint)
       - saddle_point: 0.5 (transitional, medium value)
       - repeller: 0.3 (unstable, low value)
       - unknown: 0.5 (neutral)

    2. Mass boost (centrality): +min(0.2, mass * 0.5)
       High-degree nodes are navigation hubs

    3. Field magnitude boost: +min(0.1, field_magnitude * 0.2)
       Strong gradients indicate useful navigation

    4. Energy penalty: -min(0.1, energy_total * 0.05) if energy > 1.0
       Very high energy can indicate volatility

    Final: clamp to [0.2, 1.0]

    Args:
        state: Manifold state dict

    Returns:
        TDAMIScore with computed MI
    """
    symbol = state.get("symbol", "")
    field_role = state.get("field_role", "unknown")
    energy = state.get("energy", {})
    energy_total = energy.get("total", 0.0) if isinstance(energy, dict) else 0.0
    mass = state.get("mass", 0.0)
    field_magnitude = state.get("field_magnitude", 0.0)

    # Base MI from field role
    base_mi = {
        "attractor": 0.8,
        "saddle_point": 0.5,
        "repeller": 0.3,
    }.get(field_role, 0.5)

    # Mass boost (centrality)
    mass_boost = min(0.2, mass * 0.5)

    # Field magnitude boost (gradient strength)
    field_boost = min(0.1, field_magnitude * 0.2)

    # Energy penalty (volatility)
    energy_penalty = 0.0
    if energy_total > 1.0:
        energy_penalty = min(0.1, (energy_total - 1.0) * 0.05)

    # Compute final MI
    mi_score = base_mi + mass_boost + field_boost - energy_penalty
    mi_score = max(0.2, min(1.0, mi_score))

    # Confidence based on data completeness
    confidence = 1.0
    if field_role == "unknown":
        confidence *= 0.5
    if mass == 0.0:
        confidence *= 0.8
    if field_magnitude == 0.0:
        confidence *= 0.9

    return TDAMIScore(
        atom_id=symbol,
        mi_score=mi_score,
        field_role=field_role,
        energy_total=energy_total,
        mass=mass,
        field_magnitude=field_magnitude,
        confidence=confidence,
    )


def generate_tda_mi_scores(
    workspace_root: Path,
    output_path: Optional[Path] = None,
) -> Dict[str, TDAMIScore]:
    """Generate TDA-derived MI scores from manifold states.

    Args:
        workspace_root: Workspace root directory
        output_path: Optional path to write scores (JSON)

    Returns:
        Dict mapping atom_id → TDAMIScore
    """
    manifold_path = workspace_root / ".quro_context" / "tda" / "phase2" / "manifold_states.jsonl"
    states = load_manifold_states(manifold_path)

    if not states:
        logger.warning("No manifold states found, cannot generate TDA MI scores")
        return {}

    scores: Dict[str, TDAMIScore] = {}
    for state in states:
        score = compute_tda_mi_score(state)
        scores[score.atom_id] = score

    # Statistics
    high_mi = sum(1 for s in scores.values() if s.mi_score >= 0.8)
    medium_mi = sum(1 for s in scores.values() if 0.5 <= s.mi_score < 0.8)
    low_mi = sum(1 for s in scores.values() if s.mi_score < 0.5)

    logger.info(
        "Generated TDA MI scores: %d total (high: %d, medium: %d, low: %d)",
        len(scores), high_mi, medium_mi, low_mi,
    )

    # Write to file if requested
    if output_path:
        output_data = {
            "metadata": {
                "source": "tda_phase2",
                "total_scores": len(scores),
                "high_mi_count": high_mi,
                "medium_mi_count": medium_mi,
                "low_mi_count": low_mi,
            },
            "scores": {
                atom_id: {
                    "mi_score": score.mi_score,
                    "field_role": score.field_role,
                    "energy_total": score.energy_total,
                    "mass": score.mass,
                    "field_magnitude": score.field_magnitude,
                    "confidence": score.confidence,
                }
                for atom_id, score in scores.items()
            }
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        logger.info("Wrote TDA MI scores to %s", output_path)

    return scores


def load_manual_seeds(seeds_path: Path) -> Dict[str, float]:
    """Load manual MI seed scores from JSON.

    Format:
    {
      "seeds": [
        {"atom": "sym::main", "mi_score": 1.0},
        {"atom": "cat::async", "mi_score": 0.8}
      ]
    }

    Args:
        seeds_path: Path to mi_seeds.json

    Returns:
        Dict mapping atom_id → mi_score
    """
    if not seeds_path.exists():
        return {}

    with open(seeds_path) as f:
        data = json.load(f)

    seeds = {}
    for entry in data.get("seeds", []):
        atom = entry.get("atom")
        score = entry.get("mi_score")
        if atom and score is not None:
            seeds[atom] = float(score)

    logger.info("Loaded %d manual MI seeds from %s", len(seeds), seeds_path)
    return seeds


def merge_mi_sources(
    tda_scores: Dict[str, TDAMIScore],
    manual_seeds: Dict[str, float],
) -> Dict[str, TDAMIScore]:
    """Merge TDA-derived scores with manual seeds.

    Manual seeds override TDA scores (user knows best).

    Args:
        tda_scores: TDA-derived scores
        manual_seeds: Manual seed scores

    Returns:
        Merged scores (manual seeds take precedence)
    """
    merged = dict(tda_scores)

    for atom_id, manual_score in manual_seeds.items():
        if atom_id in merged:
            # Override TDA score
            original = merged[atom_id]
            merged[atom_id] = TDAMIScore(
                atom_id=atom_id,
                mi_score=manual_score,
                field_role=original.field_role,
                energy_total=original.energy_total,
                mass=original.mass,
                field_magnitude=original.field_magnitude,
                confidence=1.0,  # Manual seeds have full confidence
            )
        else:
            # New seed not in TDA
            merged[atom_id] = TDAMIScore(
                atom_id=atom_id,
                mi_score=manual_score,
                field_role="manual_seed",
                energy_total=0.0,
                mass=0.0,
                field_magnitude=0.0,
                confidence=1.0,
            )

    logger.info("Merged %d manual seeds into TDA scores", len(manual_seeds))
    return merged

"""Pass 5: Backward Tension Computation

@module quro.tda.phase2_5.pass5_backward_tension
@intent Compute backward tension and source diversity to create anisotropic field model.

       Backward tension = aggregate incoming edge strength weighted by source gravity
       Source diversity = entropy of incoming source distribution

       This enables controlled upstream navigation without destroying forward causality.
"""

import json
import logging
import math
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnisotropicField:
    """Anisotropic field state for a symbol.

    Attributes:
        symbol: Symbol ID (sym::...)
        forward_direction: 128-dim semantic vector (from Phase 2)
        forward_magnitude: Flow strength [0, 1]
        backward_tension: Upstream pull strength [0, 1]
        source_diversity: Entropy of incoming sources [0, 1]
        in_degree: Number of incoming edges
        out_degree: Number of outgoing edges
        field_type: Always "anisotropic"
    """
    symbol: str
    forward_direction: List[float]
    forward_magnitude: float
    backward_tension: float
    source_diversity: float
    in_degree: int
    out_degree: int
    field_type: str = "anisotropic"


def compute_backward_tension(
    incoming_edges: List[tuple[str, float]],
    gravity_scores: Dict[str, float]
) -> float:
    """Compute backward tension from incoming edges.

    Formula: tension = sum(edge_weight * source_gravity) / in_degree

    Args:
        incoming_edges: List of (source_symbol, edge_weight) tuples
        gravity_scores: Dict mapping symbol → gravity score

    Returns:
        Backward tension [0, 1]
    """
    if not incoming_edges:
        return 0.0

    total_tension = sum(
        weight * gravity_scores.get(src, 0.5)
        for src, weight in incoming_edges
    )

    # Normalize by in-degree to prevent explosion
    return min(1.0, total_tension / len(incoming_edges))


def compute_source_diversity(incoming_edges: List[tuple[str, float]]) -> float:
    """Compute source diversity (entropy of incoming distribution).

    Formula: diversity = -sum(p_i * log(p_i)) / log(n)

    High diversity = many balanced sources
    Low diversity = single dominant source

    Args:
        incoming_edges: List of (source_symbol, edge_weight) tuples

    Returns:
        Source diversity [0, 1]
    """
    if not incoming_edges:
        return 0.0

    if len(incoming_edges) == 1:
        return 0.0  # Single source = no diversity

    # Normalize weights to probabilities
    total_weight = sum(weight for _, weight in incoming_edges)
    if total_weight == 0:
        return 0.0

    probs = [weight / total_weight for _, weight in incoming_edges]

    # Compute Shannon entropy
    entropy = -sum(p * math.log(p) for p in probs if p > 0)

    # Normalize by max entropy (log(n))
    max_entropy = math.log(len(incoming_edges))

    return entropy / max_entropy if max_entropy > 0 else 0.0


def load_gravity_scores(structural_metrics_path: Path) -> Dict[str, float]:
    """Load gravity scores from Pass 2 output.

    Args:
        structural_metrics_path: Path to structural_metrics.json

    Returns:
        Dict mapping symbol → gravity_score
    """
    with open(structural_metrics_path, "r") as f:
        data = json.load(f)

    # Extract metrics dict (format: {"metadata": {...}, "metrics": {symbol: {...}}})
    metrics = data.get("metrics", {})

    return {
        symbol: info["gravity_score"]
        for symbol, info in metrics.items()
    }


def load_forward_fields(offline_energy_path: Path) -> Dict[str, dict]:
    """Load forward field data from Pass 4 output.

    Args:
        offline_energy_path: Path to offline_energy.json

    Returns:
        Dict mapping symbol → {direction, magnitude}
    """
    with open(offline_energy_path, "r") as f:
        data = json.load(f)

    # Extract states dict (format: {"metadata": {...}, "states": {symbol: {...}}})
    states = data.get("states", {})

    forward_fields = {}
    for symbol, state in states.items():
        forward_fields[symbol] = {
            "direction": state.get("field_direction", [0.0] * 128),
            "magnitude": state.get("field_magnitude", 0.0)
        }

    return forward_fields


def query_incoming_edges(
    registry_db_path: Path,
    symbol: str
) -> List[tuple[str, float]]:
    """Query incoming edges for a symbol from registry database.

    Args:
        registry_db_path: Path to registry.db
        symbol: Target symbol ID

    Returns:
        List of (source_symbol, edge_weight) tuples
    """
    conn = sqlite3.connect(registry_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query edges table for incoming edges (dst = symbol)
    cursor.execute(
        """
        SELECT src, weight
        FROM edges
        WHERE dst = ?
        ORDER BY weight DESC
        """,
        (symbol,)
    )

    edges = [(row["src"], row["weight"]) for row in cursor.fetchall()]
    conn.close()

    return edges


def query_out_degree(registry_db_path: Path, symbol: str) -> int:
    """Query out-degree for a symbol.

    Args:
        registry_db_path: Path to registry.db
        symbol: Symbol ID

    Returns:
        Out-degree count
    """
    conn = sqlite3.connect(registry_db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) as cnt FROM edges WHERE src = ?",
        (symbol,)
    )

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else 0


def compute_anisotropic_fields(
    registry_db_path: Path,
    structural_metrics_path: Path,
    offline_energy_path: Path,
    output_path: Path
) -> int:
    """Compute anisotropic fields for all symbols.

    Args:
        registry_db_path: Path to registry.db
        structural_metrics_path: Path to structural_metrics.json (Pass 2)
        offline_energy_path: Path to offline_energy.json (Pass 4)
        output_path: Path to output anisotropic_fields.jsonl

    Returns:
        Number of fields computed
    """
    logger.info("Loading gravity scores from %s", structural_metrics_path)
    gravity_scores = load_gravity_scores(structural_metrics_path)

    logger.info("Loading forward fields from %s", offline_energy_path)
    forward_fields = load_forward_fields(offline_energy_path)

    logger.info("Computing backward tension for %d symbols", len(forward_fields))

    fields_computed = 0

    with open(output_path, "w") as f:
        for symbol in forward_fields.keys():
            # Query incoming edges
            incoming_edges = query_incoming_edges(registry_db_path, symbol)
            in_degree = len(incoming_edges)

            # Query out-degree
            out_degree = query_out_degree(registry_db_path, symbol)

            # Compute backward tension
            backward_tension = compute_backward_tension(
                incoming_edges,
                gravity_scores
            )

            # Compute source diversity
            source_diversity = compute_source_diversity(incoming_edges)

            # Get forward field
            forward = forward_fields[symbol]

            # Create anisotropic field
            field = AnisotropicField(
                symbol=symbol,
                forward_direction=forward["direction"],
                forward_magnitude=forward["magnitude"],
                backward_tension=backward_tension,
                source_diversity=source_diversity,
                in_degree=in_degree,
                out_degree=out_degree,
                field_type="anisotropic"
            )

            # Write to JSONL
            f.write(json.dumps(asdict(field)) + "\n")
            fields_computed += 1

            if fields_computed % 100 == 0:
                logger.info("Processed %d symbols", fields_computed)

    logger.info("Computed %d anisotropic fields", fields_computed)
    logger.info("Output written to %s", output_path)

    return fields_computed

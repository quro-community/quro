"""Pass 6: Attractor Bias Injection

@module quro.tda.phase2_5.pass6_attractor_bias
@intent Add terminal node weighting to create stable destination points in the topology.
       Fixes the "no attractors" problem identified in LLM-CQE-TDA travel analysis.

       Attractor bias is added to nodes that:
       1. Have terminal characteristics (out_degree == 0, high in_degree)
       2. Have persistence tags (database, serialize, snapshot, persist)
       3. Are not utility/helper functions

       This creates stable sinks in the energy landscape, preventing wandering
       trajectories and improving LLM interpretability.
"""

import json
import logging
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

# Attractor bias coefficient (Design 90 analysis recommendation)
ATTRACTOR_BIAS = 0.3

# Terminal tags that indicate persistence/completion
TERMINAL_TAGS = {
    "database",
    "serialize",
    "snapshot",
    "persist",
    "commit",
    "write",
    "save",
    "store",
    "flush",
    "finalize",
}

# Utility tags that should NOT be attractors
UTILITY_TAGS = {
    "helper",
    "util",
    "format",
    "validate",
    "parse",
    "convert",
}

# Basin attractor thresholds (Design 94 - annotation layer only)
BASIN_CONVERGENCE_RATIO = 2.0  # in_degree / (out_degree + 1)
BASIN_MIN_IN_DEGREE = 3
BASIN_MAX_OUT_DEGREE = 20  # Prevent hub pollution
BASIN_ENERGY_RANK_THRESHOLD = 0.3  # Top 30%


@dataclass(frozen=True)
class AttractorBiasedState:
    """Energy state with attractor bias applied.

    Attributes:
        symbol: Symbol ID
        original_total: Original total energy (before bias)
        attractor_bias: Bias added [0, ATTRACTOR_BIAS]
        adjusted_total: Total energy after bias
        is_attractor_candidate: True if bias was applied
        bias_reason: Reason for bias (terminal, tags, or none)
        out_degree: Number of outgoing edges
        in_degree: Number of incoming edges
        tags: Set of behavioral tags
        is_basin: True if node is a basin attractor (annotation only)
    """
    symbol: str
    original_total: float
    attractor_bias: float
    adjusted_total: float
    is_attractor_candidate: bool
    bias_reason: str
    out_degree: int
    in_degree: int
    tags: List[str]
    is_basin: bool = False  # Design 94 - annotation layer only


def is_basin_attractor(
    out_degree: int,
    in_degree: int,
    energy: float,
    energy_rank: float,
) -> bool:
    """Check if node is a basin attractor (convergence point).

    This is an ANNOTATION LAYER ONLY - does not affect CQE weights, tau, or pruning.
    Basin attractors are high-convergence nodes that many paths lead to.

    Args:
        out_degree: Number of outgoing edges
        in_degree: Number of incoming edges
        energy: Total energy of the node
        energy_rank: Energy rank [0,1] where 0 = highest energy

    Returns:
        True if node is a basin attractor candidate
    """
    # Convergence ratio: more incoming than outgoing
    convergence_ratio = in_degree / (out_degree + 1)  # +1 to avoid div by zero

    return (
        convergence_ratio > BASIN_CONVERGENCE_RATIO
        and in_degree >= BASIN_MIN_IN_DEGREE
        and out_degree <= BASIN_MAX_OUT_DEGREE  # Prevent hub pollution
        and energy_rank <= BASIN_ENERGY_RANK_THRESHOLD  # Top 30% energy
    )


def has_terminal_tags(tags: Set[str]) -> bool:
    """Check if symbol has terminal/persistence tags.

    Args:
        tags: Set of behavioral tags

    Returns:
        True if any terminal tag present
    """
    return bool(TERMINAL_TAGS & tags)


def has_utility_tags(tags: Set[str]) -> bool:
    """Check if symbol has utility/helper tags.

    Args:
        tags: Set of behavioral tags

    Returns:
        True if any utility tag present
    """
    return bool(UTILITY_TAGS & tags)


def is_terminal_node(out_degree: int, in_degree: int, node_type: str) -> bool:
    """Check if node is a terminal node (sink).

    Args:
        out_degree: Number of outgoing edges
        in_degree: Number of incoming edges
        node_type: Node type (method, function, class, etc.)

    Returns:
        True if terminal node
    """
    # Terminal: zero out-degree, high in-degree, not a class
    return (
        out_degree == 0
        and in_degree > 0
        and node_type in ("method", "function", "async_method")
    )


def compute_attractor_bias(
    out_degree: int,
    in_degree: int,
    tags: Set[str],
    node_type: str,
) -> tuple[float, str]:
    """Compute attractor bias for a symbol.

    Args:
        out_degree: Number of outgoing edges
        in_degree: Number of incoming edges
        tags: Set of behavioral tags
        node_type: Node type

    Returns:
        Tuple of (bias_value, reason)
    """
    # Skip utility functions
    if has_utility_tags(tags):
        return (0.0, "utility_excluded")

    # Terminal node with high in-degree
    if is_terminal_node(out_degree, in_degree, node_type):
        return (ATTRACTOR_BIAS, "terminal_sink")

    # Has terminal tags (database, serialize, etc.)
    if has_terminal_tags(tags):
        # Partial bias for non-terminal nodes with terminal tags
        return (ATTRACTOR_BIAS * 0.7, "terminal_tags")

    # No bias
    return (0.0, "none")


def load_offline_energy(offline_energy_path: Path) -> Dict[str, dict]:
    """Load offline energy states from Pass 4 output.

    Args:
        offline_energy_path: Path to offline_energy.json

    Returns:
        Dict mapping symbol → energy state
    """
    with open(offline_energy_path, "r") as f:
        data = json.load(f)

    return data.get("states", {})


def query_node_metadata(
    registry_db_path: Path,
    symbol: str,
) -> tuple[int, int, Set[str], str]:
    """Query node metadata from registry database.

    Args:
        registry_db_path: Path to registry.db
        symbol: Symbol ID

    Returns:
        Tuple of (out_degree, in_degree, tags, node_type)
    """
    conn = sqlite3.connect(registry_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query node metadata
    cursor.execute(
        """
        SELECT metadata
        FROM nodes
        WHERE id = ?
        """,
        (symbol,)
    )

    row = cursor.fetchone()
    if not row:
        conn.close()
        return (0, 0, set(), "unknown")

    metadata = json.loads(row["metadata"]) if row["metadata"] else {}
    node_type = metadata.get("kind", "unknown")

    # Query out-degree
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM edges WHERE src = ?",
        (symbol,)
    )
    out_degree = cursor.fetchone()["cnt"]

    # Query in-degree
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM edges WHERE dst = ?",
        (symbol,)
    )
    in_degree = cursor.fetchone()["cnt"]

    # Extract tags from metadata
    tags = set(metadata.get("tags", []))

    conn.close()

    return (out_degree, in_degree, tags, node_type)


def apply_attractor_bias(
    registry_db_path: Path,
    offline_energy_path: Path,
    output_path: Path,
) -> int:
    """Apply attractor bias to offline energy states.

    Also computes basin attractor annotations (Design 94 - annotation layer only).

    Args:
        registry_db_path: Path to registry.db
        offline_energy_path: Path to offline_energy.json (Pass 4)
        output_path: Path to output attractor_biased_energy.json

    Returns:
        Number of symbols with bias applied
    """
    logger.info("Loading offline energy states from %s", offline_energy_path)
    energy_states = load_offline_energy(offline_energy_path)

    logger.info("Applying attractor bias to %d symbols", len(energy_states))

    # First pass: compute energy ranks
    energies = [(symbol, state.get("total", 0.0)) for symbol, state in energy_states.items()]
    energies.sort(key=lambda x: -x[1])  # Sort descending by energy
    energy_ranks = {symbol: i / len(energies) for i, (symbol, _) in enumerate(energies)}

    biased_states: Dict[str, AttractorBiasedState] = {}
    bias_applied_count = 0
    basin_count = 0

    for symbol, state in energy_states.items():
        original_total = state.get("total", 0.0)

        # Query node metadata
        out_degree, in_degree, tags, node_type = query_node_metadata(
            registry_db_path, symbol
        )

        # Compute attractor bias (original logic - unchanged)
        bias_value, bias_reason = compute_attractor_bias(
            out_degree, in_degree, tags, node_type
        )

        # Apply bias
        adjusted_total = original_total + bias_value
        is_candidate = bias_value > 0

        if is_candidate:
            bias_applied_count += 1

        # Check basin attractor (annotation only - does NOT affect adjusted_total)
        energy_rank = energy_ranks.get(symbol, 1.0)
        is_basin = is_basin_attractor(out_degree, in_degree, original_total, energy_rank)

        if is_basin:
            basin_count += 1

        biased_states[symbol] = AttractorBiasedState(
            symbol=symbol,
            original_total=original_total,
            attractor_bias=bias_value,
            adjusted_total=adjusted_total,
            is_attractor_candidate=is_candidate,
            bias_reason=bias_reason,
            out_degree=out_degree,
            in_degree=in_degree,
            tags=list(tags),
            is_basin=is_basin,  # Design 94 - annotation only
        )

        if bias_applied_count % 100 == 0 and bias_applied_count > 0:
            logger.info("Processed %d symbols (%d with bias, %d basin)", len(biased_states), bias_applied_count, basin_count)

    logger.info(
        "Applied attractor bias to %d/%d symbols (%.1f%%), basin annotations: %d (%.1f%%)",
        bias_applied_count,
        len(biased_states),
        100.0 * bias_applied_count / len(biased_states) if biased_states else 0.0,
        basin_count,
        100.0 * basin_count / len(biased_states) if biased_states else 0.0,
    )

    # Write output
    output_data = {
        "metadata": {
            "source": "attractor_bias_injection",
            "design": "Design 90 - Fix No Attractors Problem + Design 94 Basin Annotations",
            "total_symbols": len(biased_states),
            "bias_applied_count": bias_applied_count,
            "basin_count": basin_count,  # Design 94 - annotation layer
            "bias_coefficient": ATTRACTOR_BIAS,
            "terminal_tags": list(TERMINAL_TAGS),
            "utility_tags": list(UTILITY_TAGS),
            "basin_thresholds": {  # Design 94 - annotation layer config
                "convergence_ratio": BASIN_CONVERGENCE_RATIO,
                "min_in_degree": BASIN_MIN_IN_DEGREE,
                "max_out_degree": BASIN_MAX_OUT_DEGREE,
                "energy_rank_threshold": BASIN_ENERGY_RANK_THRESHOLD,
            },
        },
        "states": {
            symbol: asdict(state)
            for symbol, state in biased_states.items()
        }
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info("Wrote attractor-biased energy states to %s", output_path)

    return bias_applied_count

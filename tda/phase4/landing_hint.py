"""Landing Hint System for TDA Navigation

@module quro.tda.phase4.landing_hint
@intent Provide selective code entry points from TDA paths
@design Design 98: Landing Hint System

This module implements a lightweight, read-only scoring layer that guides
developers and AI agents to the most relevant code entry points from TDA
navigation results.

Key Properties:
- Pure observer pattern (zero graph mutation)
- Uses only structural signals (energy, fanout, convergence, position)
- No semantic scoring (avoids hallucination)
- Preserves CQE/TDA convergence guarantees
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class LandingHint:
    """Landing hint for a code symbol.

    Attributes:
        symbol: Symbol ID
        file: File path
        line: Line number
        priority: Priority score [0, 1] (higher = more important)
        why_here: List of reasons why this node is worth inspecting
    """
    symbol: str
    file: str
    line: int
    priority: float
    why_here: List[str]


def compute_landing_hint(
    node_state: dict,
    path_rank: int,
    avg_energy: float,
) -> dict:
    """Compute landing hint score for a node.

    Pure read-only scoring. No mutation to graph.

    Args:
        node_state: Node state dict with energy, in_degree, out_degree
        path_rank: Position in path (0-indexed)
        avg_energy: Average energy across all nodes in path

    Returns:
        dict: {"score": float, "reasons": list[str]}
    """
    # Extract node properties
    energy = node_state.get("energy", 0.0)
    out_degree = node_state.get("out_degree", 0)
    in_degree = node_state.get("in_degree", 0)

    # --- Normalize ---
    energy_score = energy / (avg_energy + 1e-6)
    fanout_score = min(out_degree / 20.0, 1.0)  # cap at 20
    convergence_score = in_degree / (out_degree + 1.0)

    # --- Position bias ---
    # Prefer middle of path (not entry, not leaf)
    position_score = 1.0 / (1.0 + path_rank)

    # --- Combined score ---
    score = (
        0.4 * energy_score +
        0.2 * fanout_score +
        0.2 * convergence_score +
        0.2 * position_score
    )

    # --- Reason extraction ---
    reasons = []
    if energy_score > 1.3:
        reasons.append("high_energy")
    if out_degree > 15:
        reasons.append("high_fanout")
    if convergence_score > 2.0:
        reasons.append("convergence_point")
    if path_rank <= 2:
        reasons.append("early_path")

    return {
        "score": round(score, 3),
        "reasons": reasons
    }


def build_landing_hint(
    symbol: str,
    node_state: dict,
    path_rank: int,
    avg_energy: float,
    symbol_metadata: Optional[dict] = None,
) -> LandingHint:
    """Build landing hint for a single node.

    Args:
        symbol: Symbol ID
        node_state: Node state dict
        path_rank: Position in path
        avg_energy: Average energy across path
        symbol_metadata: Optional metadata with file/line info

    Returns:
        LandingHint object
    """
    hint = compute_landing_hint(node_state, path_rank, avg_energy)

    # Extract file and line from metadata if available
    file_path = "unknown"
    line_number = 0

    if symbol_metadata:
        file_path = symbol_metadata.get("file", "unknown")
        line_number = symbol_metadata.get("line", 0)

    return LandingHint(
        symbol=symbol,
        file=file_path,
        line=line_number,
        priority=hint["score"],
        why_here=hint["reasons"]
    )


def generate_landing_hints(
    path: List[str],
    field_data,
    symbol_resolver=None,
    top_k: int = 3,
) -> List[dict]:
    """Generate top-K landing hints for a trajectory path.

    Args:
        path: List of symbol IDs forming the trajectory
        field_data: FieldData object with node states
        symbol_resolver: Optional function to resolve symbol metadata (file, line)
        top_k: Number of top hints to return (default: 3)

    Returns:
        List of landing hint dicts, sorted by priority (highest first)
    """
    if not path:
        return []

    # Compute average energy for normalization
    energies = []
    for symbol in path:
        try:
            state = field_data.get_state(symbol)
            energies.append(state.get("energy", 0.0))
        except KeyError:
            energies.append(0.0)

    avg_energy = sum(energies) / len(energies) if energies else 1.0

    # Build hints for each node
    hints = []
    for rank, symbol in enumerate(path):
        try:
            state = field_data.get_state(symbol)

            # Add out_degree and in_degree to state if not present
            # (computed from adjacency)
            if "out_degree" not in state:
                neighbors = field_data.get_neighbors(symbol, k=100)
                state["out_degree"] = len(neighbors)

            if "in_degree" not in state:
                # Count incoming edges (expensive, so we estimate)
                # For now, use a heuristic based on energy
                state["in_degree"] = int(state.get("energy", 0.0) / 2.0)

            # Resolve symbol metadata
            metadata = None
            if symbol_resolver:
                metadata = symbol_resolver(symbol)

            hint = build_landing_hint(
                symbol=symbol,
                node_state=state,
                path_rank=rank,
                avg_energy=avg_energy,
                symbol_metadata=metadata,
            )

            hints.append({
                "symbol": hint.symbol,
                "file": hint.file,
                "line": hint.line,
                "priority": hint.priority,
                "why_here": hint.why_here,
            })
        except KeyError:
            # Symbol not found in field data, skip
            continue

    # Sort by priority and return top-K
    hints.sort(key=lambda h: h["priority"], reverse=True)
    return hints[:top_k]

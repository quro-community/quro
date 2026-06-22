"""Pass 2: Structural Analysis

@module quro.tda.phase2_5.pass2_structural_analysis
@intent Compute structural metrics (in-degree, out-degree, complexity) to derive
        "gravity" (potential wells) and "mass" (centrality).

        High in-degree = many callers = deep gravity well = low potential
        High complexity = high friction = resistance to traversal
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StructuralMetrics:
    """Structural metrics for a symbol.

    Attributes:
        symbol: Symbol ID
        in_degree: Number of incoming edges (callers)
        out_degree: Number of outgoing edges (callees)
        gravity_score: Gravity strength [0, 1] (inverse sigmoid of in-degree)
        mass: Centrality measure [0, 1] (normalized degree)
        complexity: Cyclomatic complexity (if available)
        nesting_depth: Nesting depth (if available)
        friction: Friction coefficient [0, 1] (from complexity)
    """
    symbol: str
    in_degree: int
    out_degree: int
    gravity_score: float
    mass: float
    complexity: int
    nesting_depth: int
    friction: float


def compute_gravity_score(in_degree: int) -> float:
    """Compute gravity score from in-degree.

    Formula: gravity = 1 / (1 + exp(-in_degree / 10))

    High in-degree → gravity ≈ 1.0 (deep well)
    Low in-degree → gravity ≈ 0.5 (flat)

    Args:
        in_degree: Number of incoming edges

    Returns:
        Gravity score [0, 1]
    """
    import math
    return 1.0 / (1.0 + math.exp(-in_degree / 10.0))


def compute_mass(in_degree: int, out_degree: int, max_degree: int) -> float:
    """Compute mass (centrality) from degree.

    Formula: mass = (in_degree + out_degree) / (2 * max_degree)

    Args:
        in_degree: Number of incoming edges
        out_degree: Number of outgoing edges
        max_degree: Maximum degree in graph (for normalization)

    Returns:
        Mass [0, 1]
    """
    if max_degree == 0:
        return 0.0
    total_degree = in_degree + out_degree
    return min(1.0, total_degree / (2.0 * max_degree))


def compute_friction(complexity: int) -> float:
    """Compute friction from cyclomatic complexity.

    Formula: friction = tanh(complexity / 10)

    High complexity → high friction (hard to traverse)
    Low complexity → low friction (easy to traverse)

    Args:
        complexity: Cyclomatic complexity

    Returns:
        Friction [0, 1]
    """
    import math
    return math.tanh(complexity / 10.0)


def analyze_structure(
    registry_db_path: Path,
    output_path: Path,
) -> Dict[str, StructuralMetrics]:
    """Analyze structural properties of all symbols.

    Args:
        registry_db_path: Path to registry.db
        output_path: Output path for structural_metrics.json

    Returns:
        Dict mapping symbol → StructuralMetrics
    """
    logger.info("Analyzing structural metrics from %s", registry_db_path)

    # Load registry
    from index_builder.adapters.sqlite import SQLiteRegistryAdapter
    adapter = SQLiteRegistryAdapter(db_path=registry_db_path)
    all_nodes = adapter.get_all_nodes()
    symbols = [n for n in all_nodes if n.type == "symbol"]

    logger.info("Analyzing %d symbols", len(symbols))

    # Compute in-degree and out-degree for each symbol
    in_degree_map: Dict[str, int] = {}
    out_degree_map: Dict[str, int] = {}

    # First pass: count outgoing edges
    for symbol_node in symbols:
        symbol_id = symbol_node.id
        out_edges = adapter.get_edges_from(symbol_id)
        out_degree_map[symbol_id] = len(out_edges)

        # Initialize in-degree
        in_degree_map[symbol_id] = 0

    # Second pass: count incoming edges by traversing all outgoing edges
    for symbol_node in symbols:
        symbol_id = symbol_node.id
        out_edges = adapter.get_edges_from(symbol_id)

        for edge in out_edges:
            target_id = edge.dst
            if target_id in in_degree_map:
                in_degree_map[target_id] += 1

    # Find max degree for normalization
    max_degree = max(
        max(in_degree_map.values(), default=0),
        max(out_degree_map.values(), default=0),
    )

    logger.info("Max degree in graph: %d", max_degree)

    # Compute structural metrics
    metrics: Dict[str, StructuralMetrics] = {}

    for symbol_node in symbols:
        symbol_id = symbol_node.id
        in_deg = in_degree_map.get(symbol_id, 0)
        out_deg = out_degree_map.get(symbol_id, 0)

        # Get complexity from metadata (if available)
        metadata = symbol_node.metadata or {}
        complexity = metadata.get("cyclomatic_complexity", 1)
        nesting_depth = metadata.get("nesting_depth", 1)

        # Compute derived metrics
        gravity = compute_gravity_score(in_deg)
        mass = compute_mass(in_deg, out_deg, max_degree)
        friction = compute_friction(complexity)

        metrics[symbol_id] = StructuralMetrics(
            symbol=symbol_id,
            in_degree=in_deg,
            out_degree=out_deg,
            gravity_score=round(gravity, 4),
            mass=round(mass, 4),
            complexity=complexity,
            nesting_depth=nesting_depth,
            friction=round(friction, 4),
        )

    # Statistics
    high_gravity = sum(1 for m in metrics.values() if m.gravity_score >= 0.8)
    high_mass = sum(1 for m in metrics.values() if m.mass >= 0.5)
    high_friction = sum(1 for m in metrics.values() if m.friction >= 0.5)

    logger.info(
        "Structural analysis: %d symbols (high gravity: %d, high mass: %d, high friction: %d)",
        len(metrics), high_gravity, high_mass, high_friction,
    )

    # Write to file
    output_data = {
        "metadata": {
            "source": "registry_graph",
            "total_symbols": len(metrics),
            "max_degree": max_degree,
            "high_gravity_count": high_gravity,
            "high_mass_count": high_mass,
            "high_friction_count": high_friction,
        },
        "metrics": {
            symbol: {
                "in_degree": m.in_degree,
                "out_degree": m.out_degree,
                "gravity_score": m.gravity_score,
                "mass": m.mass,
                "complexity": m.complexity,
                "nesting_depth": m.nesting_depth,
                "friction": m.friction,
            }
            for symbol, m in metrics.items()
        }
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info("Wrote structural metrics to %s", output_path)
    return metrics

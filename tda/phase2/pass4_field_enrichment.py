"""
Phase-2 Pass 4: Field Enrichment

Adds energy-based field metrics to manifold states using Phase-3.5 Kernel.
"""

from typing import List, Dict, Tuple
from pathlib import Path
import logging

from .schema import SymbolManifoldState
from ..phase3_5_kernel import EnergyFunctional
from ..phase3_5_kernel.field_kernel import FieldKernel

logger = logging.getLogger(__name__)


def build_neighbor_index(
    manifold_states: List[SymbolManifoldState],
) -> Dict[str, List[Tuple[str, SymbolManifoldState]]]:
    """Build neighbor index from manifold states.

    For now, use simple heuristic: symbols in same category are neighbors.
    In production, this should use actual graph edges from Phase-1.
    """
    # Group by primary category
    category_groups: Dict[str, List[SymbolManifoldState]] = {}

    for sms in manifold_states:
        if not sms.category_coupling:
            continue

        # Get primary category (highest coupling)
        primary_cat = max(sms.category_coupling.items(), key=lambda x: x[1])[0]

        if primary_cat not in category_groups:
            category_groups[primary_cat] = []
        category_groups[primary_cat].append(sms)

    # Build neighbor index
    neighbors_map: Dict[str, List[Tuple[str, SymbolManifoldState]]] = {}

    for sms in manifold_states:
        if not sms.category_coupling:
            neighbors_map[sms.symbol] = []
            continue

        primary_cat = max(sms.category_coupling.items(), key=lambda x: x[1])[0]

        # Neighbors = other symbols in same category (limit to 10 for performance)
        neighbors = [
            (other.symbol, other)
            for other in category_groups.get(primary_cat, [])
            if other.symbol != sms.symbol
        ][:10]

        neighbors_map[sms.symbol] = neighbors

    return neighbors_map


def enrich_with_field_metrics(
    manifold_states: List[SymbolManifoldState],
) -> List[SymbolManifoldState]:
    """Add field metrics to manifold states.

    Adds:
    - energy: {potential, kinetic, total}
    - field_role: stable_attractor/unstable_repeller/saddle_point/not_critical
    - field_magnitude: ||∇E(x)||
    - mass: importance (centrality × frequency)
    - friction: resistance to change

    Args:
        manifold_states: List of manifold states from Pass 3

    Returns:
        Enriched manifold states with field metrics
    """
    logger.info(f"Enriching {len(manifold_states)} symbols with field metrics...")

    # Initialize kernel
    energy = EnergyFunctional()
    kernel = FieldKernel(energy)

    # Build neighbor index
    neighbors_map = build_neighbor_index(manifold_states)

    # Enrich each symbol
    enriched_count = 0

    for sms in manifold_states:
        try:
            # Compute energy state
            energy_state = kernel.compute_energy_state(sms)

            # Get neighbors
            neighbors = neighbors_map.get(sms.symbol, [])

            # Compute field vector
            field_vector = kernel.compute_field_vector(sms.symbol, sms, neighbors)

            # Detect attractor type
            attractor_type = kernel.detect_attractor_type(sms.symbol, sms, neighbors)

            # Compute dynamics
            dynamics = kernel.compute_dynamics_state(sms, field_vector)

            # Add to manifold state
            sms.energy = {
                "potential": energy_state.potential,
                "kinetic": energy_state.kinetic,
                "total": energy_state.total,
            }
            sms.field_role = attractor_type
            sms.field_magnitude = field_vector.magnitude
            sms.mass = dynamics.mass
            sms.friction = dynamics.friction

            enriched_count += 1

        except Exception as e:
            logger.warning(f"Failed to enrich {sms.symbol}: {e}")
            # Set default values
            sms.energy = {"potential": 0.0, "kinetic": 0.0, "total": 0.0}
            sms.field_role = "not_critical"
            sms.field_magnitude = 0.0
            sms.mass = 0.0
            sms.friction = 0.0

    logger.info(f"Enriched {enriched_count}/{len(manifold_states)} symbols with field metrics")

    return manifold_states


def main():
    """Test field enrichment."""
    from pathlib import Path
    import json

    # Load manifold states
    manifold_states_path = Path.cwd() / ".quro_context" / "tda" / "phase2" / "manifold_states.jsonl"

    if not manifold_states_path.exists():
        print(f"Error: Manifold states not found: {manifold_states_path}")
        return

    manifold_states = []
    with open(manifold_states_path) as f:
        for line in f:
            data = json.loads(line)
            sms = SymbolManifoldState(**data)
            manifold_states.append(sms)

    print(f"Loaded {len(manifold_states)} manifold states")

    # Enrich
    enriched = enrich_with_field_metrics(manifold_states)

    # Show sample
    for sms in enriched[:3]:
        print(f"\n{sms.symbol}:")
        print(f"  Energy: {sms.energy}")
        print(f"  Field role: {sms.field_role}")
        print(f"  Field magnitude: {sms.field_magnitude:.3f}")
        print(f"  Mass: {sms.mass:.3f}")
        print(f"  Friction: {sms.friction:.3f}")


if __name__ == "__main__":
    main()

"""
Runtime API: Energy-based vector field navigation API.

Implements the 5 core APIs from Design 79, powered by the field kernel from Design 80.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np

from ..phase2.schema import SymbolManifoldState
from . import EnergyFunctional
from .field_kernel import FieldKernel
from .trajectory_simulator import TrajectorySimulator


class VectorFieldAPI:
    """Vector field navigation API powered by field physics kernel."""

    def __init__(self, manifold_states_path: Path):
        """Initialize API with manifold states.

        Args:
            manifold_states_path: Path to Phase-2 manifold states JSONL
        """
        self.manifold_states_path = manifold_states_path

        # Initialize kernel components
        self.energy = EnergyFunctional()
        self.kernel = FieldKernel(self.energy)
        self.simulator = TrajectorySimulator(self.energy)

        # Load manifold states
        self.states: Dict[str, SymbolManifoldState] = {}
        self.neighbors: Dict[str, List[str]] = {}
        self._load_states()

    def _load_states(self):
        """Load manifold states from Phase-2 output."""
        with open(self.manifold_states_path) as f:
            for line in f:
                data = json.loads(line)
                sms = SymbolManifoldState(**data)
                self.states[sms.symbol] = sms

                # Build neighbor index from category coupling
                # In production, this should use actual graph edges
                self.neighbors[sms.symbol] = []

    def get_field_vector(self, symbol: str) -> Dict:
        """Get field vector state at a symbol.

        Args:
            symbol: Symbol ID

        Returns:
            Dictionary with vector, energy, gradient, and dynamics
        """
        if symbol not in self.states:
            return {"error": f"Symbol not found: {symbol}"}

        sms = self.states[symbol]

        # Get neighbors (simplified: use all states as potential neighbors)
        neighbor_ids = list(self.states.keys())[:10]  # Limit to 10 for performance
        neighbors = [(nid, self.states[nid]) for nid in neighbor_ids if nid != symbol]

        # Compute field vector
        field_vector = self.kernel.compute_field_vector(symbol, sms, neighbors)

        # Compute energy state
        energy_state = self.kernel.compute_energy_state(sms)

        # Compute dynamics state
        dynamics_state = self.kernel.compute_dynamics_state(sms, field_vector)

        # Compute gradient
        gradient = self.kernel.compute_gradient(symbol, sms, neighbors)

        return {
            "symbol": symbol,
            "vector": {
                "direction": field_vector.direction.tolist(),
                "magnitude": float(field_vector.magnitude),
            },
            "energy": {
                "potential": energy_state.potential,
                "kinetic": energy_state.kinetic,
                "total": energy_state.total,
            },
            "energy_gradient": {
                f"dE/d{i}": float(gradient[i]) for i in range(len(gradient))
            },
            "dynamics": {
                "mass": dynamics_state.mass,
                "friction": dynamics_state.friction,
                "acceleration": dynamics_state.acceleration.tolist(),
            },
        }

    def query_next_best_nodes(
        self, from_symbol: str, intent: Optional[str] = None, max_candidates: int = 5
    ) -> Dict:
        """Query best next symbols to navigate to.

        Args:
            from_symbol: Current symbol
            intent: Optional intent description
            max_candidates: Maximum number of candidates to return

        Returns:
            Dictionary with ranked candidates
        """
        if from_symbol not in self.states:
            return {"error": f"Symbol not found: {from_symbol}"}

        from_sms = self.states[from_symbol]
        E_current = self.energy.compute_energy(from_sms)

        # Get potential neighbors (simplified)
        neighbor_ids = list(self.states.keys())[:20]
        candidates = []

        for neighbor_id in neighbor_ids:
            if neighbor_id == from_symbol:
                continue

            neighbor_sms = self.states[neighbor_id]

            # Compute energy transition
            transition = self.kernel.compute_transition_energy(from_sms, neighbor_sms)

            # Compute trajectory cost
            cost = self.simulator.compute_trajectory_cost(from_sms, neighbor_sms)

            # Compute force alignment (transition smoothness)
            # Use energy gradient magnitude as alignment metric
            # Lower gradient = smoother transition = higher alignment
            E_from = self.energy.compute_energy(from_sms)
            E_to = self.energy.compute_energy(neighbor_sms)
            gradient_magnitude = abs(E_to - E_from)

            # Normalize to [0,1] where 1 = perfect alignment (no gradient)
            force_alignment = float(np.exp(-gradient_magnitude))

            # Recommendation
            if transition["delta_E"] < 0 and cost["total_cost"] < 0.5:
                recommendation = "favorable_transition"
            elif transition["delta_E"] > 0.5:
                recommendation = "uphill_transition"
            else:
                recommendation = "neutral_transition"

            candidates.append({
                "symbol": neighbor_id,
                "energy_transition": transition,
                "force_alignment": force_alignment,
                "trajectory_cost": cost,
                "recommendation": recommendation,
            })

        # Sort by total cost (ascending)
        candidates.sort(key=lambda c: c["trajectory_cost"]["total_cost"])

        return {
            "from": from_symbol,
            "E_current": E_current,
            "candidates": candidates[:max_candidates],
        }

    def simulate_trajectory(self, trajectory: List[str], intent: Optional[str] = None) -> Dict:
        """Simulate trajectory with energy conservation.

        Args:
            trajectory: List of symbol IDs
            intent: Optional intent description

        Returns:
            Dictionary with energy dynamics and stability
        """
        # Validate symbols
        for symbol in trajectory:
            if symbol not in self.states:
                return {"error": f"Symbol not found: {symbol}"}

        # Get manifold states
        path = [self.states[symbol] for symbol in trajectory]

        # Simulate
        result = self.simulator.simulate_trajectory(path)

        # Add trajectory info
        result["trajectory"] = trajectory
        result["intent"] = intent

        return result

    def compute_field_gradient(self, symbol: str, direction: Optional[str] = None) -> Dict:
        """Compute field gradient at a symbol.

        Args:
            symbol: Symbol ID
            direction: Optional direction to compute gradient in

        Returns:
            Dictionary with gradient information
        """
        if symbol not in self.states:
            return {"error": f"Symbol not found: {symbol}"}

        sms = self.states[symbol]

        # Get neighbors
        neighbor_ids = list(self.states.keys())[:10]
        neighbors = [(nid, self.states[nid]) for nid in neighbor_ids if nid != symbol]

        # Compute gradient
        gradient = self.kernel.compute_gradient(symbol, sms, neighbors)

        # Find steepest descent
        if len(gradient) > 0:
            steepest_idx = np.argmax(np.abs(gradient))
            steepest_magnitude = float(gradient[steepest_idx])
        else:
            steepest_idx = 0
            steepest_magnitude = 0.0

        return {
            "symbol": symbol,
            "gradient": {
                f"dE/d{i}": float(gradient[i]) for i in range(len(gradient))
            },
            "steepest_descent": {
                "direction": f"axis_{steepest_idx}",
                "magnitude": steepest_magnitude,
            },
        }

    def detect_attractors(self, region: Optional[str] = None) -> Dict:
        """Detect attractors and repellers in a region.

        Args:
            region: Optional region filter

        Returns:
            Dictionary with attractors, repellers, and saddle points
        """
        attractors = []
        repellers = []
        saddle_points = []

        # Analyze all symbols (or filtered by region)
        for symbol, sms in self.states.items():
            # Get neighbors
            neighbor_ids = list(self.states.keys())[:10]
            neighbors = [(nid, self.states[nid]) for nid in neighbor_ids if nid != symbol]

            # Detect attractor type
            attractor_type = self.kernel.detect_attractor_type(symbol, sms, neighbors)

            if attractor_type == "stable_attractor":
                # Compute basin properties
                E_value = self.energy.compute_energy(sms)
                gradient = self.kernel.compute_gradient(symbol, sms, neighbors)
                gradient_norm = float(np.linalg.norm(gradient))

                attractors.append({
                    "symbol": symbol,
                    "type": "stable_attractor",
                    "energy_properties": {
                        "E_value": E_value,
                        "gradient_norm": gradient_norm,
                    },
                    "basin_properties": {
                        "basin_depth": 1.0 - E_value,  # Simplified
                        "basin_size": len(neighbors),
                    },
                })

            elif attractor_type == "unstable_repeller":
                repellers.append({
                    "symbol": symbol,
                    "type": "unstable_repeller",
                })

            elif attractor_type == "saddle_point":
                saddle_points.append({
                    "symbol": symbol,
                    "type": "saddle_point",
                })

        return {
            "region": region or "all",
            "attractors": attractors[:10],  # Limit output
            "repellers": repellers[:10],
            "saddle_points": saddle_points[:10],
        }


def main():
    """CLI entry point for testing."""
    workspace_root = Path.cwd()
    manifold_states_path = workspace_root / ".quro_context" / "tda" / "phase2" / "manifold_states.jsonl"

    if not manifold_states_path.exists():
        print(f"Error: Manifold states not found: {manifold_states_path}")
        return

    # Initialize API
    api = VectorFieldAPI(manifold_states_path)

    # Test get_field_vector
    print("Testing get_field_vector...")
    result = api.get_field_vector("sym::main")
    print(json.dumps(result, indent=2))
    print()

    # Test query_next_best_nodes
    print("Testing query_next_best_nodes...")
    result = api.query_next_best_nodes("sym::main", max_candidates=3)
    print(json.dumps(result, indent=2))
    print()

    # Test detect_attractors
    print("Testing detect_attractors...")
    result = api.detect_attractors()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

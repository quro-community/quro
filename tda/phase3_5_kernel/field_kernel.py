"""
Field Kernel: Core field physics implementation.

Implements F(x) = -∇E(x) and related field operations.
"""

from typing import Dict, List, Tuple
import numpy as np

from ..phase2.schema import SymbolManifoldState
from . import EnergyFunctional, FieldVector, EnergyState, DynamicsState


class FieldKernel:
    """Core field physics kernel.

    Implements:
    - Vector field F(x) = -∇E(x)
    - Gradient computation via finite differences
    - Attractor detection via critical point analysis
    """

    def __init__(self, energy_functional: EnergyFunctional):
        self.energy = energy_functional
        self._energy_cache: Dict[str, float] = {}
        self._gradient_cache: Dict[str, np.ndarray] = {}

    def compute_gradient(
        self,
        symbol: str,
        sms: SymbolManifoldState,
        neighbors: List[Tuple[str, SymbolManifoldState]],
    ) -> np.ndarray:
        """Compute ∇E(x) using finite differences.

        Args:
            symbol: Symbol ID
            sms: Symbol Manifold State
            neighbors: List of (neighbor_id, neighbor_sms) tuples

        Returns:
            Gradient vector
        """
        # Check cache
        if symbol in self._gradient_cache:
            return self._gradient_cache[symbol]

        # Compute energy at current symbol
        E_current = self.energy.compute_energy(sms)

        # Compute gradient using finite differences
        gradient = []
        for neighbor_id, neighbor_sms in neighbors:
            E_neighbor = self.energy.compute_energy(neighbor_sms)
            dE = E_neighbor - E_current
            gradient.append(dE)

        gradient_array = np.array(gradient) if gradient else np.zeros(1)

        # Cache result
        self._gradient_cache[symbol] = gradient_array

        return gradient_array

    def compute_field_vector(
        self,
        symbol: str,
        sms: SymbolManifoldState,
        neighbors: List[Tuple[str, SymbolManifoldState]],
    ) -> FieldVector:
        """Compute F(x) = -∇E(x).

        Args:
            symbol: Symbol ID
            sms: Symbol Manifold State
            neighbors: List of neighbors

        Returns:
            FieldVector with direction and magnitude
        """
        gradient = self.compute_gradient(symbol, sms, neighbors)

        # Vector direction = negative gradient (toward lower energy)
        gradient_norm = np.linalg.norm(gradient)
        if gradient_norm > 1e-10:
            direction = -gradient / gradient_norm
        else:
            direction = np.zeros_like(gradient)

        magnitude = gradient_norm

        return FieldVector(direction=direction, magnitude=magnitude)

    def compute_energy_state(self, sms: SymbolManifoldState) -> EnergyState:
        """Compute complete energy state.

        Args:
            sms: Symbol Manifold State

        Returns:
            EnergyState with potential, kinetic, and total energy
        """
        # Potential energy = E(x)
        potential = self.energy.compute_energy(sms)

        # Kinetic energy = ½ m v²
        # Use frequency as proxy for velocity
        mass = self.energy.compute_mass(sms)
        velocity = min(1.0, sms.temporal_signature.frequency / 1000.0)
        kinetic = 0.5 * mass * (velocity ** 2)

        total = potential + kinetic

        return EnergyState(potential=potential, kinetic=kinetic, total=total)

    def compute_dynamics_state(
        self,
        sms: SymbolManifoldState,
        field_vector: FieldVector,
    ) -> DynamicsState:
        """Compute dynamics state (mass, friction, acceleration).

        Args:
            sms: Symbol Manifold State
            field_vector: Field vector at this symbol

        Returns:
            DynamicsState
        """
        mass = self.energy.compute_mass(sms)
        friction = self.energy.compute_friction(sms)

        # F = ma → a = F/m
        # F = field_vector.magnitude * field_vector.direction
        force = field_vector.magnitude * field_vector.direction
        acceleration = force / (mass + 1e-10)  # Avoid division by zero

        return DynamicsState(mass=mass, friction=friction, acceleration=acceleration)

    def detect_attractor_type(
        self,
        symbol: str,
        sms: SymbolManifoldState,
        neighbors: List[Tuple[str, SymbolManifoldState]],
    ) -> str:
        """Detect attractor type from energy landscape.

        Args:
            symbol: Symbol ID
            sms: Symbol Manifold State
            neighbors: List of neighbors

        Returns:
            Attractor type: stable_attractor/unstable_repeller/saddle_point/not_critical_point
        """
        gradient = self.compute_gradient(symbol, sms, neighbors)
        gradient_norm = np.linalg.norm(gradient)

        # Check if critical point (∇E ≈ 0)
        if gradient_norm > 0.1:
            return "not_critical_point"

        # Compute Hessian (second derivatives) via finite differences
        hessian = self._compute_hessian(symbol, sms, neighbors)

        # Compute eigenvalues
        try:
            eigenvalues = np.linalg.eigvals(hessian)
        except np.linalg.LinAlgError:
            return "unknown"

        # Classify based on eigenvalues
        if all(ev > 0 for ev in eigenvalues):
            return "stable_attractor"  # Local minimum
        elif all(ev < 0 for ev in eigenvalues):
            return "unstable_repeller"  # Local maximum
        else:
            return "saddle_point"  # Mixed eigenvalues

    def _compute_hessian(
        self,
        symbol: str,
        sms: SymbolManifoldState,
        neighbors: List[Tuple[str, SymbolManifoldState]],
    ) -> np.ndarray:
        """Compute Hessian matrix (second derivatives).

        Args:
            symbol: Symbol ID
            sms: Symbol Manifold State
            neighbors: List of neighbors

        Returns:
            Hessian matrix
        """
        n = len(neighbors)
        if n == 0:
            return np.zeros((1, 1))

        # Simplified Hessian: diagonal approximation
        # d²E/dx² ≈ (E(x+h) - 2E(x) + E(x-h)) / h²
        E_current = self.energy.compute_energy(sms)

        hessian = np.zeros((n, n))
        for i, (neighbor_id, neighbor_sms) in enumerate(neighbors):
            E_neighbor = self.energy.compute_energy(neighbor_sms)
            # Diagonal element (second derivative)
            hessian[i, i] = E_neighbor - E_current

        return hessian

    def compute_transition_energy(
        self,
        from_sms: SymbolManifoldState,
        to_sms: SymbolManifoldState,
    ) -> Dict[str, float]:
        """Compute energy transition between two symbols.

        Args:
            from_sms: Source symbol manifold state
            to_sms: Target symbol manifold state

        Returns:
            Dictionary with transition energy metrics
        """
        E_from = self.energy.compute_energy(from_sms)
        E_to = self.energy.compute_energy(to_sms)

        delta_E = E_to - E_from

        # Transition barrier (activation energy)
        # Simplified: use friction as barrier
        friction_from = self.energy.compute_friction(from_sms)
        transition_barrier = friction_from * abs(delta_E)

        return {
            "E_from": E_from,
            "E_to": E_to,
            "delta_E": delta_E,
            "transition_barrier": transition_barrier,
        }

    def clear_cache(self):
        """Clear energy and gradient caches."""
        self._energy_cache.clear()
        self._gradient_cache.clear()

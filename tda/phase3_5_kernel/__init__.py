"""
Phase-3.5 Runtime Kernel: Field Physics Layer

Unified energy-based foundation for vector field navigation.
"""

from typing import Dict, List, Tuple
import math
import numpy as np
from dataclasses import dataclass

from ..phase2.schema import SymbolManifoldState


@dataclass
class EnergyState:
    """Energy state of a symbol."""
    potential: float
    kinetic: float
    total: float


@dataclass
class FieldVector:
    """Vector field state."""
    direction: np.ndarray
    magnitude: float


@dataclass
class DynamicsState:
    """Dynamics state of a symbol."""
    mass: float
    friction: float
    acceleration: np.ndarray


class EnergyFunctional:
    """Unified energy functional for semantic field space.

    E(x) = α·Centrality(x) + β·Frequency(x) - γ·Stability(x) + δ·CouplingEntropy(x)
    """

    def __init__(
        self,
        alpha: float = 0.4,  # centrality weight
        beta: float = 0.3,   # frequency weight
        gamma: float = 0.5,  # stability weight (negative)
        delta: float = 0.2,  # coupling entropy weight
    ):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.delta = delta

    def compute_energy(self, sms: SymbolManifoldState) -> float:
        """Compute E(x) for a symbol.

        Args:
            sms: Symbol Manifold State from Phase-2

        Returns:
            Energy value E(x)
        """
        # Normalize inputs to [0,1]
        centrality = sms.topology.centrality
        frequency = min(1.0, sms.temporal_signature.frequency / 1000.0)
        stability = sms.stability.tau_persistence
        coupling_entropy = self._compute_coupling_entropy(sms.category_coupling)

        # Energy functional
        E = (
            self.alpha * centrality +
            self.beta * frequency -
            self.gamma * stability +
            self.delta * coupling_entropy
        )

        return max(0.0, E)  # Energy cannot be negative

    def _compute_coupling_entropy(self, coupling: Dict[str, float]) -> float:
        """Compute Shannon entropy of coupling distribution.

        Args:
            coupling: Category coupling dictionary

        Returns:
            Normalized entropy [0,1]
        """
        if not coupling:
            return 0.0

        total = sum(coupling.values())
        if total == 0:
            return 0.0

        # Normalize to probability distribution
        probs = [v / total for v in coupling.values()]

        # Shannon entropy: -Σ p_i log2(p_i)
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)

        # Normalize to [0,1] (max entropy = log2(n))
        max_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0

        return entropy / max_entropy if max_entropy > 0 else 0.0

    def compute_mass(self, sms: SymbolManifoldState) -> float:
        """Compute mass (importance) of a symbol.

        Args:
            sms: Symbol Manifold State

        Returns:
            Mass value [0,1]
        """
        # Mass = centrality × frequency (normalized)
        centrality = sms.topology.centrality
        frequency = min(1.0, sms.temporal_signature.frequency / 1000.0)

        return (centrality + frequency) / 2.0

    def compute_friction(self, sms: SymbolManifoldState) -> float:
        """Compute friction (resistance to change).

        Args:
            sms: Symbol Manifold State

        Returns:
            Friction coefficient [0,1]
        """
        # Friction = inverse of stability, amplified by structural noise
        base_friction = 1.0 - sms.stability.tau_persistence
        noise_amplification = 1.0 + sms.stability.structural_noise

        return min(1.0, base_friction * noise_amplification)

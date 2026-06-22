"""Trajectory Simulator — Path-Level Memory and Coherence Analysis

@module quro.tda.phase4.trajectory_simulator
@intent Provide trajectory-aware scoring with coherence penalty and energy conservation
        validation. Implements Phase 3 of Design 85 - Field Recalibration.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrajectoryState:
    """State at a point along a trajectory.

    Attributes:
        symbol: Symbol ID
        energy: Total energy at this point
        friction: Friction coefficient
        direction: Field direction vector (128-dim)
        position: Manifold position (3D)
    """
    symbol: str
    energy: float
    friction: float
    direction: List[float]
    position: Tuple[float, float, float]


@dataclass(frozen=True)
class TrajectoryAnalysis:
    """Analysis result for a trajectory.

    Attributes:
        path: List of symbol IDs forming the trajectory
        total_cost: Total transition cost
        coherence_penalty: Coherence penalty (direction variance)
        total_score: Total score (cost + coherence penalty)
        energy_conservation: Energy conservation score [0, 1]
        is_stable: Whether trajectory is Lyapunov stable
        states: List of TrajectoryState at each point
    """
    path: List[str]
    total_cost: float
    coherence_penalty: float
    total_score: float
    energy_conservation: float
    is_stable: bool
    states: List[TrajectoryState]


class TrajectorySimulator:
    """Trajectory simulator with coherence analysis and energy conservation."""

    def __init__(
        self,
        coherence_weight: float = 0.5,
        energy_tolerance: float = 0.1,
    ):
        """Initialize trajectory simulator.

        Args:
            coherence_weight: Weight for coherence penalty (default: 0.5)
            energy_tolerance: Tolerance for energy conservation (default: 0.1)
        """
        self.coherence_weight = coherence_weight
        self.energy_tolerance = energy_tolerance

    def compute_trajectory_coherence(
        self,
        direction_vectors: List[List[float]]
    ) -> float:
        """Compute coherence penalty for a trajectory."""
        if len(direction_vectors) < 2:
            return 0.0

        mat = np.array(direction_vectors)
        variance = np.var(mat, axis=0).mean()
        return self.coherence_weight * variance

    def compute_energy_conservation(
        self,
        energies: List[float]
    ) -> float:
        """Compute energy conservation score for a trajectory."""
        if len(energies) < 2:
            return 1.0

        total_change = abs(energies[-1] - energies[0])
        fluctuations = sum(
            abs(energies[i+1] - energies[i])
            for i in range(len(energies) - 1)
        )

        if fluctuations == 0:
            return 1.0

        ratio = total_change / fluctuations
        return min(1.0, ratio)

    def check_lyapunov_stability(
        self,
        energies: List[float],
        threshold: float = 0.5
    ) -> bool:
        """Check Lyapunov stability of trajectory."""
        if len(energies) < 2:
            return True

        for i in range(len(energies) - 1):
            delta = energies[i+1] - energies[i]
            if delta > threshold:
                return False

        return True

    def simulate_trajectory(
        self,
        states: List[TrajectoryState],
        transition_costs: List[float],
    ) -> TrajectoryAnalysis:
        """Simulate and analyze a trajectory."""
        if len(states) < 2:
            return TrajectoryAnalysis(
                path=[s.symbol for s in states],
                total_cost=0.0,
                coherence_penalty=0.0,
                total_score=0.0,
                energy_conservation=1.0,
                is_stable=True,
                states=states,
            )

        path = [s.symbol for s in states]
        direction_vectors = [s.direction for s in states]
        energies = [s.energy for s in states]

        coherence_penalty = self.compute_trajectory_coherence(direction_vectors)
        total_cost = sum(transition_costs)
        total_score = total_cost + coherence_penalty
        energy_conservation = self.compute_energy_conservation(energies)
        is_stable = self.check_lyapunov_stability(energies)

        return TrajectoryAnalysis(
            path=path,
            total_cost=total_cost,
            coherence_penalty=coherence_penalty,
            total_score=total_score,
            energy_conservation=energy_conservation,
            is_stable=is_stable,
            states=states,
        )

    def compare_trajectories(
        self,
        trajectory_a: TrajectoryAnalysis,
        trajectory_b: TrajectoryAnalysis,
    ) -> str:
        """Compare two trajectories and return the better one."""
        if trajectory_a.is_stable and not trajectory_b.is_stable:
            return "a"
        if trajectory_b.is_stable and not trajectory_a.is_stable:
            return "b"

        if trajectory_a.total_score < trajectory_b.total_score:
            return "a"
        if trajectory_b.total_score < trajectory_a.total_score:
            return "b"

        if trajectory_a.energy_conservation > trajectory_b.energy_conservation:
            return "a"
        else:
            return "b"

    def validate_trajectory(
        self,
        analysis: TrajectoryAnalysis
    ) -> Tuple[bool, List[str]]:
        """Validate a trajectory against physics constraints."""
        violations = []

        if analysis.energy_conservation < (1.0 - self.energy_tolerance):
            violations.append(
                f"Poor energy conservation: {analysis.energy_conservation:.2f}"
            )

        if not analysis.is_stable:
            violations.append("Trajectory is Lyapunov unstable")

        if analysis.coherence_penalty > 1.0:
            violations.append(
                f"High coherence penalty: {analysis.coherence_penalty:.2f}"
            )

        return len(violations) == 0, violations

    def compute_path_score(
        self,
        states: List[TrajectoryState],
        transition_costs: List[float],
    ) -> float:
        """Compute total score for a path."""
        analysis = self.simulate_trajectory(states, transition_costs)
        return analysis.total_score

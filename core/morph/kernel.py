"""Morph Kernel Protocol - Pure function contract.

@module quro.core.morph.kernel
@intent Define the contract for Morph kernel implementations.
"""

from typing import Protocol, List, Tuple
from types import ManifoldNode, DriftResult, TopologicalHole, BettiResult


class MorphKernel(Protocol):
    """Pure function contract for Morph kernel.

    Invariant: All methods are pure (no side effects).

    Implementations MUST NOT:
    - Perform I/O (file, database, network)
    - Mutate input arguments
    - Access global state
    - Call logging functions
    """

    def detect_drift(
        self,
        old_node: ManifoldNode,
        new_lsh: List[int]
    ) -> DriftResult:
        """Pure: (old_state, new_lsh) → drift_result.

        Args:
            old_node: Previous manifold state
            new_lsh: Current LSH band hashes

        Returns:
            DriftResult with drift score and stability flag

        Invariant: Deterministic (same inputs → same output).
        """
        ...

    def compute_betti_1(
        self,
        nodes: List[ManifoldNode],
        k_neighbors: int = 3
    ) -> BettiResult:
        """Pure: nodes → Betti number (topological invariant).

        Args:
            nodes: List of manifold nodes
            k_neighbors: Number of neighbors for k-NN graph

        Returns:
            BettiResult with β₁ and graph statistics

        Invariant: β₁ = (edges - nodes + components) // 2
        """
        ...

    def find_topological_holes(
        self,
        nodes: List[ManifoldNode],
        grid_size: int = 10,
        density_threshold: float = 0.1
    ) -> List[TopologicalHole]:
        """Pure: nodes → low-density regions.

        Args:
            nodes: List of manifold nodes
            grid_size: Grid resolution for density analysis
            density_threshold: Relative density threshold (0.0-1.0)

        Returns:
            List of TopologicalHole (low-density regions)

        Invariant: Holes are grid cells with density < threshold * avg_density.
        """
        ...

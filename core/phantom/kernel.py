"""Phantom Kernel Protocol - Pure function contract.

@module quro.core.phantom.kernel
@intent Define the contract for Phantom kernel implementations.
"""

from typing import Protocol, List
from types import (
    ThreadSequence,
    PhantomState,
    PhantomResult,
    SimulationConfig
)


class PhantomKernel(Protocol):
    """Pure function contract for Phantom kernel.

    Invariant: All methods are pure (no side effects).

    Implementations MUST NOT:
    - Perform I/O (file, database, network)
    - Mutate input arguments
    - Access global state
    - Call logging functions
    """

    def simulate(
        self,
        threads: List[ThreadSequence],
        config: SimulationConfig
    ) -> List[PhantomResult]:
        """Pure: (threads, config) → simulation results (BFS).

        Args:
            threads: List of thread atom sequences
            config: Simulation parameters

        Returns:
            List of PhantomResult with all findings

        Invariant: BFS explores all interleavings up to max_states limit.
        """
        ...

    def initial_state(
        self,
        n_threads: int,
        resources: List[str]
    ) -> PhantomState:
        """Pure: (n_threads, resources) → initial state.

        Args:
            n_threads: Number of threads
            resources: List of resource names

        Returns:
            PhantomState with all PCs at 0 and no locks held

        Invariant: Initial state has no blocked threads.
        """
        ...

    def step(
        self,
        state: PhantomState,
        tid: int,
        threads: List[ThreadSequence]
    ) -> PhantomState | None:
        """Pure: (state, tid, threads) → next state or None.

        Args:
            state: Current simulation state
            tid: Thread ID to advance
            threads: All thread sequences

        Returns:
            New PhantomState after advancing tid, or None if blocked

        Invariant: Returns None when thread cannot advance (blocked on resource).
        """
        ...

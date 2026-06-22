"""Phantom Engine - Pure BFS interleaving simulator.

@module quro.core.phantom.engine
@intent Concrete implementation of PhantomKernel protocol.
        Pure BFS simulation with no side effects.
"""

from typing import List, Set, Tuple
from collections import deque

from types import (
    Atom,
    ThreadSequence,
    PhantomState,
    PhantomResult,
    SimulationConfig,
    Verdict
)


class PhantomEngine:
    """Phantom simulation kernel - pure implementation.

    Invariants:
    - All methods are pure (no side effects)
    - Simulation-blind (receives thread sequences, not file system)
    - No I/O (no file, database, network access)
    - No logging (pure computation only)
    """

    def simulate(
        self,
        threads: List[ThreadSequence],
        config: SimulationConfig
    ) -> List[PhantomResult]:
        """Pure: (threads, config) → simulation results (BFS).

        Performs exhaustive BFS over all possible thread interleavings
        to detect deadlock and resource leak patterns.

        Args:
            threads: List of thread atom sequences
            config: Simulation parameters

        Returns:
            List of PhantomResult with all findings
        """
        if not threads:
            return []

        # Limit threads to max_threads
        threads = threads[:config.max_threads]

        # Collect all resources referenced in atom sequences
        resources = self._collect_resources(threads)

        # Initialize BFS
        initial = self.initial_state(len(threads), resources)
        return self._explore(initial, threads, resources, config)

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
        """
        lock_map = tuple((r, None) for r in sorted(resources))
        return PhantomState(
            pcs=tuple(0 for _ in range(n_threads)),
            lock_map=lock_map,
            blocked=tuple(False for _ in range(n_threads))
        )

    def step(
        self,
        state: PhantomState,
        tid: int,
        threads: List[ThreadSequence]
    ) -> PhantomState | None:
        """Pure: (state, tid, threads) → next state or None.

        Advances thread tid by one atom. Returns None if thread is blocked.

        Args:
            state: Current simulation state
            tid: Thread ID to advance
            threads: All thread sequences

        Returns:
            New PhantomState after advancing tid, or None if blocked
        """
        pc = state.pcs[tid]
        atoms = threads[tid].atoms

        if pc >= len(atoms):
            return None

        atom = atoms[pc]
        op = atom.op
        arg = atom.arg

        lock_map = dict(state.lock_map)
        blocked = list(state.blocked)

        if op in ("ACQ", "ACQUIRE"):
            if arg and lock_map.get(arg) is not None:
                if lock_map[arg] == tid:
                    # Same-thread re-acquire (self-deadlock)
                    blocked[tid] = True
                    return PhantomState(
                        pcs=state.pcs,
                        lock_map=state.lock_map,
                        blocked=tuple(blocked)
                    )
                # Resource held by another thread - block
                blocked[tid] = True
                return PhantomState(
                    pcs=state.pcs,
                    lock_map=state.lock_map,
                    blocked=tuple(blocked)
                )
            if arg:
                lock_map[arg] = tid

        elif op in ("REL", "RELEASE"):
            if arg and lock_map.get(arg) == tid:
                lock_map[arg] = None
                # Unblock any thread waiting on this resource
                for other_tid in range(len(blocked)):
                    if blocked[other_tid]:
                        other_pc = state.pcs[other_tid]
                        if other_pc < len(threads[other_tid].atoms):
                            other_atom = threads[other_tid].atoms[other_pc]
                            if (other_atom.op in ("ACQ", "ACQUIRE")
                                    and other_atom.arg == arg):
                                blocked[other_tid] = False

        # AWT, STA, CALL, EMIT, GEN, CONT: advance PC, no lock-map change
        new_pcs = list(state.pcs)
        new_pcs[tid] = pc + 1

        return PhantomState(
            pcs=tuple(new_pcs),
            lock_map=tuple(sorted(lock_map.items())),
            blocked=tuple(blocked)
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_resources(self, threads: List[ThreadSequence]) -> List[str]:
        """Collect all unique resource names from thread sequences."""
        resources: Set[str] = set()
        for thread in threads:
            for atom in thread.atoms:
                if atom.op in ("ACQ", "ACQUIRE", "REL", "RELEASE") and atom.arg:
                    resources.add(atom.arg)
        return sorted(resources)

    def _explore(
        self,
        initial: PhantomState,
        threads: List[ThreadSequence],
        resources: List[str],
        config: SimulationConfig
    ) -> List[PhantomResult]:
        """BFS over interleaving states; return all findings.

        Exhaustive BFS with hard state-count cap. Immutable PhantomState
        used as dict key for O(1) visited check.
        """
        visited: Set[PhantomState] = set()
        queue: deque[Tuple[PhantomState, List[str]]] = deque()
        queue.append((initial, []))
        findings: List[PhantomResult] = []
        found_verdicts: Set[Verdict] = set()

        symbol_names = [t.symbol_name for t in threads]

        while queue:
            if len(visited) >= config.max_states:
                if "SIMULATION_TRUNCATED" not in found_verdicts:
                    findings.append(PhantomResult(
                        verdict="SIMULATION_TRUNCATED",
                        symbols=tuple(symbol_names),
                        resources=tuple(resources),
                        witness_trace=(),
                        note=(
                            f"State space exceeded {config.max_states} states. "
                            "Results may be incomplete. Consider reducing symbol scope."
                        )
                    ))
                break

            state, trace = queue.popleft()
            if state in visited:
                continue
            visited.add(state)

            # Check deadlock: all threads blocked
            if all(state.blocked):
                key: Verdict = "DEADLOCK_RISK"
                if key not in found_verdicts:
                    found_verdicts.add(key)
                    findings.append(PhantomResult(
                        verdict="DEADLOCK_RISK",
                        symbols=tuple(symbol_names),
                        resources=tuple(
                            r for r, owner in state.lock_map if owner is not None
                        ),
                        witness_trace=tuple(trace),
                        note=(
                            "All threads blocked in circular wait. "
                            f"Witness trace: {' -> '.join(trace)}"
                        )
                    ))
                continue

            # Advance each non-blocked thread
            for tid in range(len(threads)):
                if state.blocked[tid]:
                    continue

                pc = state.pcs[tid]
                if pc >= len(threads[tid].atoms):
                    # Thread at EOF - check resource leak
                    leaking = [
                        r for r, owner in state.lock_map if owner == tid
                    ]
                    if leaking:
                        key = "RESOURCE_LEAK"
                        if key not in found_verdicts:
                            found_verdicts.add(key)
                            findings.append(PhantomResult(
                                verdict="RESOURCE_LEAK",
                                symbols=(symbol_names[tid],),
                                resources=tuple(leaking),
                                witness_trace=tuple(trace),
                                note=(
                                    f"Thread '{symbol_names[tid]}' reached EOF while "
                                    f"holding locks: {leaking}. Missing REL."
                                )
                            ))
                    continue

                next_state = self.step(state, tid, threads)
                if next_state is not None:
                    atom = threads[tid].atoms[pc]
                    step_label = (
                        f"{symbol_names[tid]}:"
                        f"{atom.op}"
                        f"({atom.arg})"
                    )
                    queue.append((next_state, trace + [step_label]))

        return findings

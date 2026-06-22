"""
Monte Carlo Simulator for Shadow Draft System

Simulates concurrent execution of DSL atoms to detect deadlocks.
Uses digital twin simulation with random scheduling.
"""
from typing import List, Dict, Any, Set, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import random
import logging
from collections import defaultdict

from quro_cli.shadow.dsl_parser import Atom, AtomType, ExecutionGraph, DSLAtomParser

logger = logging.getLogger(__name__)


class ThreadState(Enum):
    """Thread execution state"""
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"


@dataclass
class Thread:
    """Simulated thread executing atom sequence"""
    id: int
    atoms: List[Atom]
    pc: int = 0  # Program counter
    state: ThreadState = ThreadState.READY
    held_resources: Set[str] = field(default_factory=set)
    waiting_for: Optional[str] = None

    def current_atom(self) -> Optional[Atom]:
        """Get current atom at PC"""
        if self.pc < len(self.atoms):
            return self.atoms[self.pc]
        return None

    def advance(self):
        """Advance program counter"""
        self.pc += 1
        if self.pc >= len(self.atoms):
            self.state = ThreadState.COMPLETED


@dataclass
class SimulationState:
    """Global simulation state"""
    threads: List[Thread]
    resources: Dict[str, Optional[int]]  # resource -> thread_id (None if free)
    step: int = 0
    deadlock_detected: bool = False
    deadlock_cycle: List[Tuple[int, str]] = field(default_factory=list)  # [(thread_id, resource), ...]

    def is_resource_free(self, resource: str) -> bool:
        """Check if resource is free"""
        return self.resources.get(resource) is None

    def acquire_resource(self, thread_id: int, resource: str) -> bool:
        """Try to acquire resource for thread"""
        if self.is_resource_free(resource):
            self.resources[resource] = thread_id
            return True
        return False

    def release_resource(self, thread_id: int, resource: str):
        """Release resource held by thread"""
        if self.resources.get(resource) == thread_id:
            self.resources[resource] = None


@dataclass
class WitnessTrace:
    """Witness trace showing deadlock scenario"""
    steps: List[Dict[str, Any]]
    deadlock_cycle: List[Tuple[int, str]]
    final_state: Dict[str, Any]


@dataclass
class SimulationResult:
    """Result of Monte Carlo simulation"""
    deadlock_detected: bool
    risk_score: float
    num_runs: int
    num_deadlocks: int
    witness_traces: List[WitnessTrace]
    statistics: Dict[str, Any]


class MonteCarloSimulator:
    """Monte Carlo simulator for deadlock detection"""

    def __init__(self, num_runs: int = 1000, max_steps: int = 1000, seed: Optional[int] = None):
        """
        Initialize Monte Carlo simulator

        Args:
            num_runs: Number of simulation runs
            max_steps: Maximum steps per run
            seed: Random seed for reproducibility
        """
        self.num_runs = num_runs
        self.max_steps = max_steps
        self.random = random.Random(seed)
        self.parser = DSLAtomParser()

    def simulate(self, graphs: List[ExecutionGraph]) -> SimulationResult:
        """
        Run Monte Carlo simulation on multiple execution graphs

        Args:
            graphs: List of execution graphs (one per thread)

        Returns:
            SimulationResult with deadlock detection and risk score
        """
        num_deadlocks = 0
        witness_traces = []

        for run_idx in range(self.num_runs):
            state = self._initialize_state(graphs)
            trace_steps = []

            for step in range(self.max_steps):
                state.step = step

                # Record state
                trace_steps.append(self._capture_state(state))

                # Check for deadlock
                if self._detect_deadlock(state):
                    num_deadlocks += 1
                    witness_traces.append(WitnessTrace(
                        steps=trace_steps,
                        deadlock_cycle=state.deadlock_cycle,
                        final_state=self._capture_state(state)
                    ))
                    break

                # Check if all threads completed
                if all(t.state == ThreadState.COMPLETED for t in state.threads):
                    break

                # Schedule next thread
                if not self._schedule_step(state):
                    # No progress possible - likely deadlock
                    if self._detect_deadlock(state):
                        num_deadlocks += 1
                        witness_traces.append(WitnessTrace(
                            steps=trace_steps,
                            deadlock_cycle=state.deadlock_cycle,
                            final_state=self._capture_state(state)
                        ))
                    break

        risk_score = num_deadlocks / self.num_runs

        return SimulationResult(
            deadlock_detected=num_deadlocks > 0,
            risk_score=risk_score,
            num_runs=self.num_runs,
            num_deadlocks=num_deadlocks,
            witness_traces=witness_traces[:5],  # Keep first 5 traces
            statistics={
                "deadlock_rate": risk_score,
                "avg_steps_to_deadlock": self._compute_avg_steps(witness_traces),
                "resource_contention": self._compute_resource_contention(graphs)
            }
        )

    def _initialize_state(self, graphs: List[ExecutionGraph]) -> SimulationState:
        """Initialize simulation state from execution graphs"""
        threads = []
        all_resources = set()

        for i, graph in enumerate(graphs):
            threads.append(Thread(
                id=i,
                atoms=graph.atoms,
                pc=0,
                state=ThreadState.READY
            ))
            all_resources.update(graph.resources)

        resources = {r: None for r in all_resources}

        return SimulationState(
            threads=threads,
            resources=resources
        )

    def _schedule_step(self, state: SimulationState) -> bool:
        """
        Schedule one execution step

        Returns:
            True if progress was made, False if stuck
        """
        # Get ready threads
        ready_threads = [t for t in state.threads if t.state == ThreadState.READY]

        if not ready_threads:
            # Try to unblock waiting threads
            waiting_threads = [t for t in state.threads if t.state == ThreadState.WAITING]
            for thread in waiting_threads:
                if thread.waiting_for and state.is_resource_free(thread.waiting_for):
                    thread.state = ThreadState.READY
                    ready_threads.append(thread)

            if not ready_threads:
                return False

        # Randomly select a ready thread
        thread = self.random.choice(ready_threads)
        thread.state = ThreadState.RUNNING

        # Execute current atom
        atom = thread.current_atom()
        if not atom:
            thread.state = ThreadState.COMPLETED
            return True

        success = self._execute_atom(state, thread, atom)

        if success:
            thread.advance()
            if thread.state != ThreadState.COMPLETED:
                thread.state = ThreadState.READY
        else:
            thread.state = ThreadState.BLOCKED

        return success

    def _execute_atom(self, state: SimulationState, thread: Thread, atom: Atom) -> bool:
        """
        Execute single atom

        Returns:
            True if execution succeeded, False if blocked
        """
        if atom.type == AtomType.ACQ:
            # Try to acquire resource
            if state.acquire_resource(thread.id, atom.resource):
                thread.held_resources.add(atom.resource)
                return True
            else:
                # Blocked - mark what we're waiting for
                thread.waiting_for = atom.resource
                thread.state = ThreadState.WAITING
                return False

        elif atom.type == AtomType.REL:
            # Release resource
            if atom.resource in thread.held_resources:
                state.release_resource(thread.id, atom.resource)
                thread.held_resources.remove(atom.resource)
            return True

        elif atom.type == AtomType.AWT:
            # Await - simulate random delay
            if self.random.random() < 0.9:  # 90% chance to complete
                return True
            else:
                thread.state = ThreadState.WAITING
                return False

        elif atom.type in (AtomType.STA, AtomType.CALL, AtomType.EMIT, AtomType.GEN, AtomType.CONT):
            # Other atoms execute immediately
            return True

        return True

    def _detect_deadlock(self, state: SimulationState) -> bool:
        """
        Detect deadlock using cycle detection in wait-for graph

        Returns:
            True if deadlock detected
        """
        # Build wait-for graph
        wait_for = {}  # thread_id -> resource
        resource_holders = {}  # resource -> thread_id

        for thread in state.threads:
            if thread.state == ThreadState.WAITING and thread.waiting_for:
                wait_for[thread.id] = thread.waiting_for

            for resource in thread.held_resources:
                resource_holders[resource] = thread.id

        # Check for cycles
        for start_thread in wait_for:
            visited = set()
            current = start_thread
            cycle = []

            while current is not None:
                if current in visited:
                    # Cycle detected
                    cycle_start = cycle.index(current)
                    state.deadlock_cycle = cycle[cycle_start:]
                    state.deadlock_detected = True
                    return True

                visited.add(current)
                cycle.append(current)

                # Follow wait-for edge
                resource = wait_for.get(current)
                if resource:
                    current = resource_holders.get(resource)
                else:
                    break

        return False

    def _capture_state(self, state: SimulationState) -> Dict[str, Any]:
        """Capture current simulation state"""
        return {
            "step": state.step,
            "threads": [
                {
                    "id": t.id,
                    "pc": t.pc,
                    "state": t.state.value,
                    "held_resources": list(t.held_resources),
                    "waiting_for": t.waiting_for
                }
                for t in state.threads
            ],
            "resources": {
                r: holder for r, holder in state.resources.items()
            }
        }

    def _compute_avg_steps(self, traces: List[WitnessTrace]) -> float:
        """Compute average steps to deadlock"""
        if not traces:
            return 0.0
        return sum(len(t.steps) for t in traces) / len(traces)

    def _compute_resource_contention(self, graphs: List[ExecutionGraph]) -> Dict[str, int]:
        """Compute resource contention statistics"""
        resource_usage = defaultdict(int)

        for graph in graphs:
            for resource in graph.resources:
                resource_usage[resource] += 1

        return dict(resource_usage)

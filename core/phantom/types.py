"""Phantom Kernel Types - Immutable data structures for BFS simulation.

@module quro.core.phantom.types
@intent Define pure data contracts for phantom simulation inputs/outputs.
"""

from dataclasses import dataclass
from typing import Literal, Tuple, List


# Type aliases
Verdict = Literal["SAFE", "DEADLOCK_RISK", "RESOURCE_LEAK", "SIMULATION_TRUNCATED"]
AtomOp = Literal["ACQ", "ACQUIRE", "REL", "RELEASE", "AWT", "STA", "CALL", "EMIT", "GEN", "CONT"]


@dataclass(frozen=True)
class Atom:
    """Pure data: DSL atom (immutable).

    Represents a single operation in the atom sequence.
    """
    op: AtomOp  # Operation type
    arg: str  # Resource name or method name
    line: int = 0  # Source line number


@dataclass(frozen=True)
class ThreadSequence:
    """Pure data: atom sequence for one thread (immutable).

    Represents the complete execution sequence for a single symbol.
    """
    symbol_name: str  # Symbol identifier
    atoms: Tuple[Atom, ...]  # Atom sequence


@dataclass(frozen=True)
class PhantomState:
    """Pure data: immutable snapshot of one interleaving step (immutable).

    Hashable state node for BFS visited-set deduplication.
    """
    pcs: Tuple[int, ...]  # Per-thread program counter (atom index)
    lock_map: Tuple[Tuple[str, int | None], ...]  # Sorted (resource, owner_tid|None)
    blocked: Tuple[bool, ...]  # Per-thread blocked flag


@dataclass(frozen=True)
class PhantomResult:
    """Pure data: simulation outcome (immutable).

    Carries verdict, affected symbols/resources, and witness trace.
    """
    verdict: Verdict  # Simulation verdict
    symbols: Tuple[str, ...]  # Affected symbol names
    resources: Tuple[str, ...]  # Involved resources
    witness_trace: Tuple[str, ...]  # Human-readable execution trace
    note: str  # Diagnostic message


@dataclass(frozen=True)
class SimulationConfig:
    """Pure data: simulation parameters (immutable).

    Configuration for BFS exploration limits.
    """
    max_threads: int = 4  # Maximum concurrent threads
    max_depth: int = 64  # Maximum BFS depth
    max_states: int = 10_000  # Maximum state space size

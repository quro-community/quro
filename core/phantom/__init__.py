"""Phantom Kernel - Pure BFS interleaving simulator for deadlock detection.

@module quro.core.phantom
@intent Public API for Phantom kernel (BFS simulation, deadlock detection).
"""

from types import (
    Atom,
    ThreadSequence,
    PhantomState,
    PhantomResult,
    SimulationConfig,
    Verdict,
    AtomOp
)

from kernel import PhantomKernel
from engine import PhantomEngine

__all__ = [
    # Types
    "Atom",
    "ThreadSequence",
    "PhantomState",
    "PhantomResult",
    "SimulationConfig",
    "Verdict",
    "AtomOp",
    # Protocol
    "PhantomKernel",
    # Implementation
    "PhantomEngine",
]

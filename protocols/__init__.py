"""
Quro v3 Protocol Layer - Minimal Constraint Contracts

@module quro.protocols
@intent Define minimal contracts for invariant protection
@constraint Three protocols only: Kernel, Policy, Extension

This is NOT an architecture layer - it's a constraint layer.
The goal is to prevent future modifications from breaking invariants:
1. Kernel is pure (no side effects)
2. Policy is declarative (data-only)
3. Extension is isolated (cannot touch kernel)
"""

from protocols.kernel import KernelProtocol
from protocols.policy import PolicyProtocol
from protocols.extension import ExtensionProtocol

__all__ = [
    "KernelProtocol",
    "PolicyProtocol",
    "ExtensionProtocol",
]

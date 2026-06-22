"""
Quro - Minimal Constraint Architecture

@module quro
@intent Refactor v2 with proper boundaries
@constraint Three-layer architecture with invariant protection

Layers:
1. Protocols - Minimal constraint contracts
2. Core - Pure logic engines (CQE, LSH, Morph)
3. I/O - Boundary adapters
4. Runtime - Orchestration

Invariants:
1. Kernel is pure (no side effects)
2. Policy is declarative (data-only)
3. Extension is isolated (cannot access kernel)
"""

__version__ = "3.0.0-alpha"

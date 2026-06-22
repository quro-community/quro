"""
CQE Core Module - Categorical Query Engine

@module quro.core.cqe
@intent Pure CQE logic extracted from v2
@constraint No I/O, pure functions only

Components:
- kernel.py: Max-Product Dijkstra (from v2, unchanged)
- canonical.py: Token resolution (from v2, unchanged)
- types.py: GraphProtocol, CQEResult (from v2)
- policy.py: Policy configuration (new)
"""

from core.cqe.types import GraphProtocol, CQEResult, CanonicalResult, CQERefinerProtocol, CQERefinedResult
from core.cqe.kernel import CQEKernel
from core.cqe.canonical import CanonicalLayer
from core.cqe.refiner import DefaultCQERefiner

__all__ = [
    "GraphProtocol",
    "CQEResult",
    "CanonicalResult",
    "CQERefinerProtocol",
    "CQERefinedResult",
    "DefaultCQERefiner",
    "CQEKernel",
    "CanonicalLayer",
]
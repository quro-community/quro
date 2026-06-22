"""Manifold Adapter - Public API.

@module quro.adapters.manifold
@intent Expose clean manifold I/O operations via Protocol-driven design.
"""

from .types import (
    ManifoldNode,
    DriftResult,
    NodeInsertRequest,
)
from .protocol import ManifoldAdapter
from .postgres import PostgresManifold

__all__ = [
    # Types
    "ManifoldNode",
    "DriftResult",
    "NodeInsertRequest",
    # Protocol
    "ManifoldAdapter",
    # Implementation
    "PostgresManifold",
]

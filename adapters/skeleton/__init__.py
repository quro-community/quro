"""Skeleton Adapter - Public API.

@module quro.adapters.skeleton
@intent Expose clean skeleton graph I/O operations via Protocol-driven design.
"""

from .types import (
    ModuleNode,
    DependencyEdge,
    CircularDependency,
    SkeletonGraph,
    GraphInsertRequest,
    EdgeType,
    RiskLevel,
    Language,
)
from .protocol import SkeletonAdapter
from .jsonl import JsonlSkeleton

__all__ = [
    # Types
    "ModuleNode",
    "DependencyEdge",
    "CircularDependency",
    "SkeletonGraph",
    "GraphInsertRequest",
    "EdgeType",
    "RiskLevel",
    "Language",
    # Protocol
    "SkeletonAdapter",
    # Implementation
    "JsonlSkeleton",
]

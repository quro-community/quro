"""Skeleton Kernel - Pure graph algorithms for dependency analysis.

@module quro.core.skeleton
@intent Public API for Skeleton kernel (Tarjan's SCC, BFS, DFS).
"""

from types import (
    ModuleNode,
    DependencyEdge,
    SkeletonGraph,
    CircularDependency,
    CycleResult,
    PathResult,
    DependencyResult,
    EdgeType,
    RiskLevel,
    Language
)

from kernel import SkeletonKernel
from engine import SkeletonEngine

__all__ = [
    # Types
    "ModuleNode",
    "DependencyEdge",
    "SkeletonGraph",
    "CircularDependency",
    "CycleResult",
    "PathResult",
    "DependencyResult",
    "EdgeType",
    "RiskLevel",
    "Language",
    # Protocol
    "SkeletonKernel",
    # Implementation
    "SkeletonEngine",
]

"""Skeleton Adapter Types - Immutable data structures for skeleton graph operations.

@module quro.adapters.skeleton.types
@intent Define pure data contracts for skeleton graph I/O operations.
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Literal
from datetime import datetime


EdgeType = Literal["IMPORT", "EXPORT", "CALL", "INHERIT"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Language = Literal["python", "typescript"]


@dataclass(frozen=True)
class ModuleNode:
    """Pure data: module node record (immutable).

    Represents a single module (file) in the dependency graph.
    """
    uid: str
    file_path: str
    language: Language
    exports: Tuple[str, ...]
    imports: Tuple[str, ...]
    behavioral_tags: Tuple[str, ...] = ()
    checksum: str = ""


@dataclass(frozen=True)
class DependencyEdge:
    """Pure data: dependency edge record (immutable).

    Represents a directed edge between two modules.
    """
    from_uid: str
    to_uid: str
    edge_type: EdgeType
    symbols_imported: Tuple[str, ...] = ()
    risk_level: RiskLevel = "LOW"
    line_number: Optional[int] = None


@dataclass(frozen=True)
class CircularDependency:
    """Pure data: circular dependency record (immutable).

    Represents a detected cycle in the dependency graph.
    """
    cycle_path: Tuple[str, ...]
    risk_level: RiskLevel
    detected_at: datetime
    witness: str


@dataclass(frozen=True)
class SkeletonGraph:
    """Pure data: complete skeleton graph snapshot (immutable).

    Represents the entire dependency graph at a point in time.
    """
    nodes: Tuple[ModuleNode, ...]
    edges: Tuple[DependencyEdge, ...]
    cycles: Tuple[CircularDependency, ...]
    built_at: datetime
    checksum: str


@dataclass(frozen=True)
class GraphInsertRequest:
    """Pure data: graph insert request (immutable).

    Request to save a complete skeleton graph snapshot.
    """
    nodes: Tuple[ModuleNode, ...]
    edges: Tuple[DependencyEdge, ...]
    cycles: Tuple[CircularDependency, ...]

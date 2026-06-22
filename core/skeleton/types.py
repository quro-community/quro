"""Skeleton Kernel Types - Immutable data structures for graph algorithms.

@module quro.core.skeleton.types
@intent Define pure data contracts for skeleton graph inputs/outputs.
"""

from dataclasses import dataclass
from typing import Literal, Optional, Tuple, Dict
import datetime


# Type aliases
EdgeType = Literal["IMPORT", "EXPORT", "CALL", "INHERIT"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Language = Literal["python", "typescript"]


@dataclass(frozen=True)
class ModuleNode:
    """Pure data: module representation (immutable).

    Represents a single module (file) in the dependency graph.
    """
    uid: str  # Unique identifier (file path relative to workspace)
    file_path: str  # Physical file path
    language: Language  # Programming language
    exports: Tuple[str, ...]  # Exported symbols
    imports: Tuple[str, ...]  # Imported module names
    behavioral_tags: Tuple[str, ...] = ()  # Behavioral characteristics
    checksum: str = ""  # Content hash


@dataclass(frozen=True)
class DependencyEdge:
    """Pure data: directed edge between modules (immutable).

    Represents a dependency relationship.
    """
    from_uid: str  # Source module UID
    to_uid: str  # Target module UID
    edge_type: EdgeType  # Type of dependency
    symbols_imported: Tuple[str, ...] = ()  # Imported symbols
    risk_level: RiskLevel = "LOW"  # Risk classification
    line_number: Optional[int] = None  # Source line number


@dataclass(frozen=True)
class SkeletonGraph:
    """Pure data: immutable dependency graph (immutable).

    Complete dependency graph with nodes, edges, and precomputed adjacency.
    """
    nodes: Tuple[ModuleNode, ...]  # All modules
    edges: Tuple[DependencyEdge, ...]  # All dependencies
    adjacency_out: Dict[str, Tuple[str, ...]]  # from_uid -> [to_uids]
    adjacency_in: Dict[str, Tuple[str, ...]]  # to_uid -> [from_uids]

    def __post_init__(self):
        """Validate graph invariants."""
        # Verify all edge endpoints exist in nodes
        node_uids = {node.uid for node in self.nodes}
        for edge in self.edges:
            if edge.from_uid not in node_uids:
                raise ValueError(f"Edge from_uid not in nodes: {edge.from_uid}")
            if edge.to_uid not in node_uids:
                raise ValueError(f"Edge to_uid not in nodes: {edge.to_uid}")


@dataclass(frozen=True)
class CircularDependency:
    """Pure data: detected cycle (immutable).

    Represents a circular dependency detected via Tarjan's SCC.
    """
    cycle_path: Tuple[str, ...]  # Module UIDs forming the cycle
    risk_level: RiskLevel  # Risk classification
    detected_at: datetime.datetime  # Detection timestamp
    witness: str  # DSL trace description


@dataclass(frozen=True)
class CycleResult:
    """Pure data: cycle detection output (immutable).

    Result of Tarjan's SCC algorithm.
    """
    has_cycles: bool  # True if cycles detected
    cycles: Tuple[CircularDependency, ...]  # All detected cycles
    strongly_connected_components: Tuple[Tuple[str, ...], ...]  # All SCCs


@dataclass(frozen=True)
class PathResult:
    """Pure data: path finding output (immutable).

    Result of BFS path search.
    """
    from_uid: str  # Starting module
    to_uid: str  # Target module
    path: Tuple[DependencyEdge, ...]  # Edges forming the path
    found: bool  # True if path exists
    depth: int  # Path length


@dataclass(frozen=True)
class DependencyResult:
    """Pure data: dependency query output (immutable).

    Result of BFS dependency traversal.
    """
    module_uid: str  # Queried module
    related_modules: Tuple[ModuleNode, ...]  # Found modules
    depth: int  # Traversal depth
    traversal_path: Tuple[str, ...]  # UIDs in traversal order

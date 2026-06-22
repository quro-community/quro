"""Skeleton Kernel Protocol - Pure function contract.

@module quro.core.skeleton.kernel
@intent Define the contract for Skeleton kernel implementations.
"""

from typing import Protocol, Optional
from types import (
    SkeletonGraph,
    ModuleNode,
    CycleResult,
    PathResult,
    DependencyResult
)


class SkeletonKernel(Protocol):
    """Pure function contract for Skeleton kernel.

    Invariant: All methods are pure (no side effects).

    Implementations MUST NOT:
    - Perform I/O (file, database, network)
    - Mutate input arguments
    - Access global state
    - Call logging functions
    """

    def detect_cycles(self, graph: SkeletonGraph) -> CycleResult:
        """Pure: graph → cycles (Tarjan's SCC).

        Args:
            graph: Immutable dependency graph

        Returns:
            CycleResult with all detected cycles

        Invariant: Tarjan's algorithm runs in O(V+E) time.
        """
        ...

    def find_path(
        self,
        graph: SkeletonGraph,
        from_uid: str,
        to_uid: str
    ) -> PathResult:
        """Pure: (graph, from, to) → shortest path (BFS).

        Args:
            graph: Immutable dependency graph
            from_uid: Starting module
            to_uid: Target module

        Returns:
            PathResult with shortest path if found

        Invariant: BFS finds shortest path in O(V+E) time.
        """
        ...

    def get_dependencies(
        self,
        graph: SkeletonGraph,
        module_uid: str,
        depth: int
    ) -> DependencyResult:
        """Pure: (graph, module, depth) → dependencies (BFS).

        Args:
            graph: Immutable dependency graph
            module_uid: Module to query
            depth: Maximum traversal depth

        Returns:
            DependencyResult with all dependencies up to depth

        Invariant: BFS traversal respects depth limit.
        """
        ...

    def get_dependents(
        self,
        graph: SkeletonGraph,
        module_uid: str,
        depth: int
    ) -> DependencyResult:
        """Pure: (graph, module, depth) → dependents (reverse BFS).

        Args:
            graph: Immutable dependency graph
            module_uid: Module to query
            depth: Maximum traversal depth

        Returns:
            DependencyResult with all dependents up to depth

        Invariant: Reverse BFS traversal respects depth limit.
        """
        ...

    def get_module(
        self,
        graph: SkeletonGraph,
        module_uid: str
    ) -> Optional[ModuleNode]:
        """Pure: (graph, uid) → module node.

        Args:
            graph: Immutable dependency graph
            module_uid: Module to lookup

        Returns:
            ModuleNode if found, None otherwise

        Invariant: O(1) lookup via precomputed index.
        """
        ...

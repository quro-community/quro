"""Skeleton Orchestrator - Bridges Skeleton Adapter and Skeleton Kernel.

@module quro.orchestrators.skeleton
@intent Coordinate dependency graph analysis and persistence.
"""

from typing import Tuple, Optional, Set, Dict
from datetime import datetime
from core.skeleton import (
    SkeletonEngine,
    ModuleNode as KernelModuleNode,
    DependencyEdge as KernelDependencyEdge,
    SkeletonGraph as KernelSkeletonGraph,
    CircularDependency,
)
from adapters.skeleton import (
    SkeletonAdapter,
    ModuleNode,
    DependencyEdge,
    SkeletonGraph,
    CircularDependency as AdapterCircularDependency,
)


class SkeletonOrchestrator:
    """Orchestrates dependency graph analysis and persistence.

    Coordinates:
    - Skeleton Kernel (pure computation)
    - Skeleton Adapter (I/O persistence)

    Invariant: Orchestration only, no business logic.
    """

    def __init__(
        self,
        skeleton_adapter: SkeletonAdapter,
    ):
        """Initialize Skeleton orchestrator.

        Args:
            skeleton_adapter: Skeleton persistence adapter
        """
        self.adapter = skeleton_adapter
        self.kernel = SkeletonEngine()

    async def build_and_store_graph(
        self,
        nodes: Tuple[ModuleNode, ...],
        edges: Tuple[DependencyEdge, ...],
    ) -> SkeletonGraph:
        """Build dependency graph and detect cycles.

        Args:
            nodes: Module nodes
            edges: Dependency edges

        Returns:
            SkeletonGraph with cycle detection

        Pipeline:
            1. Build adjacency lists
            2. Detect cycles (kernel)
            3. Store graph (adapter)
        """
        # Step 1: Build adjacency lists for kernel
        adjacency_out: Dict[str, Tuple[str, ...]] = {}
        adjacency_in: Dict[str, Tuple[str, ...]] = {}

        for node in nodes:
            adjacency_out[node.uid] = ()
            adjacency_in[node.uid] = ()

        for edge in edges:
            # Add to adjacency_out
            current_out = list(adjacency_out.get(edge.from_uid, ()))
            current_out.append(edge.to_uid)
            adjacency_out[edge.from_uid] = tuple(current_out)

            # Add to adjacency_in
            current_in = list(adjacency_in.get(edge.to_uid, ()))
            current_in.append(edge.from_uid)
            adjacency_in[edge.to_uid] = tuple(current_in)

        # Step 2: Create kernel graph with adjacency lists
        kernel_graph = KernelSkeletonGraph(
            nodes=nodes,
            edges=edges,
            adjacency_out=adjacency_out,
            adjacency_in=adjacency_in,
        )

        # Step 3: Detect cycles (pure computation)
        cycle_result = self.kernel.detect_cycles(kernel_graph)

        # Step 4: Create adapter graph (without adjacency lists)
        graph = SkeletonGraph(
            nodes=nodes,
            edges=edges,
            cycles=cycle_result.cycles,
            built_at=datetime.now(),
            checksum=self._compute_checksum(nodes, edges),
        )

        # Step 5: Store graph (I/O)
        await self.adapter.save_graph(graph)

        return graph

    async def find_dependencies(
        self,
        module_uid: str,
        max_depth: int = 3,
    ) -> Tuple[str, ...]:
        """Find all dependencies of a module.

        Args:
            module_uid: Module unique identifier
            max_depth: Maximum traversal depth

        Returns:
            Tuple of dependent module UIDs

        Pipeline:
            1. Load graph (adapter)
            2. Build adjacency lists
            3. Traverse dependencies (kernel)
        """
        # Step 1: Load graph (I/O)
        graph = await self.adapter.load_latest_graph()
        if graph is None:
            return ()

        # Step 2: Build adjacency lists
        kernel_graph = self._build_kernel_graph(graph)

        # Step 3: Traverse dependencies (pure computation)
        dep_result = self.kernel.get_dependencies(kernel_graph, module_uid, max_depth)

        return dep_result.dependencies

    async def find_dependents(
        self,
        module_uid: str,
        max_depth: int = 3,
    ) -> Tuple[str, ...]:
        """Find all modules that depend on this module.

        Args:
            module_uid: Module unique identifier
            max_depth: Maximum traversal depth

        Returns:
            Tuple of dependent module UIDs

        Pipeline:
            1. Load graph (adapter)
            2. Build adjacency lists
            3. Traverse dependents (kernel)
        """
        # Step 1: Load graph (I/O)
        graph = await self.adapter.load_latest_graph()
        if graph is None:
            return ()

        # Step 2: Build adjacency lists
        kernel_graph = self._build_kernel_graph(graph)

        # Step 3: Traverse dependents (pure computation)
        dep_result = self.kernel.get_dependents(kernel_graph, module_uid, max_depth)

        return dep_result.dependents

    async def get_cycles(self) -> Tuple[AdapterCircularDependency, ...]:
        """Get all circular dependencies in latest graph.

        Returns:
            Tuple of CircularDependency objects

        Pipeline:
            1. Load graph (adapter)
            2. Return cycles
        """
        # Load graph (I/O)
        graph = await self.adapter.load_latest_graph()
        if graph is None:
            return ()

        return graph.cycles

    def _compute_checksum(
        self,
        nodes: Tuple[ModuleNode, ...],
        edges: Tuple[DependencyEdge, ...],
    ) -> str:
        """Compute checksum for graph.

        Args:
            nodes: Module nodes
            edges: Dependency edges

        Returns:
            Checksum string
        """
        import hashlib

        # Concatenate all UIDs and compute hash
        content = "".join(node.uid for node in nodes)
        content += "".join(f"{edge.from_uid}->{edge.to_uid}" for edge in edges)

        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _build_kernel_graph(self, adapter_graph: SkeletonGraph) -> KernelSkeletonGraph:
        """Build kernel graph with adjacency lists from adapter graph.

        Args:
            adapter_graph: Adapter skeleton graph

        Returns:
            Kernel skeleton graph with adjacency lists
        """
        # Build adjacency lists
        adjacency_out: Dict[str, Tuple[str, ...]] = {}
        adjacency_in: Dict[str, Tuple[str, ...]] = {}

        for node in adapter_graph.nodes:
            adjacency_out[node.uid] = ()
            adjacency_in[node.uid] = ()

        for edge in adapter_graph.edges:
            # Add to adjacency_out
            current_out = list(adjacency_out.get(edge.from_uid, ()))
            current_out.append(edge.to_uid)
            adjacency_out[edge.from_uid] = tuple(current_out)

            # Add to adjacency_in
            current_in = list(adjacency_in.get(edge.to_uid, ()))
            current_in.append(edge.from_uid)
            adjacency_in[edge.to_uid] = tuple(current_in)

        return KernelSkeletonGraph(
            nodes=adapter_graph.nodes,
            edges=adapter_graph.edges,
            adjacency_out=adjacency_out,
            adjacency_in=adjacency_in,
        )

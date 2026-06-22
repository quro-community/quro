"""Skeleton Engine - Pure graph algorithms (Tarjan's SCC, BFS, DFS).

@module quro.core.skeleton.engine
@intent Concrete implementation of SkeletonKernel protocol.
        Pure graph algorithms with no side effects.
"""

from typing import Optional, Dict, Set, List, Tuple
from collections import deque
import datetime

from types import (
    SkeletonGraph,
    ModuleNode,
    DependencyEdge,
    CircularDependency,
    CycleResult,
    PathResult,
    DependencyResult,
    RiskLevel
)


class SkeletonEngine:
    """Skeleton graph kernel - pure implementation.

    Invariants:
    - All methods are pure (no side effects)
    - Graph-blind (receives graph data structure, not database)
    - No I/O (no file, database, network access)
    - No logging (pure computation only)
    """

    def detect_cycles(self, graph: SkeletonGraph) -> CycleResult:
        """Pure: graph → cycles (Tarjan's SCC).

        Implements Tarjan's strongly connected components algorithm.
        Time complexity: O(V+E)
        Space complexity: O(V)

        Args:
            graph: Immutable dependency graph

        Returns:
            CycleResult with all detected cycles
        """
        # Tarjan's algorithm state
        index_counter = [0]
        stack: List[str] = []
        low_links: Dict[str, int] = {}
        index: Dict[str, int] = {}
        on_stack: Dict[str, bool] = {}
        sccs: List[List[str]] = []

        # Run Tarjan's algorithm iteratively to avoid RecursionError
        for start_node in graph.nodes:
            if start_node.uid in index:
                continue

            # call_stack stores (node, neighbor_iterator)
            call_stack = [(start_node.uid, iter(graph.adjacency_out.get(start_node.uid, ())))]
            
            # Setup initial node
            index[start_node.uid] = index_counter[0]
            low_links[start_node.uid] = index_counter[0]
            index_counter[0] += 1
            stack.append(start_node.uid)
            on_stack[start_node.uid] = True
            
            while call_stack:
                node, neighbors_iter = call_stack[-1]
                
                try:
                    successor = next(neighbors_iter)
                    if successor not in index:
                        index[successor] = index_counter[0]
                        low_links[successor] = index_counter[0]
                        index_counter[0] += 1
                        stack.append(successor)
                        on_stack[successor] = True
                        call_stack.append((successor, iter(graph.adjacency_out.get(successor, ()))))
                    elif on_stack.get(successor, False):
                        low_links[node] = min(low_links[node], index[successor])
                except StopIteration:
                    call_stack.pop()
                    if call_stack:
                        prev_node = call_stack[-1][0]
                        low_links[prev_node] = min(low_links[prev_node], low_links[node])
                    
                    if low_links[node] == index[node]:
                        scc: List[str] = []
                        while True:
                            w = stack.pop()
                            on_stack[w] = False
                            scc.append(w)
                            if w == node:
                                break
                        sccs.append(scc)

        # Filter SCCs with > 1 node (these are cycles)
        cycles: List[CircularDependency] = []
        for scc in sccs:
            if len(scc) > 1:
                # Build cycle path (close the cycle)
                cycle_path = tuple(scc + [scc[0]])

                # Classify risk
                risk_level = self._classify_cycle_risk(cycle_path, graph)

                # Generate witness
                witness = self._generate_witness(cycle_path)

                cycles.append(CircularDependency(
                    cycle_path=cycle_path,
                    risk_level=risk_level,
                    detected_at=datetime.datetime.now(),
                    witness=witness
                ))

        # Detect self-loops (A → A)
        for edge in graph.edges:
            if edge.from_uid == edge.to_uid:
                cycles.append(CircularDependency(
                    cycle_path=(edge.from_uid, edge.to_uid),
                    risk_level="LOW",
                    detected_at=datetime.datetime.now(),
                    witness=f"{edge.from_uid} → {edge.to_uid} (self-loop)"
                ))

        # Sort by risk level
        risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        cycles.sort(key=lambda c: risk_order[c.risk_level])

        return CycleResult(
            has_cycles=len(cycles) > 0,
            cycles=tuple(cycles),
            strongly_connected_components=tuple(tuple(scc) for scc in sccs)
        )

    def _classify_cycle_risk(
        self,
        cycle_path: Tuple[str, ...],
        graph: SkeletonGraph
    ) -> RiskLevel:
        """Classify risk level of a circular dependency.

        Rules:
        - CRITICAL: Cycle involves async/lock behavioral tags
        - HIGH: Cycle involves database_io or network_io tags
        - MEDIUM: Cycle has 3+ modules
        - LOW: Cycle has exactly 2 modules
        """
        # Build node map for behavioral tag lookup
        node_map = {node.uid: node for node in graph.nodes}

        # Check behavioral tags in cycle
        has_async_lock = False
        has_database_network = False

        for uid in cycle_path[:-1]:  # Exclude last (duplicate of first)
            if uid in node_map:
                tags = node_map[uid].behavioral_tags
                if any(tag in tags for tag in ["async", "lock", "mutex", "semaphore"]):
                    has_async_lock = True
                if any(tag in tags for tag in ["database", "network", "database_io", "network_io"]):
                    has_database_network = True

        # Classify
        if has_async_lock:
            return "CRITICAL"
        elif has_database_network:
            return "HIGH"
        elif len(cycle_path) > 4:  # 3+ modules (path includes start twice)
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_witness(self, cycle_path: Tuple[str, ...]) -> str:
        """Generate witness trace for a cycle."""
        path_str = " → ".join(cycle_path)
        return f"{path_str} (circular dependency detected)"

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
        """
        # Build node map
        node_map = {node.uid: node for node in graph.nodes}

        if from_uid not in node_map or to_uid not in node_map:
            return PathResult(
                from_uid=from_uid,
                to_uid=to_uid,
                path=(),
                found=False,
                depth=0
            )

        if from_uid == to_uid:
            return PathResult(
                from_uid=from_uid,
                to_uid=to_uid,
                path=(),
                found=True,
                depth=0
            )

        # Build edge map for path reconstruction
        edge_map: Dict[Tuple[str, str], DependencyEdge] = {}
        for edge in graph.edges:
            edge_map[(edge.from_uid, edge.to_uid)] = edge

        # BFS to find shortest path
        visited: Set[str] = {from_uid}
        parent: Dict[str, str] = {}
        queue = deque([from_uid])

        while queue:
            current_uid = queue.popleft()

            # Check if reached target
            if current_uid == to_uid:
                # Reconstruct path
                path: List[DependencyEdge] = []
                node = to_uid

                while node != from_uid:
                    parent_node = parent[node]
                    edge = edge_map.get((parent_node, node))
                    if edge:
                        path.append(edge)
                    node = parent_node

                path.reverse()

                return PathResult(
                    from_uid=from_uid,
                    to_uid=to_uid,
                    path=tuple(path),
                    found=True,
                    depth=len(path)
                )

            # Explore neighbors
            if current_uid in graph.adjacency_out:
                for next_uid in graph.adjacency_out[current_uid]:
                    if next_uid not in visited:
                        visited.add(next_uid)
                        parent[next_uid] = current_uid
                        queue.append(next_uid)

        # No path found
        return PathResult(
            from_uid=from_uid,
            to_uid=to_uid,
            path=(),
            found=False,
            depth=0
        )

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
        """
        # Build node map
        node_map = {node.uid: node for node in graph.nodes}

        if module_uid not in node_map:
            return DependencyResult(
                module_uid=module_uid,
                related_modules=(),
                depth=0,
                traversal_path=(module_uid,)
            )

        visited: Set[str] = {module_uid}
        related: List[ModuleNode] = []
        traversal_path: List[str] = []

        # BFS traversal
        queue = deque([(module_uid, 0)])

        while queue:
            current_uid, current_depth = queue.popleft()

            # Stop if reached max depth
            if current_depth >= depth:
                continue

            # Get outgoing edges (dependencies)
            if current_uid in graph.adjacency_out:
                for next_uid in graph.adjacency_out[current_uid]:
                    if next_uid not in visited:
                        visited.add(next_uid)
                        traversal_path.append(next_uid)

                        # Add module to results
                        if next_uid in node_map:
                            related.append(node_map[next_uid])

                        # Enqueue for next level
                        queue.append((next_uid, current_depth + 1))

        return DependencyResult(
            module_uid=module_uid,
            related_modules=tuple(related),
            depth=depth,
            traversal_path=tuple(traversal_path)
        )

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
        """
        # Build node map
        node_map = {node.uid: node for node in graph.nodes}

        if module_uid not in node_map:
            return DependencyResult(
                module_uid=module_uid,
                related_modules=(),
                depth=0,
                traversal_path=(module_uid,)
            )

        visited: Set[str] = {module_uid}
        related: List[ModuleNode] = []
        traversal_path: List[str] = []

        # BFS traversal (reverse direction)
        queue = deque([(module_uid, 0)])

        while queue:
            current_uid, current_depth = queue.popleft()

            # Stop if reached max depth
            if current_depth >= depth:
                continue

            # Get incoming edges (dependents)
            if current_uid in graph.adjacency_in:
                for next_uid in graph.adjacency_in[current_uid]:
                    if next_uid not in visited:
                        visited.add(next_uid)
                        traversal_path.append(next_uid)

                        # Add module to results
                        if next_uid in node_map:
                            related.append(node_map[next_uid])

                        # Enqueue for next level
                        queue.append((next_uid, current_depth + 1))

        return DependencyResult(
            module_uid=module_uid,
            related_modules=tuple(related),
            depth=depth,
            traversal_path=tuple(traversal_path)
        )

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
        """
        for node in graph.nodes:
            if node.uid == module_uid:
                return node
        return None
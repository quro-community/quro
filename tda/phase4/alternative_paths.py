"""Alternative Path Generation using K-Shortest Paths

@module quro.tda.phase4.alternative_paths
@intent Generate multiple alternative trajectories for comparison and selection.
"""

import heapq
import logging
from typing import Dict, List, Optional, Set

from .energy_model import compute_transition_energy
from .heuristic import compute_heuristic

logger = logging.getLogger(__name__)


class AlternativePathGenerator:
    """Generate k-shortest paths using Yen's algorithm."""

    def __init__(self, field_data, escape_mechanism, intent_encoder):
        """Initialize alternative path generator.

        Args:
            field_data: FieldData instance
            escape_mechanism: EscapeMechanism instance
            intent_encoder: IntentEncoder instance
        """
        self.field_data = field_data
        self.escape_mechanism = escape_mechanism
        self.intent_encoder = intent_encoder

    def generate_k_shortest_paths(
        self,
        start: str,
        goal: str,
        intent_vector: Optional[List[float]],
        constraints,
        k: int = 3,
    ) -> List[tuple[List[str], float]]:
        """Generate k-shortest paths using Yen's algorithm.

        Args:
            start: Start symbol
            goal: Goal symbol
            intent_vector: Intent vector (optional)
            constraints: TrajectoryConstraints
            k: Number of alternative paths to generate

        Returns:
            List of (path, cost) tuples, sorted by cost
        """
        # Find first shortest path
        first_path, first_cost = self._find_shortest_path(
            start, goal, intent_vector, constraints, excluded_edges=set()
        )

        if first_path is None:
            return []

        # Store k-shortest paths
        A = [(first_path, first_cost)]

        # Candidate paths (priority queue)
        B = []

        for k_iter in range(1, k):
            # Get previous shortest path
            prev_path, prev_cost = A[-1]

            # For each node in previous path (except goal)
            for i in range(len(prev_path) - 1):
                # Spur node
                spur_node = prev_path[i]

                # Root path (from start to spur node)
                root_path = prev_path[:i + 1]

                # Edges to exclude
                excluded_edges = set()

                # Exclude edges that would create duplicate paths
                for path, _ in A:
                    if len(path) > i and path[:i + 1] == root_path:
                        # Exclude edge from path[i] to path[i+1]
                        if i + 1 < len(path):
                            excluded_edges.add((path[i], path[i + 1]))

                # Find spur path (from spur node to goal)
                spur_path, spur_cost = self._find_shortest_path(
                    spur_node,
                    goal,
                    intent_vector,
                    constraints,
                    excluded_edges=excluded_edges,
                )

                if spur_path is not None:
                    # Combine root path + spur path
                    total_path = root_path[:-1] + spur_path
                    total_cost = self._compute_path_cost(
                        total_path, intent_vector
                    )

                    # Add to candidates if not duplicate
                    if not any(p == total_path for p, _ in B):
                        heapq.heappush(B, (total_cost, total_path))

            # No more candidates
            if not B:
                break

            # Add best candidate to A
            best_cost, best_path = heapq.heappop(B)
            A.append((best_path, best_cost))

        return A

    def _find_shortest_path(
        self,
        start: str,
        goal: str,
        intent_vector: Optional[List[float]],
        constraints,
        excluded_edges: Set[tuple[str, str]],
    ) -> tuple[Optional[List[str]], float]:
        """Find shortest path with excluded edges.

        Args:
            start: Start symbol
            goal: Goal symbol
            intent_vector: Intent vector (optional)
            constraints: TrajectoryConstraints
            excluded_edges: Set of (src, dst) edges to exclude

        Returns:
            (path, cost) tuple, or (None, inf) if no path
        """
        logger.debug(f"Finding path from {start} to {goal}, excluded edges: {len(excluded_edges)}")

        # A* search with excluded edges
        open_set = []
        heapq.heappush(open_set, (0.0, start))

        came_from: Dict[str, str] = {}
        g_score: Dict[str, float] = {start: 0.0}

        start_state = self.field_data.get_state(start)
        goal_state = self.field_data.get_state(goal)
        h_start = compute_heuristic(start_state, goal_state)
        f_score: Dict[str, float] = {start: h_start}

        closed_set: Set[str] = set()
        iterations = 0
        max_iterations = 10000  # Prevent infinite loops

        while open_set and iterations < max_iterations:
            iterations += 1

            if iterations % 100 == 0:
                logger.debug(f"A* iteration {iterations}, open_set size: {len(open_set)}, closed_set size: {len(closed_set)}")

            current_f, current = heapq.heappop(open_set)

            if current == goal:
                path = self._reconstruct_path(came_from, current)
                logger.info(f"Found path in {iterations} iterations: length={len(path)}, cost={g_score[current]:.2f}")
                return path, g_score[current]

            if current in closed_set:
                continue

            closed_set.add(current)

            if g_score[current] > constraints.max_energy:
                continue

            neighbors = self.field_data.get_neighbors(current, k=10)

            # Phase 3: Escape mechanism removed for natural backtracking
            # When A* encounters a sink node (neighbors=[]), it will naturally
            # backtrack by popping the next best node from the priority queue.
            # This preserves path causality and prevents "teleportation" jumps.
            #
            # DEPRECATED (Phase 3 - Design 88):
            # if self.escape_mechanism.is_sink(current, neighbors):
            #     logger.debug(f"Node {current} is a sink, attempting escape")
            #     escape_target = self.escape_mechanism.find_escape_target(
            #         current, intent_vector, top_k=3
            #     )
            #     if escape_target and escape_target not in closed_set:
            #         logger.debug(f"Escape target found: {escape_target}")
            #         neighbors = [escape_target]
            #     else:
            #         logger.debug(f"No escape target available")
            #         neighbors = []

            for neighbor in neighbors:
                # Skip excluded edges
                if (current, neighbor) in excluded_edges:
                    continue

                if neighbor in constraints.avoid_symbols:
                    continue

                if neighbor in closed_set:
                    continue

                neighbor_state = self.field_data.get_state(neighbor)
                if neighbor_state["friction"] > constraints.max_friction:
                    continue

                current_state = self.field_data.get_state(current)
                transition_cost = compute_transition_energy(
                    current_state, neighbor_state, intent_vector
                )

                tentative_g = g_score[current] + transition_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g

                    h = compute_heuristic(neighbor_state, goal_state)
                    f_score[neighbor] = tentative_g + h

                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        logger.warning(f"No path found after {iterations} iterations")
        return None, float('inf')

    def _reconstruct_path(
        self,
        came_from: Dict[str, str],
        current: str,
    ) -> List[str]:
        """Reconstruct path from parent pointers."""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def _compute_path_cost(
        self,
        path: List[str],
        intent_vector: Optional[List[float]],
    ) -> float:
        """Compute total cost of a path."""
        total_cost = 0.0

        for i in range(len(path) - 1):
            src_state = self.field_data.get_state(path[i])
            dst_state = self.field_data.get_state(path[i + 1])

            cost = compute_transition_energy(
                src_state, dst_state, intent_vector
            )
            total_cost += cost

        return total_cost

"""
Geometric Pathfinder

A* pathfinding with curvature-aware friction costs for Phase 3.
Integrates Ricci curvature and friction mapping for manifold traversal.
"""

import heapq
import sqlite3
from typing import Optional, Dict, Tuple, List, Set
from dataclasses import dataclass

from ..phase2.ricci_curvature import RicciCurvatureCalculator
from .friction_mapper import FrictionMapper


@dataclass(frozen=True)
class PathNode:
    """Node in A* search path."""

    symbol: str  # Symbol ID
    g_cost: float  # Cost from start
    h_cost: float  # Heuristic to goal
    parent: Optional[str]  # Parent symbol in path

    @property
    def f_cost(self) -> float:
        """Total cost f = g + h."""
        return self.g_cost + self.h_cost


@dataclass(frozen=True)
class PathResult:
    """Result of pathfinding."""

    path: List[str]  # Ordered list of symbols from start to goal
    total_cost: float  # Total path cost
    nodes_explored: int  # Number of nodes explored
    friction_costs: List[float]  # Friction cost for each edge in path
    curvatures: List[float]  # Ricci curvature for each edge in path


class GeometricPathfinder:
    """A* pathfinder with curvature-aware friction costs."""

    def __init__(
        self,
        registry_db_path: str = ".quro_context/registry.db",
        use_friction: bool = True,
        friction_alpha: float = 0.5,
        friction_beta_cap: float = 5.0,
    ):
        """Initialize geometric pathfinder.

        Args:
            registry_db_path: Path to registry.db
            use_friction: Use friction costs (True) or uniform costs (False)
            friction_alpha: Curvature sensitivity for friction mapping
            friction_beta_cap: Exponential cap for friction
        """
        self.registry_db_path = registry_db_path
        self.use_friction = use_friction
        self._conn: Optional[sqlite3.Connection] = None
        self._curvature_calc: Optional[RicciCurvatureCalculator] = None
        self._friction_mapper = FrictionMapper(
            alpha=friction_alpha,
            beta_cap=friction_beta_cap
        )

    def __enter__(self):
        """Context manager entry."""
        self._conn = sqlite3.connect(self.registry_db_path)
        self._conn.row_factory = sqlite3.Row
        self._curvature_calc = RicciCurvatureCalculator(self.registry_db_path).__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._curvature_calc:
            self._curvature_calc.__exit__(exc_type, exc_val, exc_tb)
            self._curvature_calc = None

        if self._conn:
            self._conn.close()
            self._conn = None

    def find_path(
        self,
        start: str,
        goal: str,
        max_depth: int = 10
    ) -> Optional[PathResult]:
        """Find shortest path from start to goal using A*.

        Args:
            start: Start symbol ID
            goal: Goal symbol ID
            max_depth: Maximum path depth

        Returns:
            PathResult if path found, None otherwise
        """
        if not self._conn or not self._curvature_calc:
            raise RuntimeError("GeometricPathfinder must be used as context manager")

        # A* data structures
        open_set: List[Tuple[float, str]] = []  # Priority queue (f_cost, symbol)
        closed_set: Set[str] = set()
        g_costs: Dict[str, float] = {start: 0.0}
        parents: Dict[str, Optional[str]] = {start: None}
        nodes_explored = 0

        # Initialize with start node
        h_cost = self._heuristic(start, goal)
        heapq.heappush(open_set, (h_cost, start))

        while open_set:
            # Get node with lowest f_cost
            f_cost, current = heapq.heappop(open_set)
            nodes_explored += 1

            # Goal reached
            if current == goal:
                return self._reconstruct_path(start, goal, parents, g_costs)

            # Already explored
            if current in closed_set:
                continue

            closed_set.add(current)

            # Check depth limit
            path_depth = self._get_path_depth(current, parents)
            if path_depth >= max_depth:
                continue

            # Explore neighbors
            neighbors = self._get_neighbors(current)
            for neighbor in neighbors:
                if neighbor in closed_set:
                    continue

                # Compute edge cost
                edge_cost = self._compute_edge_cost(current, neighbor)
                tentative_g = g_costs[current] + edge_cost

                # Update if better path found
                if neighbor not in g_costs or tentative_g < g_costs[neighbor]:
                    g_costs[neighbor] = tentative_g
                    parents[neighbor] = current
                    h_cost = self._heuristic(neighbor, goal)
                    f_cost = tentative_g + h_cost
                    heapq.heappush(open_set, (f_cost, neighbor))

        # No path found
        return None

    def _compute_edge_cost(self, source: str, target: str) -> float:
        """Compute edge cost (friction or uniform).

        Args:
            source: Source symbol
            target: Target symbol

        Returns:
            Edge cost
        """
        if not self.use_friction:
            return 1.0  # Uniform cost

        # Compute curvature and friction
        curvature = self._curvature_calc.compute_curvature(source, target)
        friction = self._friction_mapper.compute_friction(curvature.ricci_norm)
        return friction.friction

    def _heuristic(self, current: str, goal: str) -> float:
        """Heuristic function (admissible).

        Uses minimum possible cost (1.0 per edge) as lower bound.

        Args:
            current: Current symbol
            goal: Goal symbol

        Returns:
            Heuristic cost
        """
        # Simple heuristic: assume minimum cost of 1.0 per edge
        # In practice, could use graph distance or other metrics
        return 0.0  # Dijkstra-like (no heuristic bias)

    def _get_neighbors(self, symbol: str) -> List[str]:
        """Get outgoing neighbors of a symbol.

        Args:
            symbol: Symbol ID

        Returns:
            List of neighbor symbol IDs
        """
        cursor = self._conn.execute(
            "SELECT dst FROM edges WHERE src = ?",
            (symbol,)
        )
        return [row["dst"] for row in cursor.fetchall()]

    def _get_path_depth(self, symbol: str, parents: Dict[str, Optional[str]]) -> int:
        """Get depth of symbol in current path.

        Args:
            symbol: Symbol ID
            parents: Parent map

        Returns:
            Path depth
        """
        depth = 0
        current = symbol
        while parents.get(current) is not None:
            depth += 1
            current = parents[current]
        return depth

    def _reconstruct_path(
        self,
        start: str,
        goal: str,
        parents: Dict[str, Optional[str]],
        g_costs: Dict[str, float]
    ) -> PathResult:
        """Reconstruct path from start to goal.

        Args:
            start: Start symbol
            goal: Goal symbol
            parents: Parent map
            g_costs: Cost map

        Returns:
            PathResult with path and metadata
        """
        # Build path from goal to start
        path = []
        current = goal
        while current is not None:
            path.append(current)
            current = parents.get(current)
        path.reverse()

        # Compute friction and curvature for each edge
        friction_costs = []
        curvatures = []
        for i in range(len(path) - 1):
            source = path[i]
            target = path[i + 1]
            curvature = self._curvature_calc.compute_curvature(source, target)
            friction = self._friction_mapper.compute_friction(curvature.ricci_norm)
            friction_costs.append(friction.friction)
            curvatures.append(curvature.ricci_norm)

        return PathResult(
            path=path,
            total_cost=g_costs[goal],
            nodes_explored=len(parents),
            friction_costs=friction_costs,
            curvatures=curvatures,
        )

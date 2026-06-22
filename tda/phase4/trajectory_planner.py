"""Trajectory Planner — A* and Beam Search

@module quro.tda.phase4.trajectory_planner

Two planning modes:
  - A* (plan_trajectory): Single optimal path using energy-based cost
  - Beam Search (explore): Multi-path exploration with step-level decisions

Phase 4 v2 (Beam Search) is the recommended mode.
Phase 4 v1 (A*) is kept for backward compatibility.

Design contract (v2):
  - Paths are navigation possibilities, NOT execution traces
  - Scores are per-node, NOT cumulative along paths
  - Energy field is a hint, NOT a decision signal
  - Diversity is structural, NOT a score bonus
"""

import heapq
import json
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import duckdb
import numpy as np

logger = logging.getLogger(__name__)

from .alternative_paths import AlternativePathGenerator
from .energy_model import (
    compute_transition_energy,
    compute_vector_alignment,
    compute_intent_alignment,
)
from .escape_mechanism import EscapeMechanism
from .heuristic import compute_heuristic, BlackHoleDetector
from .intent_encoder import IntentEncoder
from .trajectory_analysis import TrajectoryAnalyzer
from .landing_hint import generate_landing_hints


@dataclass
class TrajectoryConstraints:
    """Constraints for trajectory planning.

    Attributes:
        max_energy: Maximum total energy budget
        max_friction: Maximum friction threshold
        max_hops: Maximum path length
        avoid_symbols: Symbols to avoid
    """
    max_energy: float = 10.0
    max_friction: float = 0.8
    max_hops: int = 20
    avoid_symbols: List[str] = field(default_factory=list)


@dataclass
class TrajectoryRequest:
    """Request for trajectory planning.

    Attributes:
        start: Starting symbol ID
        goal: Target symbol ID
        intent: User intent (natural language or vector)
        constraints: Optional constraints
    """
    start: str
    goal: str
    intent: str
    constraints: Optional[TrajectoryConstraints] = None


@dataclass
class TrajectoryPlan:
    """Planned trajectory with metrics.

    Attributes:
        path: List of symbol IDs forming the trajectory
        total_energy: Total energy cost
        avg_alignment: Average intent alignment
        risk_score: Average friction along path
        coherence: Path coherence (1 - direction variance)
        is_valid: Whether trajectory passes validation
        landing_hints: Optional list of top-K landing hints for code entry
    """
    path: List[str]
    total_energy: float
    avg_alignment: float
    risk_score: float
    coherence: float
    is_valid: bool
    landing_hints: Optional[List[dict]] = None


# =============================================================================
# Phase 4 v2: Exploration Engine (Beam Search)
# Replaces A* with step-level decisions and multi-path exploration.
# =============================================================================

@dataclass
class CandidateDecision:
    """A candidate node in a step decision.

    Attributes:
        node: Symbol ID
        score: Layer 2 direction score (intent alignment, single axis)
        energy_hint: Layer 3 energy hint (ranking tie-break, NOT decision-relevant)
        is_attractor: Whether this node is an attractor (metadata tag)
        friction: Friction value (for transparency)
    """
    node: str
    score: float           # Layer 2: intent alignment (0-1)
    energy_hint: float     # Layer 3: energy hint (not decision-relevant)
    is_attractor: bool     # Metadata tag
    friction: float        # For transparency


@dataclass
class RejectedNode:
    """A rejected node with reasons.

    Attributes:
        node: Symbol ID
        reasons: List of rejection reasons (e.g. "high_friction", "low_alignment")
    """
    node: str
    reasons: List[str]


@dataclass
class StepDecision:
    """A single step in beam search with explainable decisions.

    Attributes:
        step: Step number (0-indexed)
        current: Current node (beam source)
        candidates: Ranked candidate nodes that passed feasibility
        rejected: Nodes rejected with reasons (for LLM transparency)
    """
    step: int
    current: str
    candidates: List[CandidateDecision]
    rejected: List[RejectedNode]


@dataclass
class PathResult:
    """A final path candidate from beam search.

    Attributes:
        path: List of symbol IDs
        score: Direction score of the last node (NOT cumulative)
        confidence: Combined confidence (alignment × diversity)
        is_valid: Whether path passes feasibility checks
        landing_hints: Top-K landing hints
    """
    path: List[str]
    score: float           # Last node's direction score (NOT cumulative)
    confidence: float      # alignment × diversity factor
    is_valid: bool
    landing_hints: Optional[List[dict]] = None


@dataclass
class ExplorationResult:
    """Result of beam search exploration.

    Attributes:
        start: Starting symbol ID
        intent: User intent string
        beams: Beam state after each step (for debugging/visualization)
        decisions: Per-step explainable decisions
        final_paths: Top-K final path candidates
    """
    start: str
    intent: str
    beams: List[List[str]]       # Beam state after each step
    decisions: List[StepDecision]  # Per-step decisions
    final_paths: List[PathResult]  # Final path candidates


class FieldData:
    """Container for TDA field data."""

    def __init__(self, field_data_path: Path):
        """Initialize field data from TDA output.

        Args:
            field_data_path: Path to .quro_context/tda/ directory
        """
        self.field_data_path = field_data_path
        self.states: Dict[str, dict] = {}
        self.adjacency: Dict[str, List[str]] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Load manifold states and adjacency from TDA output.

        Uses pickle cache for ~10× faster loading on subsequent runs.
        Adjacency reads from DuckDB events table (primary) or JSONL fallback.
        """
        cache_path = self.field_data_path / "field_data_cache.pkl"
        manifold_path = self.field_data_path / "phase2" / "manifold_states.jsonl"
        db_path = self.field_data_path.parent / "quro_tda.duckdb"
        events_path = self.field_data_path / "phase1" / "graph_events.jsonl"

        # Determine the newest source for adjacency staleness check
        adj_source_path = db_path if db_path.exists() else events_path

        # Try to load from pickle cache first
        if cache_path.exists() and manifold_path.exists():
            manifold_mtime = manifold_path.stat().st_mtime
            cache_mtime = cache_path.stat().st_mtime

            # Use cache if it's newer than source files
            adj_mtime = adj_source_path.stat().st_mtime if adj_source_path.exists() else 0
            if cache_mtime >= manifold_mtime and cache_mtime >= adj_mtime:
                try:
                    logger.info("Loading field data from pickle cache: %s", cache_path)
                    with open(cache_path, "rb") as f:
                        cached_data = pickle.load(f)
                    self.states = cached_data["states"]
                    self.adjacency = cached_data["adjacency"]
                    logger.info("Loaded %d states and %d adjacency entries from cache",
                               len(self.states), len(self.adjacency))
                    return
                except Exception as e:
                    logger.warning("Failed to load pickle cache: %s. Rebuilding...", e)

        # Build cache from scratch
        logger.info("Building field data cache from %s", manifold_path)

        # Load manifold states from Phase 2
        if not manifold_path.exists():
            raise FileNotFoundError(f"Manifold states not found: {manifold_path}")

        with open(manifold_path) as f:
            for line in f:
                if line.strip():
                    state = json.loads(line)
                    symbol = state["symbol"]

                    # Extract position
                    pos_data = state["manifold_position"]
                    if isinstance(pos_data, dict) and "embedding" in pos_data:
                        embedding = pos_data["embedding"]
                    else:
                        embedding = pos_data
                    position = embedding[:3] if len(embedding) >= 3 else [0, 0, 0]

                    # Extract energy
                    energy_data = state.get("energy", {})
                    total_energy = energy_data.get("total", 0.0)

                    # Extract field data
                    friction = state.get("friction", 0.5)
                    field_direction = state.get("field_direction", [0, 0, 0])

                    self.states[symbol] = {
                        "position": position,
                        "direction": field_direction,
                        "friction": friction,
                        "energy": total_energy,
                    }

        # Load adjacency from DuckDB (primary) or JSONL (fallback)
        if db_path.exists():
            self._load_adjacency_from_duckdb(db_path)
        elif events_path.exists():
            self._load_adjacency_from_jsonl(events_path)

        logger.info("Loaded %d states and %d adjacency entries",
                   len(self.states), len(self.adjacency))

        # Save to pickle cache for next time
        try:
            logger.info("Saving field data cache to %s", cache_path)
            with open(cache_path, "wb") as f:
                pickle.dump({
                    "states": self.states,
                    "adjacency": self.adjacency
                }, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info("Cache saved successfully")
        except Exception as e:
            logger.warning("Failed to save pickle cache: %s", e)

    def _load_adjacency_from_duckdb(self, db_path: Path) -> None:
        """Load adjacency from DuckDB events table."""
        logger.info("Building adjacency from DuckDB: %s", db_path)
        try:
            conn = duckdb.connect(str(db_path), read_only=True)
            rows = conn.execute(
                "SELECT src, dst FROM events "
                "WHERE event_type = 'EDGE_TRAVERSE' "
                "AND src LIKE 'sym::%' AND dst LIKE 'sym::%'"
            ).fetchall()
            conn.close()

            for src, dst in rows:
                if src not in self.adjacency:
                    self.adjacency[src] = []
                if dst not in self.adjacency[src]:
                    self.adjacency[src].append(dst)

            logger.info("DuckDB: loaded %d adjacency edges for %d symbols",
                       len(rows), len(self.adjacency))
        except Exception as e:
            logger.warning("Failed to load adjacency from DuckDB: %s", e)

    def _load_adjacency_from_jsonl(self, events_path: Path) -> None:
        """Load adjacency from JSONL file (fallback)."""
        logger.info("Building adjacency from JSONL: %s", events_path)
        with open(events_path) as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    if event.get("event_type") == "EDGE_TRAVERSE":
                        edge = event.get("edge", {})
                        src = edge.get("src")
                        dst = edge.get("dst")
                        if src and dst and src.startswith("sym::") and dst.startswith("sym::"):
                            if src not in self.adjacency:
                                self.adjacency[src] = []
                            if dst not in self.adjacency[src]:
                                self.adjacency[src].append(dst)
                    else:
                        src = event.get("src")
                        dst = event.get("dst")
                        if src and dst:
                            if src not in self.adjacency:
                                self.adjacency[src] = []
                            if dst not in self.adjacency[src]:
                                self.adjacency[src].append(dst)

    def get_state(self, symbol: str) -> dict:
        """Get state for a symbol.

        Args:
            symbol: Symbol ID

        Returns:
            State dict with position, direction, friction, energy

        Raises:
            KeyError: If symbol not found
        """
        if symbol not in self.states:
            raise KeyError(f"Symbol not found: {symbol}")
        return self.states[symbol]

    def get_neighbors(self, symbol: str, k: int = 10) -> List[str]:
        """Get neighbors of a symbol.

        Args:
            symbol: Symbol ID
            k: Maximum number of neighbors (beam width)

        Returns:
            List of neighbor symbol IDs
        """
        neighbors = self.adjacency.get(symbol, [])
        # Filter to only neighbors that exist in states
        valid_neighbors = [n for n in neighbors if n in self.states]
        return valid_neighbors[:k]


class TrajectoryPlanner:
    """A* trajectory planner on semantic field."""

    def __init__(self, field_data_path: Path):
        """Initialize trajectory planner.

        Args:
            field_data_path: Path to .quro_context/tda/ directory
        """
        self.field_data = FieldData(field_data_path)
        self.escape_mechanism = EscapeMechanism(field_data_path)
        self.intent_encoder = IntentEncoder(embedding_dim=128)
        self.trajectory_analyzer = TrajectoryAnalyzer()
        self.alternative_path_generator = AlternativePathGenerator(
            self.field_data,
            self.escape_mechanism,
            self.intent_encoder,
        )

        # Phase 2: Initialize black hole detector for gravity field
        tda_db_path = field_data_path.parent / "tda_index.db"
        self.black_hole_detector = BlackHoleDetector(tda_db_path)

        # Store field_data_path for symbol resolution
        self.field_data_path = field_data_path

        # Phase 4 v2: Exploration Engine (Beam Search)
        self.exploration_engine = ExplorationEngine(self.field_data)

    def explore(
        self,
        start: str,
        intent: str,
        steps: int = 5,
        beam_width: int = 5,
        max_hops: int = 20,
    ) -> ExplorationResult:
        """Explore from start following intent using Beam Search.

        Phase 4 v2 replaces A* with a three-layer decision structure:
          Layer 1: Feasibility Gate (hard reject with reasons)
          Layer 2: Direction Score (single axis: intent alignment)
          Layer 3: Energy Hint (ranking tie-break, NOT decision)
          Layer 4: Diversity Enforcement (structure-level)

        Args:
            start: Starting symbol ID
            intent: User intent string
            steps: Maximum exploration steps
            beam_width: Number of candidates to keep per step
            max_hops: Maximum path length

        Returns:
            ExplorationResult with beams, decisions, and final paths
        """
        return self.exploration_engine.explore(
            start=start,
            intent=intent,
            steps=steps,
            beam_width=beam_width,
            max_hops=max_hops,
            intent_vector=None,
        )

    def plan_trajectory(
        self,
        request: TrajectoryRequest,
    ) -> Optional[TrajectoryPlan]:
        """Plan optimal trajectory using A* on semantic field.

        Args:
            request: Trajectory planning request

        Returns:
            TrajectoryPlan if path found, None otherwise
        """
        start = request.start
        goal = request.goal
        intent_vector = self._encode_intent(request.intent)
        constraints = request.constraints or TrajectoryConstraints()

        # Validate start and goal exist
        if start not in self.field_data.states:
            raise ValueError(f"Start symbol not found: {start}")
        if goal not in self.field_data.states:
            raise ValueError(f"Goal symbol not found: {goal}")

        # Initialize A* data structures
        open_set = []  # Priority queue: (f_score, node)
        heapq.heappush(open_set, (0.0, start))

        came_from: Dict[str, str] = {}  # Parent pointers
        g_score: Dict[str, float] = {start: 0.0}  # Cost from start

        start_state = self.field_data.get_state(start)
        goal_state = self.field_data.get_state(goal)
        h_start = compute_heuristic(
            start_state,
            goal_state,
            black_hole_detector=self.black_hole_detector,
            node_symbol=start
        )
        f_score: Dict[str, float] = {start: h_start}

        closed_set: Set[str] = set()  # Visited nodes

        while open_set:
            current_f, current = heapq.heappop(open_set)

            # Goal reached
            if current == goal:
                path = self._reconstruct_path(came_from, current)
                plan = self._create_trajectory_plan(path, g_score, intent_vector)

                # Generate landing hints
                plan.landing_hints = generate_landing_hints(
                    path=path,
                    field_data=self.field_data,
                    symbol_resolver=self._resolve_symbol_metadata,
                    top_k=3,
                )

                return plan

            # Already visited
            if current in closed_set:
                continue

            closed_set.add(current)

            # Energy budget exceeded
            if g_score[current] > constraints.max_energy:
                continue

            # Path too long
            path_length = len(self._reconstruct_path(came_from, current))
            if path_length > constraints.max_hops:
                continue

            # Get neighbors
            neighbors = self.field_data.get_neighbors(current, k=10)

            # Phase 3: Escape mechanism removed for natural backtracking
            # When A* encounters a sink node (neighbors=[]), it will naturally
            # backtrack by popping the next best node from the priority queue.
            # This preserves path causality and prevents "teleportation" jumps.
            #
            # DEPRECATED (Phase 3 - Design 88):
            # if self.escape_mechanism.is_sink(current, neighbors):
            #     escape_target = self.escape_mechanism.find_escape_target(
            #         current,
            #         intent_vector=intent_vector,
            #         top_k=3
            #     )
            #     if escape_target and escape_target not in closed_set:
            #         neighbors = [escape_target]
            #     else:
            #         # No escape possible, continue with empty neighbors
            #         neighbors = []

            # Expand neighbors
            for neighbor in neighbors:
                # Skip if in avoid list
                if neighbor in constraints.avoid_symbols:
                    continue

                # Skip if already visited
                if neighbor in closed_set:
                    continue

                # Friction gate (prune high-friction nodes)
                neighbor_state = self.field_data.get_state(neighbor)
                if neighbor_state["friction"] > constraints.max_friction:
                    continue

                # Compute tentative g_score
                current_state = self.field_data.get_state(current)
                transition_cost = compute_transition_energy(
                    current_state,
                    neighbor_state,
                    intent_vector,
                )

                tentative_g = g_score[current] + transition_cost

                # Update if better path found
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g

                    h = compute_heuristic(
                        neighbor_state,
                        goal_state,
                        black_hole_detector=self.black_hole_detector,
                        node_symbol=neighbor
                    )
                    f_score[neighbor] = tentative_g + h

                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        # No path found
        return None

    def plan_alternative_trajectories(
        self,
        request: TrajectoryRequest,
        k: int = 3,
    ) -> List[TrajectoryPlan]:
        """Plan k alternative trajectories and rank by quality.

        Args:
            request: Trajectory planning request
            k: Number of alternative paths to generate

        Returns:
            List of TrajectoryPlan objects, ranked by quality (best first)
        """
        start = request.start
        goal = request.goal
        intent_vector = self._encode_intent(request.intent)
        constraints = request.constraints or TrajectoryConstraints()

        # Validate start and goal exist
        if start not in self.field_data.states:
            raise ValueError(f"Start symbol not found: {start}")
        if goal not in self.field_data.states:
            raise ValueError(f"Goal symbol not found: {goal}")

        # Generate k-shortest paths
        paths_with_costs = self.alternative_path_generator.generate_k_shortest_paths(
            start, goal, intent_vector, constraints, k=k
        )

        if not paths_with_costs:
            return []

        # Create trajectory plans
        plans = []
        g_score = {}
        for path, cost in paths_with_costs:
            # Build g_score map for this path
            g_score[path[-1]] = cost
            plan = self._create_trajectory_plan(path, g_score, intent_vector)
            plans.append(plan)

        # Rank by quality
        rankings = self.trajectory_analyzer.rank_trajectories(plans)

        # Return plans sorted by quality
        ranked_plans = [plans[i] for i, _ in rankings]
        return ranked_plans

    def compare_plans(self, plan1: TrajectoryPlan, plan2: TrajectoryPlan):
        """Compare two trajectory plans.

        Args:
            plan1: First trajectory plan
            plan2: Second trajectory plan

        Returns:
            TrajectoryComparison with recommendation
        """
        return self.trajectory_analyzer.compare_trajectories(plan1, plan2)

    def assess_plan_quality(self, plan: TrajectoryPlan):
        """Assess trajectory plan quality.

        Args:
            plan: Trajectory plan to assess

        Returns:
            TrajectoryQuality with detailed scores
        """
        return self.trajectory_analyzer.assess_quality(plan)

    def _encode_intent(self, intent: str) -> Optional[List[float]]:
        """Encode user intent to vector.

        Args:
            intent: Natural language intent

        Returns:
            Intent vector (128-dim) or None
        """
        return self.intent_encoder.encode(intent)

    def _reconstruct_path(
        self,
        came_from: Dict[str, str],
        current: str,
    ) -> List[str]:
        """Reconstruct path from parent pointers.

        Args:
            came_from: Parent pointer map
            current: Goal node

        Returns:
            Path from start to goal
        """
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def _create_trajectory_plan(
        self,
        path: List[str],
        g_score: Dict[str, float],
        intent_vector: Optional[List[float]],
    ) -> TrajectoryPlan:
        """Create trajectory plan with metrics.

        Args:
            path: Planned path
            g_score: Cost map from A*
            intent_vector: User intent vector

        Returns:
            TrajectoryPlan with computed metrics
        """
        # Total energy
        total_energy = g_score[path[-1]]

        # Average alignment (kept for backward compatibility)
        alignments = []
        for i in range(len(path) - 1):
            src_state = self.field_data.get_state(path[i])
            dst_state = self.field_data.get_state(path[i + 1])
            alignment = compute_vector_alignment(
                src_state["direction"],
                dst_state["direction"]
            )
            alignments.append(alignment)
        avg_alignment = sum(alignments) / len(alignments) if alignments else 0.0

        # Risk score (average friction)
        frictions = [self.field_data.get_state(node)["friction"] for node in path]
        risk_score = sum(frictions) / len(frictions)

        # Coherence - NEW: Tensor path integral instead of variance
        coherence = self._compute_tensor_path_integral(path, intent_vector)

        # Validation
        # Note: Tensor path integral produces lower coherence values (0.2-0.4 range)
        # compared to variance-based coherence (0.8-1.0 range)
        is_valid = bool(
            total_energy <= 10.0 and
            risk_score <= 0.8 and
            coherence > 0.15  # Adjusted threshold for tensor integral
        )

        return TrajectoryPlan(
            path=path,
            total_energy=total_energy,
            avg_alignment=avg_alignment,
            risk_score=risk_score,
            coherence=coherence,
            is_valid=is_valid,
        )

    def _compute_trajectory_coherence(self, directions: List[List[float]]) -> float:
        """Compute trajectory coherence (1 - direction variance).

        DEPRECATED: This method is kept for backward compatibility.
        Use _compute_tensor_path_integral() instead for better discrimination.

        Args:
            directions: List of direction vectors

        Returns:
            Coherence score in [0, 1] (1 = perfectly coherent)
        """
        if len(directions) < 2:
            return 1.0

        mat = np.array(directions)
        variance = np.var(mat, axis=0).mean()

        # Convert variance to coherence (lower variance = higher coherence)
        coherence = 1.0 / (1.0 + variance)
        return coherence

    def _compute_tensor_path_integral(
        self,
        path: List[str],
        intent_vector: Optional[List[float]],
    ) -> float:
        """Compute path quality via tensor integration along trajectory.

        Uses friction as a proxy for Ricci curvature (until Phase 2.5 Forman-Ricci
        is integrated). Higher friction = more negative equivalent curvature = lower quality.

        Formula: ∏ ((1 - friction) × alignment_factor) along each edge
        Then apply geometric mean: result^(1/(n-1)) to prevent underflow

        Args:
            path: List of symbol IDs forming the trajectory
            intent_vector: User intent vector (optional)

        Returns:
            Quality score in [0, 1] (higher = better)
        """
        if len(path) < 2:
            return 1.0

        # Initialize tensor quality (multiplicative identity)
        tensor_quality = 1.0

        for i in range(len(path) - 1):
            src = path[i]
            dst = path[i + 1]

            # Get friction from destination node (proxy for Ricci curvature)
            dst_state = self.field_data.get_state(dst)
            friction = dst_state["friction"]

            # Map friction to curvature factor
            # Higher friction (bottom layer, architectural boundary) = lower quality
            # friction ∈ [0, 1], so (1 - friction) ∈ [0, 1]
            curvature_factor = 1.0 - friction

            # Get intent alignment from source node
            src_state = self.field_data.get_state(src)
            src_direction = src_state["direction"]

            if intent_vector and src_direction:
                # Compute alignment with intent
                alignment = compute_vector_alignment(src_direction, intent_vector)
                # alignment ∈ [-1, 1], map to [0.85, 1.0] to maintain high base quality
                # Even low alignment shouldn't kill the path quality
                alignment_factor = 0.85 + 0.15 * ((alignment + 1.0) / 2.0)
            else:
                # No intent vector, use high neutral factor to reach 0.8-0.9 range
                alignment_factor = 0.98

            # Tensor product (multiplicative integration)
            edge_quality = curvature_factor * alignment_factor
            tensor_quality *= edge_quality

        # Apply geometric mean to prevent underflow on long paths
        # This keeps the score in a human-interpretable range (0.7-0.9)
        n_edges = len(path) - 1
        coherence = tensor_quality ** (1.0 / n_edges)

        return coherence

    def _resolve_symbol_metadata(self, symbol: str) -> Optional[dict]:
        """Resolve symbol metadata (file, line) from index.

        Args:
            symbol: Symbol ID (e.g., 'sym::build_offline_index')

        Returns:
            dict with 'file' and 'line' keys, or None if not found
        """
        # Try to load from registry database (aliases table)
        try:
            registry_db_path = self.field_data_path.parent / "registry.db"
            if not registry_db_path.exists():
                return None

            import sqlite3
            conn = sqlite3.connect(str(registry_db_path))
            cursor = conn.cursor()

            # Query symbol metadata from aliases table
            # Use the first alias (primary definition)
            cursor.execute(
                "SELECT path, line FROM aliases WHERE symbol_id = ? LIMIT 1",
                (symbol,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    "file": row[0],
                    "line": row[1],
                }
        except Exception as e:
            logger.warning("Failed to resolve symbol metadata for %s: %s", symbol, e)

        return None


# =============================================================================
# Phase 4 v2: Exploration Engine (Beam Search)
# =============================================================================

# Layer 1: Feasibility thresholds
FRICTION_THRESHOLD = 0.8    # Nodes with friction > this are rejected
ALIGNMENT_THRESHOLD = 0.3    # Nodes with intent alignment < this are rejected
COHERENCE_THRESHOLD = 0.2    # Nodes with low coherence are rejected

# Layer 4: Diversity threshold
DIVERSITY_THRESHOLD = 0.6    # Jaccard similarity threshold for path diversity


class ExplorationEngine:
    """Beam search exploration engine with step-level decisions.

    Replaces A* with a three-layer decision structure:
      Layer 1: Feasibility Gate (hard reject with reasons)
      Layer 2: Direction Score (single axis: intent alignment)
      Layer 3: Energy Hint (ranking tie-break, NOT decision)
      Layer 4: Diversity Enforcement (structure-level)

    Key design:
      - Scores are per-node, NOT cumulative along paths
      - Diversity is structural, NOT a score bonus
      - All rejections include reasons (for LLM transparency)
    """

    def __init__(self, field_data: "FieldData"):
        """Initialize exploration engine.

        Args:
            field_data: FieldData instance with states and adjacency
        """
        self.field_data = field_data

    def explore(
        self,
        start: str,
        intent: str,
        steps: int = 5,
        beam_width: int = 5,
        max_hops: int = 20,
        intent_vector: Optional[List[float]] = None,
    ) -> ExplorationResult:
        """Run beam search exploration from start following intent.

        Args:
            start: Starting symbol ID
            intent: User intent string (for display)
            steps: Maximum number of exploration steps
            beam_width: Number of candidates to keep per step
            max_hops: Maximum path length
            intent_vector: Pre-encoded intent vector (128-dim)

        Returns:
            ExplorationResult with beams, decisions, and final paths
        """
        if intent_vector is None:
            intent_vector = self._encode_intent(intent)

        if start not in self.field_data.states:
            raise ValueError(f"Start symbol not found: {start}")

        # Beam: list of (path, last_score) tuples
        beams: List[List[str]] = [[start]]
        decisions: List[StepDecision] = []
        step = 0

        while beams and step < steps:
            # Expand all beam paths
            all_candidates: List[Tuple[List[str], float, str]] = []

            for path in beams:
                current = path[-1]

                # Get neighbors
                neighbors = self.field_data.get_neighbors(current, k=20)
                if not neighbors:
                    continue

                for neighbor in neighbors:
                    if neighbor in path:  # Avoid cycles
                        continue

                    try:
                        node_state = self.field_data.get_state(neighbor)
                    except KeyError:
                        continue

                    # Layer 1: Feasibility
                    feasible, reasons = self._compute_feasibility(
                        neighbor, node_state, intent_vector
                    )
                    if not feasible:
                        continue

                    # Layer 2: Direction score (single axis)
                    score = self._compute_direction(node_state, intent_vector)

                    all_candidates.append((path + [neighbor], score, neighbor))

            if not all_candidates:
                break

            # Sort by direction score (Layer 2 primary)
            all_candidates.sort(key=lambda x: x[1], reverse=True)

            # Layer 4: Enforce diversity on top candidates
            diverse_candidates = self._enforce_diversity(all_candidates, beam_width)

            # Build step decisions (for transparency)
            step_decision = self._build_step_decision(
                beams, diverse_candidates, all_candidates, step, intent_vector
            )
            decisions.append(step_decision)

            # Extract new beams
            beams = [candidate[0] for candidate in diverse_candidates]

            # Stop if all beams are at max length
            if all(len(path) >= max_hops for path in beams):
                break

            step += 1

        # Build final paths
        final_paths = self._build_final_paths(beams, intent_vector)

        return ExplorationResult(
            start=start,
            intent=intent,
            beams=beams,
            decisions=decisions,
            final_paths=final_paths,
        )

    def _compute_feasibility(
        self,
        node: str,
        node_state: dict,
        intent_vector: Optional[List[float]],
    ) -> Tuple[bool, List[str]]:
        """Layer 1: Hard feasibility gate with explainable rejection reasons.

        Args:
            node: Symbol ID
            node_state: Node state dict
            intent_vector: Intent vector

        Returns:
            (feasible, reasons) tuple
        """
        reasons: List[str] = []

        # Friction gate
        friction = node_state.get("friction", 0.0)
        if friction > FRICTION_THRESHOLD:
            reasons.append("high_friction")

        # Intent alignment gate — only if direction data exists
        if intent_vector:
            direction = node_state.get("direction", None)
            if direction and any(v != 0 for v in direction):
                alignment = self._compute_intent_alignment(node_state, intent_vector)
                if alignment < ALIGNMENT_THRESHOLD:
                    reasons.append("low_alignment")
            # No direction = neutral (can't reject)
        else:
            alignment = 1.0  # No intent = no penalty

        # Semantic coherence gate — only if direction data exists
        coherence = self._compute_coherence(node, node_state)
        if coherence < COHERENCE_THRESHOLD:
            # Only reject if we have meaningful direction data
            direction = node_state.get("direction", None)
            if direction and any(v != 0 for v in direction):
                reasons.append("incoherent")
            # No direction = assume coherent (neutral pass)

        return (len(reasons) == 0, reasons)

    def _compute_direction(
        self,
        node_state: dict,
        intent_vector: Optional[List[float]],
    ) -> float:
        """Layer 2: Single-axis direction score (intent alignment only).

        This is the ONLY axis used for ranking. No energy, no centrality.

        Args:
            node_state: Node state dict
            intent_vector: Intent vector

        Returns:
            Alignment score in [0, 1] (1 = perfectly aligned)
            Returns 0.5 (neutral) if no direction data.
        """
        direction = node_state.get("direction", None)
        if not intent_vector or not direction or not any(v != 0 for v in direction):
            return 0.5  # Neutral if no direction data

        return self._compute_intent_alignment(node_state, intent_vector)

    def _compute_intent_alignment(
        self,
        node_state: dict,
        intent_vector: List[float],
    ) -> float:
        """Compute alignment between node direction and intent vector.

        Args:
            node_state: Node state dict with 'direction' key
            intent_vector: User intent vector (128-dim)

        Returns:
            Alignment score in [0, 1]
        """
        direction = node_state.get("direction", None)
        if not direction:
            return 0.5  # Neutral if no direction

        return compute_intent_alignment(direction, intent_vector)

    def _compute_coherence(self, node: str, node_state: dict) -> float:
        """Compute local semantic coherence.

        Uses direction norm as a proxy for signal strength.
        Low norm = low signal = could be incoherent.

        Args:
            node: Symbol ID
            node_state: Node state dict

        Returns:
            Coherence score in [0, 1]
        """
        direction = node_state.get("direction", None)
        if not direction:
            return 1.0  # No data, assume coherent

        direction_arr = np.array(direction)
        norm = float(np.linalg.norm(direction_arr))
        # Typical norms are 0.1-2.0; normalize to [0, 1]
        norm_score = min(norm / 1.5, 1.0) if norm > 0 else 0.0
        return norm_score

    def _enforce_diversity(
        self,
        candidates: List[Tuple[List[str], float, str]],
        beam_width: int,
    ) -> List[Tuple[List[str], float, str]]:
        """Layer 4: Enforce diversity at the SET level.

        This is NOT a score bonus — it removes lower-scored paths that are
        too similar to higher-scored ones.

        Args:
            candidates: Sorted list of (path, score, last_node)
            beam_width: Number to keep

        Returns:
            Diverse subset of candidates
        """
        if len(candidates) <= beam_width:
            return candidates

        selected: List[Tuple[List[str], float, str]] = []

        for candidate in candidates:
            if len(selected) >= beam_width:
                break

            path = candidate[0]
            is_duplicate = False

            for existing_path, _, _ in selected:
                similarity = self._path_similarity(path, existing_path)
                if similarity > DIVERSITY_THRESHOLD:
                    is_duplicate = True
                    break

            if not is_duplicate:
                selected.append(candidate)

        # If too many dropped, fill with next-best diverse candidates
        if len(selected) < beam_width // 2:
            for candidate in candidates:
                if candidate in selected:
                    continue
                if len(selected) >= beam_width:
                    break
                selected.append(candidate)

        return selected

    def _path_similarity(self, path1: List[str], path2: List[str]) -> float:
        """Compute Jaccard similarity between two paths.

        Args:
            path1: First path
            path2: Second path

        Returns:
            Jaccard similarity in [0, 1] (1 = identical)
        """
        set1 = set(path1)
        set2 = set(path2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _build_step_decision(
        self,
        beams: List[List[str]],
        selected: List[Tuple[List[str], float, str]],
        all_candidates: List[Tuple[List[str], float, str]],
        step: int,
        intent_vector: Optional[List[float]],
    ) -> StepDecision:
        """Build explainable step decision for LLM transparency.

        Args:
            beams: Previous beam state
            selected: Selected candidates after diversity
            all_candidates: All scored candidates
            step: Step number
            intent_vector: Intent vector

        Returns:
            StepDecision with candidates and rejections
        """
        selected_last_nodes = {c[2] for c in selected}

        candidate_decisions: List[CandidateDecision] = []
        rejected_nodes: List[RejectedNode] = []

        for path, score, last_node in all_candidates:
            if last_node in selected_last_nodes:
                try:
                    state = self.field_data.get_state(last_node)
                except KeyError:
                    state = {}

                energy = state.get("energy", 0.0)
                field_role = state.get("field_role", None)
                is_attractor = field_role == "attractor"

                candidate_decisions.append(CandidateDecision(
                    node=last_node,
                    score=round(score, 3),
                    energy_hint=round(energy, 2),
                    is_attractor=is_attractor,
                    friction=round(state.get("friction", 0.0), 3),
                ))
            else:
                # This node passed feasibility but was filtered by diversity.
                # We know it passed feasibility (in all_candidates) so tag it.
                # Reasons will be empty if it had no direction data (neutral).
                try:
                    node_state = self.field_data.get_state(last_node)
                    feasible, reasons = self._compute_feasibility(
                        last_node, node_state, intent_vector
                    )
                except KeyError:
                    reasons = ["unknown"]

                # Tag as diversity-filtered if no other reasons
                if not reasons:
                    reasons = ["diversity"]

                rejected_nodes.append(RejectedNode(node=last_node, reasons=reasons))

        candidate_decisions.sort(key=lambda c: c.score, reverse=True)

        current = beams[0][-1] if beams else "unknown"

        return StepDecision(
            step=step,
            current=current,
            candidates=candidate_decisions,
            rejected=rejected_nodes,
        )

    def _build_final_paths(
        self,
        beams: List[List[str]],
        intent_vector: Optional[List[float]],
    ) -> List[PathResult]:
        """Build final path results from beam state.

        Args:
            beams: Final beam state
            intent_vector: Intent vector

        Returns:
            List of PathResult
        """
        if not beams:
            return []

        results: List[PathResult] = []

        for path in beams:
            if len(path) < 2:
                continue

            last_node = path[-1]
            try:
                last_state = self.field_data.get_state(last_node)
            except KeyError:
                continue

            # Score = last node's direction score (NOT cumulative)
            score = self._compute_direction(last_state, intent_vector)
            confidence = score

            is_valid = len(path) >= 2

            landing_hints = generate_landing_hints(
                path=path,
                field_data=self.field_data,
                symbol_resolver=None,
                top_k=3,
            )

            results.append(PathResult(
                path=path,
                score=round(score, 3),
                confidence=round(confidence, 3),
                is_valid=is_valid,
                landing_hints=landing_hints,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _encode_intent(self, intent: str) -> Optional[List[float]]:
        """Encode intent string to vector.

        Args:
            intent: Intent string

        Returns:
            Intent vector (128-dim) or None
        """
        try:
            encoder = IntentEncoder(embedding_dim=128)
            return encoder.encode(intent)
        except Exception:
            logger.warning("Failed to encode intent: %s", intent)
            return None


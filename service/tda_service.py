"""TDA Service

@module quro.service.tda_service
@intent TDA navigation and trajectory planning service.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from service.base import BaseService


class TDAService(BaseService):
    """TDA navigation and trajectory planning service.

    Provides topological data analysis and semantic navigation capabilities.
    """

    def __init__(self):
        """Initialize TDA service."""
        super().__init__()
        self._trajectory_planner = None
        self._tda_bridge = None

    def get_name(self) -> str:
        """Return service name."""
        return "tda"

    def get_description(self) -> str:
        """Return service description."""
        return "TDA navigation and trajectory planning"

    def initialize(self, workspace_root: Path) -> None:
        """Initialize service with workspace.

        Args:
            workspace_root: Path to workspace root directory

        Raises:
            ValueError: If workspace is invalid
            RuntimeError: If initialization fails
        """
        if not workspace_root.exists():
            raise ValueError(f"Workspace not found: {workspace_root}")

        if not workspace_root.is_dir():
            raise ValueError(f"Workspace is not a directory: {workspace_root}")

        # Check for TDA data
        tda_path = workspace_root / ".quro_context" / "tda"
        if not tda_path.exists():
            raise RuntimeError(
                f"TDA data not found at {tda_path}. "
                f"Run 'quro tda run' first to generate TDA data."
            )

        # Initialize trajectory planner
        try:
            from tda.phase4.trajectory_planner import TrajectoryPlanner
            self._trajectory_planner = TrajectoryPlanner(tda_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load trajectory planner: {e}") from e

        # Initialize TDA bridge
        try:
            from core.cqe.tda_bridge import TDABridge
            self._tda_bridge = TDABridge(workspace_root)
            self._tda_bridge._load_manifold_states()
        except Exception as e:
            # TDA bridge is optional
            self._tda_bridge = None

        self._workspace_root = workspace_root
        self._initialized = True

    def get_capabilities(self) -> Dict[str, Any]:
        """Return service capabilities."""
        return {
            "name": self.get_name(),
            "description": self.get_description(),
            "methods": [
                "query_next_nodes",
                "plan_trajectory",
                "explore",
                "find_upstream",
                "escape_sink",
                "classify_role",
                "get_field_vector",
                "detect_attractors",
                "get_semantic_centers",
                "get_center_reachability",
            ],
            "initialized": self._initialized,
            "has_trajectory_planner": self._trajectory_planner is not None,
            "has_tda_bridge": self._tda_bridge is not None,
        }

    def query_next_nodes(
        self,
        from_symbol: str,
        intent: str = "",
        max_candidates: int = 5,
    ) -> Dict[str, Any]:
        """Query best next navigation candidates.

        Args:
            from_symbol: Current symbol (e.g., 'sym::main')
            intent: Optional navigation intent
            max_candidates: Maximum candidates to return (default: 5)

        Returns:
            Ranked navigation candidates

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        # Use type-aware navigation
        from mcp.type_aware_navigation import get_type_aware_neighbors
        from index_builder.adapters import SQLiteRegistryAdapter

        registry_path = self._workspace_root / ".quro_context" / "registry.db"
        registry_adapter = SQLiteRegistryAdapter(db_path=registry_path)

        return get_type_aware_neighbors(
            from_symbol=from_symbol,
            registry_adapter=registry_adapter,
            tda_api=None,
            max_candidates=max_candidates,
        )

    def plan_trajectory(
        self,
        start: str,
        goal: str,
        intent: str,
        max_hops: int = 20,
        max_energy: float = 10.0,
        max_friction: float = 0.8,
    ) -> Dict[str, Any]:
        """Plan trajectory from start to goal.

        Args:
            start: Starting symbol (e.g., 'sym::main')
            goal: Goal symbol (e.g., 'sym::EventLogWriter')
            intent: Intent description
            max_hops: Maximum path length (default: 20)
            max_energy: Maximum energy budget (default: 10.0)
            max_friction: Maximum friction threshold (default: 0.8)

        Returns:
            Trajectory plan with path, energy, and quality metrics

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        from tda.phase4 import (
            TrajectoryRequest,
            TrajectoryConstraints,
        )

        request = TrajectoryRequest(
            start=start,
            goal=goal,
            intent=intent,
            constraints=TrajectoryConstraints(
                max_hops=max_hops,
                max_energy=max_energy,
                max_friction=max_friction,
            ),
        )

        plan = self._trajectory_planner.plan_trajectory(request)

        if not plan:
            return {
                "error": "No path found",
                "start": start,
                "goal": goal,
            }

        result = {
            "start": plan.path[0] if plan.path else start,
            "goal": plan.path[-1] if plan.path else goal,
            "path": plan.path,
            "total_energy": plan.total_energy,
            "avg_alignment": plan.avg_alignment,
            "risk_score": plan.risk_score,
            "coherence": plan.coherence,
            "is_valid": plan.is_valid,
        }

        if plan.landing_hints:
            result["landing_hints"] = plan.landing_hints

        return result

    def explore(
        self,
        start: str,
        intent: str = "explore codebase",
        steps: int = 5,
        beam_width: int = 5,
        max_hops: int = 20,
    ) -> Dict[str, Any]:
        """Explore codebase using beam search.

        Args:
            start: Starting symbol
            intent: Exploration intent
            steps: Maximum exploration steps (default: 5)
            beam_width: Beam width (default: 5)
            max_hops: Maximum path length (default: 20)

        Returns:
            Exploration results with multiple paths

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        result = self._trajectory_planner.explore(
            start=start,
            intent=intent,
            steps=steps,
            beam_width=beam_width,
            max_hops=max_hops,
        )

        return {
            "mode": "beam_search",
            "start": result.start,
            "intent": result.intent,
            "steps": len(result.decisions),
            "final_paths": [
                {
                    "rank": i + 1,
                    "path": path_result.path,
                    "score": path_result.score,
                    "confidence": path_result.confidence,
                    "is_valid": path_result.is_valid,
                    "landing_hints": path_result.landing_hints,
                }
                for i, path_result in enumerate(result.final_paths)
            ],
        }

    def find_upstream(
        self,
        symbol: str,
        top_k: int = 5,
        max_depth: int = 2,
    ) -> Dict[str, Any]:
        """Find upstream sources for a symbol.

        Args:
            symbol: Symbol ID (e.g., 'sym::CQEIndexPipeline')
            top_k: Number of top sources to return (default: 5)
            max_depth: Maximum traversal depth (default: 2)

        Returns:
            Upstream sources with tension and distance

        Raises:
            RuntimeError: If service not initialized or TDA bridge not available
        """
        self._ensure_initialized()

        if not self._tda_bridge:
            raise RuntimeError("TDA bridge not available")

        # Use QuroV3Service for upstream finding
        from mcp.service import QuroV3Service
        service = QuroV3Service(workspace_root=self._workspace_root)

        return service.tda_find_upstream(
            symbol=symbol,
            top_k=top_k,
            max_depth=max_depth,
        )

    def escape_sink(self, symbol: str) -> Dict[str, Any]:
        """Escape from a sink node.

        Args:
            symbol: Sink node ID

        Returns:
            Best escape target with confidence

        Raises:
            RuntimeError: If service not initialized or TDA bridge not available
        """
        self._ensure_initialized()

        if not self._tda_bridge:
            raise RuntimeError("TDA bridge not available")

        from mcp.service import QuroV3Service
        service = QuroV3Service(workspace_root=self._workspace_root)

        return service.tda_escape_sink(symbol=symbol)

    def classify_role(self, symbol: str) -> Dict[str, Any]:
        """Classify node role.

        Args:
            symbol: Symbol ID to classify

        Returns:
            Role classification (CORE_ATTRACTOR/EMITTER/SINK/TRANSIENT)

        Raises:
            RuntimeError: If service not initialized or TDA bridge not available
        """
        self._ensure_initialized()

        if not self._tda_bridge:
            raise RuntimeError("TDA bridge not available")

        from mcp.service import QuroV3Service
        service = QuroV3Service(workspace_root=self._workspace_root)

        return service.tda_classify_role(symbol=symbol)

    def get_field_vector(self, symbol: str) -> Dict[str, Any]:
        """Get field vector state at a symbol.

        Args:
            symbol: Symbol ID (e.g., 'sym::main')

        Returns:
            Complete energy state, gradient, and dynamics

        Raises:
            RuntimeError: If service not initialized or TDA bridge not available
        """
        self._ensure_initialized()

        if not self._tda_bridge:
            raise RuntimeError("TDA bridge not available")

        from mcp.service import QuroV3Service
        service = QuroV3Service(workspace_root=self._workspace_root)

        return service.tda_get_field_vector(symbol=symbol)

    def detect_attractors(self, region: str = "") -> Dict[str, Any]:
        """Detect attractors and repellers.

        Args:
            region: Optional region filter

        Returns:
            Stable attractors, unstable repellers, and saddle points

        Raises:
            RuntimeError: If service not initialized or TDA bridge not available
        """
        self._ensure_initialized()

        if not self._tda_bridge:
            raise RuntimeError("TDA bridge not available")

        attractors = []
        repellers = []
        saddle_points = []

        # Scan all symbols
        for symbol_id in self._tda_bridge._state_cache.keys():
            if region and region not in symbol_id:
                continue

            if self._tda_bridge.is_attractor(symbol_id):
                attractors.append({
                    "symbol": symbol_id,
                    "gravity": self._tda_bridge.get_gravity_score(symbol_id),
                    "energy": self._tda_bridge.get_energy_total(symbol_id),
                })
            elif self._tda_bridge.is_repeller(symbol_id):
                repellers.append({
                    "symbol": symbol_id,
                    "gravity": self._tda_bridge.get_gravity_score(symbol_id),
                    "energy": self._tda_bridge.get_energy_total(symbol_id),
                })
            elif self._tda_bridge.is_saddle_point(symbol_id):
                saddle_points.append({
                    "symbol": symbol_id,
                    "gravity": self._tda_bridge.get_gravity_score(symbol_id),
                    "energy": self._tda_bridge.get_energy_total(symbol_id),
                })

        return {
            "attractors": sorted(attractors, key=lambda x: x["gravity"], reverse=True)[:20],
            "repellers": sorted(repellers, key=lambda x: x["gravity"])[:20],
            "saddle_points": sorted(saddle_points, key=lambda x: x["energy"], reverse=True)[:20],
            "total_attractors": len(attractors),
            "total_repellers": len(repellers),
            "total_saddle_points": len(saddle_points),
        }

    def get_semantic_centers(self) -> Dict[str, Any]:
        """Get semantic centers.

        Returns:
            Partitioned semantic centers with structural affordances

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        centers_path = (
            self._workspace_root / ".quro_context" / "tda" / "phase3_5" / "semantic_centers.json"
        )

        if not centers_path.exists():
            raise RuntimeError(
                f"Semantic centers not found at {centers_path}. "
                f"Run Phase 3.5 first: python -m quro.tda.phase3_5"
            )

        with open(centers_path) as f:
            centers_data = json.load(f)

        return {
            "centers": centers_data.get("centers", []),
            "total_symbols": centers_data.get("total_symbols", 0),
            "partition_coverage": centers_data.get("partition_coverage", 0.0),
            "summary": (
                f"Detected {len(centers_data.get('centers', []))} semantic centers "
                f"covering {centers_data.get('partition_coverage', 0.0):.1%} of codebase"
            ),
        }

    def get_center_reachability(
        self,
        center_id: str,
        max_symbols: int = 50,
    ) -> Dict[str, Any]:
        """Get reachable symbols from a semantic center.

        Args:
            center_id: Center ID (e.g., C0, C1)
            max_symbols: Maximum symbols to return (default: 50)

        Returns:
            Reachable symbols from center's entry points

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        from collections import deque
        import time

        start_time = time.time()

        centers_path = (
            self._workspace_root / ".quro_context" / "tda" / "phase3_5" / "semantic_centers.json"
        )

        if not centers_path.exists():
            raise RuntimeError(
                f"Semantic centers not found. Run Phase 3.5 first."
            )

        with open(centers_path) as f:
            centers_data = json.load(f)

        centers_list = centers_data.get("centers", [])
        center_by_id = {c["id"]: c for c in centers_list}

        if center_id not in center_by_id:
            available = list(center_by_id.keys())
            raise ValueError(
                f"Center not found: {center_id}. "
                f"Available centers: {available}"
            )

        target_center = center_by_id[center_id]
        entry_points = target_center.get("topology", {}).get("entry_points", [])

        if not entry_points:
            return {
                "center_id": center_id,
                "reachable_symbols": [],
                "count": 0,
                "message": "No entry points defined for this center",
            }

        # Use GraphAdapter for BFS
        from tda.adapters import GraphAdapter

        tda_path = self._workspace_root / ".quro_context" / "tda"
        graph = GraphAdapter.create(tda_path)

        # BFS from entry points
        visited = set()
        reachable = []
        queue = deque()

        for ep in entry_points[:3]:
            queue.append((ep["symbol"], 0))
            visited.add(ep["symbol"])

        max_depth = 10
        while queue and len(reachable) < max_symbols:
            node, depth = queue.popleft()

            if depth > 0:
                reachable.append(node)

            if depth < max_depth:
                for neighbor in graph.get_out_neighbors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))

        elapsed = time.time() - start_time

        return {
            "center_id": center_id,
            "reachable_symbols": reachable[:max_symbols],
            "count": len(reachable),
            "max_symbols": max_symbols,
            "entry_points_used": [ep["symbol"] for ep in entry_points[:3]],
            "computation_time_ms": round(elapsed * 1000, 2),
        }

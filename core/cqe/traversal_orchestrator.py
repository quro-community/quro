"""Traversal Mode Orchestrator — Automatic Mode Selection and Switching

@module quro.core.cqe.traversal_orchestrator
@intent Orchestrate traversal mode selection and switching based on node state.
       Provides unified interface for all traversal modes with automatic
       mode switching and telemetry.

       Modes:
       - FORWARD: Default CQE forward traversal
       - REVERSE: Gravity-constrained reverse traversal (sink escape)
       - FIELD_GUIDED: TDA field vector navigation
       - SADDLE_ESCAPE: Automatic saddle point escape

       Decision tree:
       1. Check node state (sink, saddle, attractor, repeller)
       2. Select appropriate mode
       3. Execute traversal
       4. Record mode switches
       5. Return results with telemetry
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from adapters.graph.protocol import GraphAdapter
from core.cqe.tda_bridge import TDABridge
from core.cqe.node_state import NodeState
from core.cqe.traversal_modes import (
    TraversalMode,
    ModeSwitchEvent,
    select_traversal_mode,
    should_switch_mode,
)
from core.cqe.reverse_traverser import ReverseTraverser
from core.cqe.field_guided_traverser import (
    FieldGuidedTraverser,
    FieldNavigationMode,
)
from core.cqe.saddle_escape_traverser import SaddleEscapeTraverser
from core.cqe.upstream_navigator import UpstreamNavigator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TraversalResult:
    """Unified result for all traversal modes.

    Attributes:
        start_node: Starting node ID
        mode: Traversal mode used
        visited_nodes: Set of visited node IDs
        results: List of (node_id, score, path) tuples
        mode_switches: List of mode switch events
        telemetry: Additional telemetry data
    """
    start_node: str
    mode: TraversalMode
    visited_nodes: Set[str]
    results: List[Tuple[str, float, List[str]]]
    mode_switches: List[ModeSwitchEvent]
    telemetry: Dict[str, any]


class TraversalOrchestrator:
    """Orchestrator for automatic traversal mode selection and switching.

    Provides unified interface for all traversal modes with automatic
    mode selection based on node state.

    Invariant: Always selects optimal mode for current node state.
    """

    def __init__(
        self,
        graph: GraphAdapter,
        tda_bridge: TDABridge,
        mi_scores: Dict[str, float],
        upstream_navigator: Optional[UpstreamNavigator] = None,
    ):
        """Initialize traversal orchestrator.

        Args:
            graph: Graph adapter
            tda_bridge: TDA bridge for node state
            mi_scores: MI scores for each node
            upstream_navigator: Optional upstream navigator for escape (Phase 3.5)
        """
        self.graph = graph
        self.tda_bridge = tda_bridge
        self.mi_scores = mi_scores
        self.upstream_navigator = upstream_navigator

        # Initialize traversers
        self.reverse_traverser = ReverseTraverser(
            graph=graph,
            tda_bridge=tda_bridge,
            mi_scores=mi_scores,
        )
        self.field_traverser = FieldGuidedTraverser(
            graph=graph,
            tda_bridge=tda_bridge,
        )
        self.saddle_traverser = SaddleEscapeTraverser(
            graph=graph,
            tda_bridge=tda_bridge,
        )

    def get_node_state(self, node_id: str) -> NodeState:
        """Get complete node state for a node.

        Args:
            node_id: Node ID

        Returns:
            Complete NodeState with TDA enrichment
        """
        out_degree = self.graph.out_degree(node_id)
        in_degree = self.graph.in_degree(node_id)

        return self.tda_bridge.get_node_state(node_id, out_degree, in_degree)

    def traverse(
        self,
        start_node: str,
        max_depth: int = 3,
        top_k: int = 5,
        force_mode: Optional[TraversalMode] = None,
    ) -> TraversalResult:
        """Execute traversal with automatic mode selection.

        Args:
            start_node: Starting node ID
            max_depth: Maximum traversal depth
            top_k: Number of top results to return
            force_mode: Force specific mode (skip automatic selection)

        Returns:
            TraversalResult with results and telemetry
        """
        logger.info(
            "Starting orchestrated traversal from %s (max_depth=%d, top_k=%d)",
            start_node, max_depth, top_k,
        )

        # Get node state
        node_state = self.get_node_state(start_node)
        logger.info("Node state: %s", node_state)

        # Select mode (or use forced mode)
        if force_mode is not None:
            selected_mode = force_mode
            trigger = "forced"
            logger.info("Using forced mode: %s", selected_mode.value)
        else:
            selected_mode, trigger = select_traversal_mode(node_state)
            logger.info(
                "Selected mode: %s (trigger: %s)",
                selected_mode.value, trigger,
            )

        # Record initial mode selection
        mode_switches: List[ModeSwitchEvent] = []
        if trigger:
            mode_switches.append(
                ModeSwitchEvent(
                    from_mode=TraversalMode.FORWARD,  # Assume default is FORWARD
                    to_mode=selected_mode,
                    trigger=trigger,
                    node_id=start_node,
                    node_state=node_state,
                    escape_probability=0.0,
                )
            )

        # Execute traversal based on mode
        telemetry: Dict[str, any] = {
            "node_state": node_state,
            "selected_mode": selected_mode.value,
            "trigger": trigger,
        }

        # Handle isolated nodes (no neighbors at all)
        if node_state.is_isolated:
            logger.warning("Node %s is isolated (out=0, in=0), no traversal possible", start_node)
            return TraversalResult(
                start_node=start_node,
                mode=TraversalMode.FORWARD,
                visited_nodes={start_node},
                results=[],
                mode_switches=mode_switches,
                telemetry={**telemetry, "warning": "isolated_node_no_neighbors"},
            )

        if selected_mode == TraversalMode.REVERSE:
            # Reverse traversal (sink escape)
            result = self._execute_reverse(start_node, max_depth, top_k, telemetry)
            mode_switches.extend(result.mode_switches)
            return result

        elif selected_mode == TraversalMode.FIELD_GUIDED:
            # Field-guided traversal
            result = self._execute_field_guided(start_node, max_depth, top_k, telemetry)
            mode_switches.extend(result.mode_switches)
            return result

        elif selected_mode == TraversalMode.SADDLE_ESCAPE:
            # Saddle escape
            result = self._execute_saddle_escape(start_node, max_depth, top_k, telemetry)
            mode_switches.extend(result.mode_switches)
            return result

        else:  # FORWARD (default)
            # Forward traversal (delegate to CQE kernel)
            result = self._execute_forward(start_node, max_depth, top_k, telemetry)
            mode_switches.extend(result.mode_switches)
            return result

    def _execute_forward(
        self,
        start_node: str,
        max_depth: int,
        top_k: int,
        telemetry: Dict[str, any],
    ) -> TraversalResult:
        """Execute forward traversal using CQE kernel.

        Args:
            start_node: Starting node ID
            max_depth: Maximum traversal depth (not used by kernel, but kept for consistency)
            top_k: Number of top results
            telemetry: Telemetry dict to update

        Returns:
            TraversalResult
        """
        from core.cqe.kernel import CQEKernel

        # Execute CQE kernel traversal
        # Use very low tau to allow multi-hop traversal (reaching symbols through categories)
        # Edge weights are ~0.01, so tau=0.0001 allows 2-3 hops
        tau = 0.0001
        kernel_result = CQEKernel.query(self.graph, start_node, tau=tau)

        telemetry["forward_tau"] = tau
        telemetry["forward_visited"] = len(kernel_result.max_weights)

        # Separate symbols and categories
        symbols = {k: v for k, v in kernel_result.max_weights.items() if k.startswith('sym::')}
        categories = {k: v for k, v in kernel_result.max_weights.items() if k.startswith('cat::')}

        telemetry["forward_symbols"] = len(symbols)
        telemetry["forward_categories"] = len(categories)

        # Check if forward traversal is stuck or producing weak results
        # Trigger escape if:
        # 1. No symbols (or only self) - topological sink
        # 2. Low quality results (max score < 0.001) - semantic sink
        max_symbol_score = max(symbols.values()) if symbols else 0.0
        is_stuck = (
            len(symbols) <= 1 or  # Topological sink
            (len(symbols) > 0 and max_symbol_score < 0.001)  # Semantic sink (weak results)
        )

        if is_stuck and self.upstream_navigator:
            logger.warning(
                "Forward traversal stuck at %s (symbols=%d, max_score=%.6f), attempting upstream escape",
                start_node, len(symbols), max_symbol_score
            )

            # Attempt escape via upstream navigator
            escape_result = self.upstream_navigator.escape_sink(start_node)

            if escape_result.confidence > 0.5:
                logger.info(
                    "Escape successful: %s → %s (confidence=%.2f, reason=%s)",
                    start_node, escape_result.escape_to,
                    escape_result.confidence, escape_result.reason
                )

                # Record escape in telemetry
                telemetry["escape_attempted"] = True
                telemetry["escape_target"] = escape_result.escape_to
                telemetry["escape_confidence"] = escape_result.confidence
                telemetry["escape_reason"] = escape_result.reason

                # Resume forward traversal from escape target
                return self._execute_forward(
                    escape_result.escape_to,
                    max_depth,
                    top_k,
                    telemetry
                )
            else:
                logger.warning(
                    "Escape failed: no viable upstream sources (confidence=%.2f)",
                    escape_result.confidence
                )
                telemetry["escape_attempted"] = True
                telemetry["escape_failed"] = True

        # Prefer symbols over categories in results
        # Sort symbols by weight (descending) and take top-k
        sorted_symbols = sorted(
            symbols.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Exclude start node and take top-k symbols
        filtered_symbols = [
            (node_id, weight)
            for node_id, weight in sorted_symbols
            if node_id != start_node
        ][:top_k]

        # If we have fewer than top_k symbols, add top categories to fill
        if len(filtered_symbols) < top_k:
            sorted_categories = sorted(
                categories.items(),
                key=lambda x: x[1],
                reverse=True
            )
            remaining = top_k - len(filtered_symbols)
            filtered_symbols.extend(sorted_categories[:remaining])

        # Reconstruct paths using predecessors
        results = []
        for node_id, weight in filtered_symbols:
            path = self._reconstruct_path(kernel_result.predecessors, start_node, node_id)
            results.append((node_id, weight, path))

        return TraversalResult(
            start_node=start_node,
            mode=TraversalMode.FORWARD,
            visited_nodes=set(kernel_result.max_weights.keys()),
            results=results,
            mode_switches=[],
            telemetry=telemetry,
        )

    def _reconstruct_path(
        self,
        predecessors: Dict[str, Optional[str]],
        start_node: str,
        end_node: str,
    ) -> List[str]:
        """Reconstruct path from start to end using predecessors.

        Args:
            predecessors: Dict mapping node → predecessor
            start_node: Starting node
            end_node: Ending node

        Returns:
            List of node IDs forming the path
        """
        path = []
        current = end_node

        while current is not None:
            path.append(current)
            current = predecessors.get(current)

        path.reverse()
        return path

    def _execute_reverse(
        self,
        start_node: str,
        max_depth: int,
        top_k: int,
        telemetry: Dict[str, any],
    ) -> TraversalResult:
        """Execute reverse traversal.

        Args:
            start_node: Starting node ID
            max_depth: Maximum traversal depth
            top_k: Number of top results
            telemetry: Telemetry dict to update

        Returns:
            TraversalResult
        """
        reverse_result = self.reverse_traverser.traverse(
            start_node=start_node,
            max_depth=max_depth,
            top_k=top_k,
        )

        telemetry["reverse_visited"] = len(reverse_result.visited_nodes)
        telemetry["reverse_paths"] = len(reverse_result.paths)

        # Convert to unified format
        results = [
            (node_id, escape_prob, path)
            for node_id, escape_prob, path in reverse_result.top_escapes
        ]

        return TraversalResult(
            start_node=start_node,
            mode=TraversalMode.REVERSE,
            visited_nodes=reverse_result.visited_nodes,
            results=results,
            mode_switches=[],
            telemetry=telemetry,
        )

    def _execute_field_guided(
        self,
        start_node: str,
        max_depth: int,
        top_k: int,
        telemetry: Dict[str, any],
    ) -> TraversalResult:
        """Execute field-guided traversal.

        Args:
            start_node: Starting node ID
            max_depth: Maximum traversal depth (used as max_steps)
            top_k: Number of top results
            telemetry: Telemetry dict to update

        Returns:
            TraversalResult
        """
        # Determine navigation mode based on node state
        node_state = self.get_node_state(start_node)

        if node_state.is_volatile:
            # Repeller: use ASCENT to escape
            nav_mode = FieldNavigationMode.ASCENT
        else:
            # Default: use DESCENT to find attractor
            nav_mode = FieldNavigationMode.DESCENT

        field_result = self.field_traverser.traverse(
            start_node=start_node,
            mode=nav_mode,
            max_steps=max_depth,
        )

        telemetry["field_mode"] = nav_mode.value
        telemetry["field_steps"] = len(field_result.trajectory) - 1
        telemetry["energy_change"] = field_result.total_energy_change
        telemetry["endpoint_role"] = field_result.endpoint_role.value

        # Convert to unified format
        results = [
            (field_result.endpoint, abs(field_result.total_energy_change), [start_node, field_result.endpoint])
        ]

        return TraversalResult(
            start_node=start_node,
            mode=TraversalMode.FIELD_GUIDED,
            visited_nodes=field_result.visited_nodes,
            results=results,
            mode_switches=[],
            telemetry=telemetry,
        )

    def _execute_saddle_escape(
        self,
        start_node: str,
        max_depth: int,
        top_k: int,
        telemetry: Dict[str, any],
    ) -> TraversalResult:
        """Execute saddle escape.

        Args:
            start_node: Starting node ID
            max_depth: Maximum traversal depth (used as max_steps)
            top_k: Number of top results
            telemetry: Telemetry dict to update

        Returns:
            TraversalResult
        """
        escape_result = self.saddle_traverser.escape(
            saddle_node=start_node,
            max_steps=max_depth,
        )

        telemetry["escape_steps"] = len(escape_result.escape_trajectory) - 1
        telemetry["endpoint_role"] = escape_result.escape_endpoint_role.value
        telemetry["final_mode"] = escape_result.final_mode.value

        # Convert to unified format
        results = [
            (escape_result.escape_endpoint, 1.0, [start_node, escape_result.escape_endpoint])
        ]

        return TraversalResult(
            start_node=start_node,
            mode=TraversalMode.SADDLE_ESCAPE,
            visited_nodes=set([node for node, _, _ in escape_result.escape_trajectory]),
            results=results,
            mode_switches=escape_result.mode_switches,
            telemetry=telemetry,
        )

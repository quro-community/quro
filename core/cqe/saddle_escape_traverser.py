"""Saddle Escape Traverser — Automatic Escape from Saddle Points

@module quro.core.cqe.saddle_escape_traverser
@intent Detect and escape from saddle points using hybrid strategy:
       1. Analyze field gradient to determine escape direction
       2. Use field-guided traversal for initial escape
       3. Switch to forward/reverse based on topology after escape

       Saddle points are transitional nodes with moderate gradients.
       They are neither stable (attractor) nor volatile (repeller).
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple

from adapters.graph.protocol import GraphAdapter
from core.cqe.tda_bridge import TDABridge
from core.cqe.field_guided_traverser import (
    FieldGuidedTraverser,
    FieldNavigationMode,
)
from core.cqe.node_state import FieldRole
from core.cqe.traversal_modes import TraversalMode, ModeSwitchEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SaddleEscapeResult:
    """Result of saddle escape traversal.

    Attributes:
        start_node: Starting saddle point node ID
        escape_trajectory: List of (node_id, energy, field_magnitude) during escape
        escape_endpoint: Node reached after escape
        escape_endpoint_role: Field role of escape endpoint
        mode_switches: List of mode switch events during escape
        final_mode: Final traversal mode after escape
    """
    start_node: str
    escape_trajectory: List[Tuple[str, float, float]]
    escape_endpoint: str
    escape_endpoint_role: FieldRole
    mode_switches: List[ModeSwitchEvent]
    final_mode: TraversalMode


class SaddleEscapeTraverser:
    """Saddle escape traverser with automatic mode switching.

    Strategy:
    1. Detect saddle point (field_role == SADDLE_POINT)
    2. Use field-guided traversal to escape (follow gradient)
    3. After escape, analyze endpoint topology
    4. Switch to appropriate mode (FORWARD/REVERSE/FIELD_GUIDED)

    Invariant: Always escapes from saddle points within max_steps.
    """

    def __init__(
        self,
        graph: GraphAdapter,
        tda_bridge: TDABridge,
    ):
        """Initialize saddle escape traverser.

        Args:
            graph: Graph adapter
            tda_bridge: TDA bridge for field vectors and energy
        """
        self.graph = graph
        self.tda_bridge = tda_bridge
        self.field_traverser = FieldGuidedTraverser(graph, tda_bridge)

    def _determine_escape_direction(self, saddle_node: str) -> FieldNavigationMode:
        """Determine escape direction from saddle point.

        Strategy:
        - If energy > 0.5: use DESCENT (move to lower energy)
        - If energy <= 0.5: use ASCENT (move to higher energy)

        This ensures we move away from the saddle point in the
        direction of steepest gradient.

        Args:
            saddle_node: Saddle point node ID

        Returns:
            FieldNavigationMode (DESCENT or ASCENT)
        """
        energy = self.tda_bridge.get_energy_total(saddle_node)

        if energy > 0.5:
            return FieldNavigationMode.DESCENT
        else:
            return FieldNavigationMode.ASCENT

    def _select_post_escape_mode(
        self,
        escape_endpoint: str,
    ) -> TraversalMode:
        """Select traversal mode after escaping saddle point.

        Decision tree:
        1. If endpoint is attractor → FORWARD (stable, continue forward)
        2. If endpoint is repeller → FIELD_GUIDED (volatile, use field)
        3. If endpoint is sink → REVERSE (no forward path)
        4. Default → FORWARD

        Args:
            escape_endpoint: Node reached after escape

        Returns:
            TraversalMode for continued traversal
        """
        out_degree = self.graph.out_degree(escape_endpoint)
        in_degree = self.graph.in_degree(escape_endpoint)
        field_role = self.tda_bridge.get_field_role(escape_endpoint)

        # Rule 1: Attractor → FORWARD
        if field_role == FieldRole.ATTRACTOR:
            return TraversalMode.FORWARD

        # Rule 2: Repeller → FIELD_GUIDED
        if field_role == FieldRole.REPELLER:
            return TraversalMode.FIELD_GUIDED

        # Rule 3: Sink → REVERSE
        if out_degree == 0 and in_degree > 0:
            return TraversalMode.REVERSE

        # Rule 4: Default → FORWARD
        return TraversalMode.FORWARD

    def escape(
        self,
        saddle_node: str,
        max_steps: int = 5,
    ) -> SaddleEscapeResult:
        """Escape from saddle point using field-guided traversal.

        Args:
            saddle_node: Starting saddle point node ID
            max_steps: Maximum escape steps (default 5)

        Returns:
            SaddleEscapeResult with escape trajectory and final mode
        """
        logger.info(
            "Starting saddle escape from %s (max_steps=%d)",
            saddle_node, max_steps,
        )

        # Verify it's a saddle point
        field_role = self.tda_bridge.get_field_role(saddle_node)
        if field_role != FieldRole.SADDLE_POINT:
            logger.warning(
                "Node %s is not a saddle point (role=%s), escaping anyway",
                saddle_node, field_role.value,
            )

        # Determine escape direction
        escape_mode = self._determine_escape_direction(saddle_node)
        logger.info("Escape direction: %s", escape_mode.value)

        # Record mode switch: SADDLE_ESCAPE → FIELD_GUIDED
        out_degree = self.graph.out_degree(saddle_node)
        in_degree = self.graph.in_degree(saddle_node)
        from core.cqe.node_state import classify_node_role
        node_role = classify_node_role(out_degree, in_degree)

        from core.cqe.node_state import NodeState
        start_state = NodeState(
            node_id=saddle_node,
            out_degree=out_degree,
            in_degree=in_degree,
            node_role=node_role,
            field_role=field_role,
            gravity_score=self.tda_bridge.get_gravity_score(saddle_node),
            energy_total=self.tda_bridge.get_energy_total(saddle_node),
            field_magnitude=self.tda_bridge.get_field_magnitude(saddle_node),
        )

        mode_switches = [
            ModeSwitchEvent(
                from_mode=TraversalMode.SADDLE_ESCAPE,
                to_mode=TraversalMode.FIELD_GUIDED,
                trigger="saddle_escape_initiated",
                node_id=saddle_node,
                node_state=start_state,
                escape_probability=0.0,  # Not applicable for saddle escape
            )
        ]

        # Use field-guided traversal to escape
        field_result = self.field_traverser.traverse(
            saddle_node,
            mode=escape_mode,
            max_steps=max_steps,
        )

        # Select post-escape mode
        final_mode = self._select_post_escape_mode(field_result.endpoint)
        logger.info(
            "Escaped to %s (role=%s), switching to %s mode",
            field_result.endpoint,
            field_result.endpoint_role.value,
            final_mode.value,
        )

        # Record mode switch: FIELD_GUIDED → final_mode
        endpoint_out = self.graph.out_degree(field_result.endpoint)
        endpoint_in = self.graph.in_degree(field_result.endpoint)
        endpoint_role = classify_node_role(endpoint_out, endpoint_in)

        endpoint_state = NodeState(
            node_id=field_result.endpoint,
            out_degree=endpoint_out,
            in_degree=endpoint_in,
            node_role=endpoint_role,
            field_role=field_result.endpoint_role,
            gravity_score=self.tda_bridge.get_gravity_score(field_result.endpoint),
            energy_total=self.tda_bridge.get_energy_total(field_result.endpoint),
            field_magnitude=self.tda_bridge.get_field_magnitude(field_result.endpoint),
        )

        mode_switches.append(
            ModeSwitchEvent(
                from_mode=TraversalMode.FIELD_GUIDED,
                to_mode=final_mode,
                trigger=f"post_escape_{field_result.endpoint_role.value}",
                node_id=field_result.endpoint,
                node_state=endpoint_state,
                escape_probability=0.0,
            )
        )

        return SaddleEscapeResult(
            start_node=saddle_node,
            escape_trajectory=field_result.trajectory,
            escape_endpoint=field_result.endpoint,
            escape_endpoint_role=field_result.endpoint_role,
            mode_switches=mode_switches,
            final_mode=final_mode,
        )

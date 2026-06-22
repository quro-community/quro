"""Traversal Mode Selection and Switching

@module quro.core.cqe.traversal_modes
@intent Automatic mode selection based on node state. Provides telemetry for
       mode switches and escape probability calculation.

       Modes:
       - FORWARD: Default CQE forward traversal (outgoing edges)
       - REVERSE: Gravity-constrained reverse traversal (incoming edges)
       - FIELD_GUIDED: TDA field vector descent/ascent
       - SADDLE_ESCAPE: Automatic escape from saddle points
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.cqe.node_state import NodeState, NodeRole, FieldRole


class TraversalMode(Enum):
    """Traversal mode for CQE navigation."""
    FORWARD = "forward"              # Default: follow outgoing edges
    REVERSE = "reverse"              # Sink escape: follow incoming edges
    FIELD_GUIDED = "field_guided"    # TDA-driven: follow energy gradient
    SADDLE_ESCAPE = "saddle_escape"  # Auto-switch: escape saddle points


@dataclass(frozen=True)
class ModeSwitchEvent:
    """Telemetry event for mode switches.

    Attributes:
        from_mode: Previous traversal mode
        to_mode: New traversal mode
        trigger: Reason for switch (e.g., "sink_detected", "saddle_point")
        node_id: Symbol ID where switch occurred
        node_state: Complete node state at switch point
        escape_probability: Probability of successful escape [0, 1]
    """
    from_mode: TraversalMode
    to_mode: TraversalMode
    trigger: str
    node_id: str
    node_state: NodeState
    escape_probability: float


def compute_escape_probability(
    gravity_score: float,
    mi_weight: float,
    noise_ratio: float,
) -> float:
    """Compute escape probability for reverse traversal.

    Formula (from 大G):
    escape_prob = gravity_score * mi_weight * (1 - noise_ratio)

    Args:
        gravity_score: Gravity strength [0, 1] (from TDA)
        mi_weight: MI score [0, 1] (from CQE)
        noise_ratio: Noise level [0, 1] (from query history)

    Returns:
        Escape probability [0, 1]
    """
    return gravity_score * mi_weight * (1.0 - noise_ratio)


def select_traversal_mode(
    node_state: NodeState,
    current_mode: TraversalMode = TraversalMode.FORWARD,
) -> tuple[TraversalMode, Optional[str]]:
    """Select traversal mode based on node state.

    Decision tree:
    1. Isolated node (out=0, in=0) → FORWARD (no traversal possible, return empty)
    2. Sink node (out=0, in>0) → REVERSE
    3. Saddle point → SADDLE_ESCAPE
    4. High-gravity attractor → FIELD_GUIDED (descent)
    5. Repeller → FIELD_GUIDED (ascent)
    6. Default → FORWARD

    Args:
        node_state: Complete node state
        current_mode: Current traversal mode

    Returns:
        Tuple of (selected_mode, trigger_reason)
    """
    # Rule 0: Isolated node → FORWARD (will return empty, but don't try other modes)
    if node_state.is_isolated:
        return (TraversalMode.FORWARD, "isolated_node")

    # Rule 1: Sink node → REVERSE
    if node_state.is_sink:
        return (TraversalMode.REVERSE, "sink_detected")

    # Rule 2: Saddle point → SADDLE_ESCAPE
    if node_state.field_role == FieldRole.SADDLE_POINT:
        return (TraversalMode.SADDLE_ESCAPE, "saddle_point")

    # Rule 3: High-gravity attractor → FIELD_GUIDED
    if node_state.is_high_gravity and node_state.field_role == FieldRole.ATTRACTOR:
        return (TraversalMode.FIELD_GUIDED, "high_gravity_attractor")

    # Rule 4: Repeller → FIELD_GUIDED (escape)
    if node_state.is_volatile:
        return (TraversalMode.FIELD_GUIDED, "repeller_escape")

    # Rule 5: Default → FORWARD
    return (TraversalMode.FORWARD, None)


def should_switch_mode(
    node_state: NodeState,
    current_mode: TraversalMode,
) -> tuple[bool, Optional[TraversalMode], Optional[str]]:
    """Check if mode switch is needed.

    Args:
        node_state: Complete node state
        current_mode: Current traversal mode

    Returns:
        Tuple of (should_switch, new_mode, trigger_reason)
    """
    selected_mode, trigger = select_traversal_mode(node_state, current_mode)

    if selected_mode != current_mode:
        return (True, selected_mode, trigger)

    return (False, None, None)

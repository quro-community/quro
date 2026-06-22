"""Node State Detection and Self-Awareness

@module quro.core.cqe.node_state
@intent Provide "体检" (health check) for every node entering the orchestrator.
       Nodes must know: Who am I? How many exits? Who's watching? Energy level?

       This is the foundation for automatic mode switching.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class NodeRole(Enum):
    """Node role in the graph topology."""
    SOURCE = "source"          # High out-degree, low in-degree (entry points)
    SINK = "sink"              # Zero out-degree, high in-degree (terminal nodes)
    HUB = "hub"                # High out-degree, high in-degree (central nodes)
    BRIDGE = "bridge"          # Medium out-degree, medium in-degree (connectors)
    LEAF = "leaf"              # Low out-degree, low in-degree (peripheral nodes)
    ISOLATED = "isolated"      # Zero out-degree, zero in-degree (disconnected)


class FieldRole(Enum):
    """TDA field role (from Phase 2.5 offline physics)."""
    ATTRACTOR = "attractor"              # Stable, low-energy well
    REPELLER = "repeller"                # Volatile, high-energy zone
    SADDLE_POINT = "saddle_point"        # Transitional, moderate gradient
    NOT_CRITICAL_POINT = "not_critical_point"  # Regular node


@dataclass(frozen=True)
class NodeState:
    """Complete state of a node for traversal mode selection.

    This is the "self-awareness" layer - every node knows its identity,
    connectivity, and energy state before entering the orchestrator.

    Attributes:
        node_id: Symbol ID (e.g., 'sym::CQEIndexPipeline')
        out_degree: Number of outgoing edges (who I call)
        in_degree: Number of incoming edges (who calls me)
        node_role: Topological role (source, sink, hub, etc.)
        field_role: TDA field role (attractor, repeller, saddle, etc.)
        gravity_score: Gravity strength [0, 1] (from Phase 2.5)
        energy_total: Total energy (potential + kinetic)
        field_magnitude: Field gradient magnitude
        is_sink: True if out_degree == 0 and in_degree > 0
        is_critical_point: True if field_role is attractor/repeller/saddle
    """
    node_id: str
    out_degree: int
    in_degree: int
    node_role: NodeRole
    field_role: FieldRole
    gravity_score: float
    energy_total: float
    field_magnitude: float

    @property
    def is_sink(self) -> bool:
        """Check if this is a sink node (terminal point)."""
        return self.out_degree == 0 and self.in_degree > 0

    @property
    def is_isolated(self) -> bool:
        """Check if this is an isolated node (disconnected)."""
        return self.out_degree == 0 and self.in_degree == 0

    @property
    def is_critical_point(self) -> bool:
        """Check if this is a TDA critical point."""
        return self.field_role in {
            FieldRole.ATTRACTOR,
            FieldRole.REPELLER,
            FieldRole.SADDLE_POINT,
        }

    @property
    def is_high_gravity(self) -> bool:
        """Check if this node has high gravity (deep potential well)."""
        return self.gravity_score >= 0.7

    @property
    def is_volatile(self) -> bool:
        """Check if this node is volatile (repeller)."""
        return self.field_role == FieldRole.REPELLER

    def __repr__(self) -> str:
        return (
            f"NodeState({self.node_id}, "
            f"out={self.out_degree}, in={self.in_degree}, "
            f"role={self.node_role.value}, "
            f"field={self.field_role.value}, "
            f"gravity={self.gravity_score:.2f})"
        )


def classify_node_role(out_degree: int, in_degree: int) -> NodeRole:
    """Classify node role based on degree.

    Args:
        out_degree: Number of outgoing edges
        in_degree: Number of incoming edges

    Returns:
        NodeRole classification
    """
    if out_degree == 0 and in_degree == 0:
        return NodeRole.ISOLATED
    elif out_degree == 0 and in_degree > 0:
        return NodeRole.SINK
    elif out_degree > 0 and in_degree == 0:
        return NodeRole.SOURCE
    elif out_degree >= 10 and in_degree >= 10:
        return NodeRole.HUB
    elif out_degree >= 5 or in_degree >= 5:
        return NodeRole.BRIDGE
    else:
        return NodeRole.LEAF

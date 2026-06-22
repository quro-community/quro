"""
Pass 1: Role Interpreter

Compresses topology metrics into cognitive role labels.
"""

from typing import Tuple
from ..phase2.schema import SymbolManifoldState
from . import CognitiveRole


class RoleInterpreter:
    """Interprets Phase-2 roles into cognitive labels."""

    def __init__(self):
        pass

    def interpret(self, sms: SymbolManifoldState) -> CognitiveRole:
        """Interpret manifold state into cognitive role.

        Args:
            sms: Symbol Manifold State from Phase-2

        Returns:
            CognitiveRole with cognitive labels
        """
        role_type = sms.role.type
        centrality = sms.topology.centrality
        betweenness = sms.topology.betweenness
        confidence = sms.role.confidence

        # Map Phase-2 role to cognitive role
        cognitive_type, action_implication, query_bias = self._map_role(
            role_type, centrality, betweenness
        )

        return CognitiveRole(
            type=cognitive_type,
            confidence=confidence,
            action_implication=action_implication,
            query_bias=query_bias,
        )

    def _map_role(
        self, role_type: str, centrality: float, betweenness: float
    ) -> Tuple[str, str, str]:
        """Map Phase-2 role to cognitive labels.

        Returns:
            (cognitive_type, action_implication, query_bias)
        """
        # Hub: high centrality
        if role_type == "hub" and centrality > 0.7:
            return (
                "query_anchor",
                "high_visibility",
                "prefer_as_anchor",
            )

        # Bridge: high betweenness
        if role_type == "bridge" and betweenness > 0.5:
            return (
                "system_critical_connector",
                "modification_risk_high",
                "prefer_as_anchor",
            )

        # Sink: data aggregation
        if role_type == "sink":
            return (
                "data_aggregation_point",
                "safe_to_modify",
                "neutral",
            )

        # Leaf: low connectivity
        if role_type == "leaf" and centrality < 0.3:
            return (
                "safe_to_ignore",
                "low_priority",
                "avoid_as_entry",
            )

        # Default: moderate importance
        return (
            "moderate_importance",
            "safe_to_modify",
            "neutral",
        )

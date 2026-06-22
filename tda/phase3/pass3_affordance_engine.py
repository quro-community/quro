"""
Pass 3: Cognitive Affordance Engine

Maps manifold position to reasoning affordances for LLM.
"""

from typing import List, Tuple
from ..phase2.schema import SymbolManifoldState


class CognitiveAffordanceEngine:
    """Detects cognitive affordances from manifold state."""

    def __init__(self):
        pass

    def detect_affordances(self, sms: SymbolManifoldState) -> Tuple[List[str], float]:
        """Detect cognitive affordances and attention weight.

        Args:
            sms: Symbol Manifold State from Phase-2

        Returns:
            (affordances, attention_weight)
        """
        affordances = []

        # Entry point candidate: hub with high centrality and frequency
        if self._is_entry_point_candidate(sms):
            affordances.append("entry_point_candidate")

        # Debug anchor: high betweenness and stability
        if self._is_debug_anchor(sms):
            affordances.append("debug_anchor")

        # Workflow orchestrator: hub with cross-category coupling
        if self._is_workflow_orchestrator(sms):
            affordances.append("workflow_orchestrator")

        # Safe refactor target: leaf with low mutation risk
        if self._is_safe_refactor_target(sms):
            affordances.append("safe_refactor_target")

        # Data transformer: sink with moderate stability
        if self._is_data_transformer(sms):
            affordances.append("data_transformer")

        # Critical bridge: bridge with high impact
        if self._is_critical_bridge(sms):
            affordances.append("critical_bridge")

        # Compute attention weight
        attention_weight = self._compute_attention_weight(sms)

        return affordances, attention_weight

    def _is_entry_point_candidate(self, sms: SymbolManifoldState) -> bool:
        """Check if symbol is good entry point."""
        return (
            sms.role.type == "hub"
            and sms.topology.centrality > 0.7
            and sms.temporal_signature.frequency > 100
        )

    def _is_debug_anchor(self, sms: SymbolManifoldState) -> bool:
        """Check if symbol is good debug anchor."""
        return (
            sms.topology.betweenness > 0.6
            and sms.stability.tau_persistence > 0.7
        )

    def _is_workflow_orchestrator(self, sms: SymbolManifoldState) -> bool:
        """Check if symbol orchestrates workflows."""
        return (
            sms.role.type == "hub"
            and len(sms.category_coupling) >= 2
        )

    def _is_safe_refactor_target(self, sms: SymbolManifoldState) -> bool:
        """Check if symbol is safe to refactor."""
        return (
            sms.role.type == "leaf"
            and sms.stability.tau_persistence > 0.7
            and sms.topology.centrality < 0.3
        )

    def _is_data_transformer(self, sms: SymbolManifoldState) -> bool:
        """Check if symbol transforms data."""
        return (
            sms.role.type == "sink"
            and sms.topology.centrality > 0.4
        )

    def _is_critical_bridge(self, sms: SymbolManifoldState) -> bool:
        """Check if symbol is critical bridge."""
        return (
            sms.role.type == "bridge"
            and sms.topology.betweenness > 0.7
        )

    def _compute_attention_weight(self, sms: SymbolManifoldState) -> float:
        """Compute attention weight for LLM [0,1]."""
        # Weighted combination of centrality, frequency percentile, and stability
        centrality_weight = sms.topology.centrality * 0.4
        frequency_weight = sms.percentiles.get("frequency", 0.5) * 0.3
        stability_weight = sms.stability.tau_persistence * 0.3

        return min(1.0, centrality_weight + frequency_weight + stability_weight)

"""
Pass 2: Risk & Stability Mapper

Translates stability metrics into engineering risk assessment.
"""

from ..phase2.schema import SymbolManifoldState
from . import StabilityAssessment


class RiskStabilityMapper:
    """Maps stability metrics to risk assessment."""

    def __init__(self):
        pass

    def map_stability(self, sms: SymbolManifoldState) -> StabilityAssessment:
        """Map stability metrics to risk assessment.

        Args:
            sms: Symbol Manifold State from Phase-2

        Returns:
            StabilityAssessment with risk labels
        """
        tau_persistence = sms.stability.tau_persistence
        structural_noise = sms.stability.structural_noise
        entry_variance = sms.stability.entry_variance

        # Classify stability
        stability_class = self._classify_stability(tau_persistence, structural_noise)

        # Assess mutation risk
        mutation_risk = self._assess_mutation_risk(tau_persistence, structural_noise)

        # Compute refactor sensitivity
        refactor_sensitivity = self._compute_refactor_sensitivity(
            structural_noise, entry_variance
        )

        # Assess change impact radius
        change_impact_radius = self._assess_impact_radius(sms)

        return StabilityAssessment(
            stability_class=stability_class,
            mutation_risk=mutation_risk,
            refactor_sensitivity=refactor_sensitivity,
            change_impact_radius=change_impact_radius,
        )

    def _classify_stability(self, tau_persistence: float, structural_noise: float) -> str:
        """Classify stability into core_invariant/stable/volatile."""
        if tau_persistence > 0.8 and structural_noise < 0.2:
            return "core_invariant"
        elif tau_persistence > 0.5 and structural_noise < 0.5:
            return "stable"
        else:
            return "volatile"

    def _assess_mutation_risk(self, tau_persistence: float, structural_noise: float) -> str:
        """Assess mutation risk: low/medium/high."""
        if tau_persistence > 0.8 and structural_noise < 0.2:
            return "low"
        elif tau_persistence > 0.5 and structural_noise < 0.5:
            return "medium"
        else:
            return "high"

    def _compute_refactor_sensitivity(
        self, structural_noise: float, entry_variance: float
    ) -> float:
        """Compute refactor sensitivity [0,1]."""
        # High noise + high variance = high sensitivity
        return min(1.0, (structural_noise + entry_variance) / 2.0)

    def _assess_impact_radius(self, sms: SymbolManifoldState) -> str:
        """Assess change impact radius based on centrality and betweenness."""
        centrality = sms.topology.centrality
        betweenness = sms.topology.betweenness

        # High centrality or betweenness = high impact
        if centrality > 0.7 or betweenness > 0.7:
            return "high"
        elif centrality > 0.4 or betweenness > 0.4:
            return "medium"
        else:
            return "low"

"""
Pass 4: Context Injection Formatter

Generates LLM-consumable context blocks.
"""

from typing import List, Optional
from ..phase2.schema import SymbolManifoldState
from . import CognitiveSymbolContext, CognitiveRole, StabilityAssessment, LLMContextBlock
from .tensor_debugger import TensorDebugger, TensorDebugInfo


class ContextInjectionFormatter:
    """Formats cognitive context for LLM consumption."""

    def __init__(self, debug_tensor_view: bool = False):
        """Initialize formatter.

        Args:
            debug_tensor_view: If True, output tensor debug information
        """
        self.debug_tensor_view = debug_tensor_view
        self.tensor_debugger = TensorDebugger() if debug_tensor_view else None

    def format_context(
        self,
        sms: SymbolManifoldState,
        cognitive_role: CognitiveRole,
        stability: StabilityAssessment,
        affordances: List[str],
        attention_weight: float,
        # Debug parameters (optional)
        in_degree: Optional[int] = None,
        out_degree: Optional[int] = None,
        calling_modules: Optional[set] = None,
        total_modules: Optional[int] = None,
        outgoing_weights: Optional[List[float]] = None,
    ) -> CognitiveSymbolContext:
        """Format complete cognitive context.

        Args:
            sms: Symbol Manifold State from Phase-2
            cognitive_role: Cognitive role from Pass 1
            stability: Stability assessment from Pass 2
            affordances: Affordances from Pass 3
            attention_weight: Attention weight from Pass 3
            in_degree: (Debug) Total incoming edges
            out_degree: (Debug) Total outgoing edges
            calling_modules: (Debug) Set of modules calling this symbol
            total_modules: (Debug) Total modules in system
            outgoing_weights: (Debug) List of outgoing edge weights

        Returns:
            CognitiveSymbolContext ready for LLM injection
        """
        # Generate debug output if enabled
        if self.debug_tensor_view and all([
            in_degree is not None,
            out_degree is not None,
            calling_modules is not None,
            total_modules is not None,
            outgoing_weights is not None,
        ]):
            debug_info = self.tensor_debugger.compute_debug_info(
                sms=sms,
                in_degree=in_degree,
                out_degree=out_degree,
                calling_modules=calling_modules,
                total_modules=total_modules,
                outgoing_weights=outgoing_weights,
            )
            print(self.tensor_debugger.format_debug_output(debug_info))

        # Generate summary
        summary = self._generate_summary(sms, cognitive_role)

        # Generate hints
        hints = self._generate_hints(sms, cognitive_role, stability, affordances)

        # Generate decision guidance
        decision_guidance = self._generate_decision_guidance(
            cognitive_role, stability, affordances
        )

        # Create LLM context block
        llm_context_block = LLMContextBlock(
            summary=summary,
            hints=hints,
            decision_guidance=decision_guidance,
        )

        return CognitiveSymbolContext(
            symbol=sms.symbol,
            cognitive_role=cognitive_role,
            stability=stability,
            affordances=affordances,
            attention_weight=attention_weight,
            llm_context_block=llm_context_block,
            percentile_ranks=sms.percentiles,
        )

    def _generate_summary(
        self, sms: SymbolManifoldState, cognitive_role: CognitiveRole
    ) -> str:
        """Generate one-line summary."""
        role_type = cognitive_role.type
        symbol_name = sms.symbol.replace("sym::", "")

        # Role-based summary templates
        templates = {
            "query_anchor": f"High-traffic coordination point: {symbol_name}",
            "system_critical_connector": f"Critical bridge connecting system regions: {symbol_name}",
            "data_aggregation_point": f"Data aggregation and processing node: {symbol_name}",
            "safe_to_ignore": f"Low-priority utility function: {symbol_name}",
            "moderate_importance": f"Standard function: {symbol_name}",
        }

        return templates.get(role_type, f"Symbol: {symbol_name}")

    def _generate_hints(
        self,
        sms: SymbolManifoldState,
        cognitive_role: CognitiveRole,
        stability: StabilityAssessment,
        affordances: List[str],
    ) -> List[str]:
        """Generate reasoning hints for LLM."""
        hints = []

        # Role-based hints
        if cognitive_role.type == "query_anchor":
            hints.append("High-visibility coordination point")
            hints.append("Good starting point for understanding system flow")

        if cognitive_role.type == "system_critical_connector":
            hints.append("Connects multiple system regions")
            hints.append("Modification requires careful impact analysis")

        if cognitive_role.type == "data_aggregation_point":
            hints.append("Aggregates data from multiple sources")

        # Stability hints
        if stability.stability_class == "core_invariant":
            hints.append("Highly stable across different query patterns")

        if stability.mutation_risk == "high":
            hints.append("High mutation risk - changes may have wide impact")

        # Category coupling hints
        if len(sms.category_coupling) >= 2:
            categories = list(sms.category_coupling.keys())[:2]
            hints.append(f"Bridges {categories[0]} ↔ {categories[1]} subsystems")

        # Frequency hints
        if sms.temporal_signature.frequency > 500:
            hints.append(f"High-traffic node ({sms.temporal_signature.frequency} visits)")

        # Affordance hints
        if "entry_point_candidate" in affordances:
            hints.append("Recommended as exploration entry point")

        if "safe_refactor_target" in affordances:
            hints.append("Safe target for refactoring")

        return hints

    def _generate_decision_guidance(
        self,
        cognitive_role: CognitiveRole,
        stability: StabilityAssessment,
        affordances: List[str],
    ) -> dict:
        """Generate decision guidance flags."""
        guidance = {}

        # Safe to modify?
        safe_to_modify = (
            stability.mutation_risk == "low"
            and cognitive_role.action_implication != "modification_risk_high"
        )
        guidance["safe_to_modify"] = "yes" if safe_to_modify else "no"

        # Preferred usage
        if cognitive_role.query_bias == "prefer_as_anchor":
            guidance["preferred_usage"] = "entry_anchor"
        elif "safe_refactor_target" in affordances:
            guidance["preferred_usage"] = "refactor_target"
        else:
            guidance["preferred_usage"] = "standard"

        # Refactor caution
        if stability.refactor_sensitivity > 0.7:
            guidance["refactor_caution"] = "high"
        elif stability.refactor_sensitivity > 0.4:
            guidance["refactor_caution"] = "medium"
        else:
            guidance["refactor_caution"] = "low"

        # Change impact
        guidance["change_impact_radius"] = stability.change_impact_radius

        return guidance

"""
Pydantic models for Phase-3 output (Cognitive Symbol Context).
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class CognitiveRole(BaseModel):
    """Cognitive role interpretation."""
    type: str = Field(..., description="Cognitive role: query_anchor/system_critical_connector/data_aggregation_point/safe_to_ignore")
    confidence: float = Field(..., description="Role confidence [0,1]")
    action_implication: str = Field(..., description="Action implication: high_visibility/modification_risk_high/safe_to_modify/low_priority")
    query_bias: str = Field(..., description="Query bias: prefer_as_anchor/avoid_as_entry/neutral")


class StabilityAssessment(BaseModel):
    """Stability and risk assessment."""
    stability_class: str = Field(..., description="Stability class: core_invariant/stable/volatile")
    mutation_risk: str = Field(..., description="Mutation risk: low/medium/high")
    refactor_sensitivity: float = Field(..., description="Refactor sensitivity [0,1]")
    change_impact_radius: str = Field(..., description="Change impact radius: low/medium/high")


class LLMContextBlock(BaseModel):
    """LLM-consumable context block."""
    summary: str = Field(..., description="One-line summary of symbol purpose")
    hints: List[str] = Field(default_factory=list, description="Reasoning hints for LLM")
    decision_guidance: Dict[str, str] = Field(default_factory=dict, description="Decision guidance flags")


class CognitiveSymbolContext(BaseModel):
    """Complete cognitive context for a symbol (Phase-3 output)."""
    symbol: str = Field(..., description="Symbol ID (sym::...)")

    cognitive_role: CognitiveRole = Field(..., description="Cognitive role interpretation")
    stability: StabilityAssessment = Field(..., description="Stability and risk assessment")

    affordances: List[str] = Field(default_factory=list, description="Cognitive affordances")
    attention_weight: float = Field(..., description="Attention weight for LLM [0,1]")

    llm_context_block: LLMContextBlock = Field(..., description="LLM-consumable context")

    percentile_ranks: Dict[str, float] = Field(default_factory=dict, description="Percentile rankings")

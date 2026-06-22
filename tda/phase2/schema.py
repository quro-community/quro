"""
Pydantic models for Phase-2 output (Symbol Manifold State).
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ManifoldPosition(BaseModel):
    """Symbol position in manifold space."""
    embedding: List[float] = Field(..., description="Semantic embedding vector")
    norm: float = Field(..., description="Vector norm")


class TopologyMetrics(BaseModel):
    """Topological properties of symbol."""
    centrality: float = Field(..., description="Weighted degree centrality [0,1]")
    betweenness: float = Field(..., description="Betweenness centrality [0,1]")
    clustering_coeff: float = Field(..., description="Clustering coefficient [0,1]")


class StabilityMetrics(BaseModel):
    """Stability under perturbation."""
    tau_persistence: float = Field(..., description="Survival rate across tau thresholds [0,1]")
    entry_variance: float = Field(..., description="Variance across entry points [0,1]")
    structural_noise: float = Field(..., description="Noise in edge weights [0,1]")


class RoleInfo(BaseModel):
    """Inferred role in graph."""
    type: str = Field(..., description="Role type: hub/bridge/sink/leaf")
    confidence: float = Field(..., description="Role confidence [0,1]")


class TemporalSignature(BaseModel):
    """Temporal access patterns."""
    first_seen: int = Field(..., description="Unix epoch (microseconds)")
    frequency: int = Field(..., description="Total visit count")
    burstiness: float = Field(..., description="Burstiness coefficient [0,1]")


class SymbolManifoldState(BaseModel):
    """Complete manifold state for a symbol."""
    symbol: str = Field(..., description="Symbol ID (sym::...)")

    manifold_position: Optional[ManifoldPosition] = Field(None, description="Position in manifold space")
    topology: TopologyMetrics = Field(..., description="Topological metrics")
    stability: StabilityMetrics = Field(..., description="Stability metrics")
    role: RoleInfo = Field(..., description="Inferred role")
    category_coupling: Dict[str, float] = Field(default_factory=dict, description="Category pair → coupling strength")
    temporal_signature: TemporalSignature = Field(..., description="Temporal patterns")

    # Percentile rankings (for UI/filtering)
    percentiles: Dict[str, float] = Field(default_factory=dict, description="Metric → percentile rank")

    # Field metrics (added by pass4_field_enrichment)
    energy: Optional[Dict[str, float]] = Field(None, description="Energy state: potential, kinetic, total")
    field_role: Optional[str] = Field(None, description="Role in field: stable_attractor/unstable_repeller/saddle_point/not_critical")
    field_magnitude: Optional[float] = Field(None, description="Field strength ||∇E(x)||")
    mass: Optional[float] = Field(None, description="Mass (importance): (centrality + frequency) / 2")
    friction: Optional[float] = Field(None, description="Friction (resistance to change): (1 - stability) × (1 + noise)")

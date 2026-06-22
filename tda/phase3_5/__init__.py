"""
Pydantic models for Phase-3.5 output (Codebase Hologram).
"""

import hashlib
from enum import Enum
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field


def _size_tier(size: int) -> str:
    """Compute size tier for stable identity (tolerates small fluctuations)."""
    if size >= 1000:
        return "XL"
    elif size >= 500:
        return "L"
    elif size >= 100:
        return "M"
    return "S"


def compute_stable_id(
    entry_points: List["EntryPointInfo"],
    archetype: str,
    size: int,
) -> str:
    """Compute content-addressed stable identity for a semantic center.

    Built from: sorted top-3 entry points + archetype + size tier.
    Uses SHA256 truncated to 12 hex chars.
    """
    top_anchors = sorted(
        ep.symbol for ep in (entry_points or [])[:3]
    )
    tier = _size_tier(size)
    raw = "|".join(top_anchors) + "|" + archetype + "|" + tier
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def compute_members_hash(symbol_ids: Set[str]) -> str:
    """Compute SHA256 hash of sorted member symbol IDs.

    Full 64-char hex digest for precise change detection.
    """
    concatenated = "|".join(sorted(symbol_ids))
    return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()


def get_git_hash(workspace_root: "Path") -> Optional[str]:
    """Return current git HEAD commit hash, or None if unavailable."""
    import subprocess
    from pathlib import Path

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


class GlobalMetrics(BaseModel):
    """Global codebase metrics."""
    center_of_mass: str = Field(..., description="Semantic center of gravity (directory path)")
    dominant_axis: str = Field(..., description="Dominant coupling axis (e.g., 'async ↔ database')")
    coherence: float = Field(..., description="Overall coherence [0,1]")
    fragmentation: float = Field(..., description="Fragmentation score [0,1]")
    coupling_pressure: float = Field(..., description="Coupling pressure [0,1]")


class FieldStatistics(BaseModel):
    """Energy field statistics."""
    energy_distribution: Dict[str, float] = Field(..., description="Energy distribution: mean, std, min, max")
    attractor_count: int = Field(..., description="Number of stable attractors")
    repeller_count: int = Field(..., description="Number of unstable repellers")
    saddle_count: int = Field(..., description="Number of saddle points")


class MajorAttractor(BaseModel):
    """Major attractor in energy landscape."""
    symbol: str = Field(..., description="Symbol ID")
    energy: float = Field(..., description="Energy value")
    basin_depth: float = Field(..., description="Basin depth (1 - energy)")
    basin_size: int = Field(..., description="Number of neighbors in basin")


class SemanticFoldingRegion(BaseModel):
    """Semantic folding region (high complexity zone)."""
    region: str = Field(..., description="Directory path")
    fold_type: str = Field(..., description="Fold type: high-compression/moderate/low")
    meaning: str = Field(..., description="Interpretation of folding")
    complexity_score: float = Field(..., description="Complexity score [0,1]")


class VoidRegion(BaseModel):
    """Semantic void region (low activity zone)."""
    path: str = Field(..., description="Directory path")
    void_score: float = Field(..., description="Void score [0,1]")
    code_lines: int = Field(..., description="Estimated code lines")
    visit_count: int = Field(..., description="Total visit count")
    recommendation: str = Field(..., description="Recommendation: candidate_for_removal/review_needed/keep")


class ArchitectureState(BaseModel):
    """Overall architecture health state."""
    coherence: float = Field(..., description="Coherence [0,1]")
    fragmentation: float = Field(..., description="Fragmentation [0,1]")
    coupling_pressure: float = Field(..., description="Coupling pressure [0,1]")
    overall_health: str = Field(..., description="Overall health: excellent/good/fair/poor")


class NavigationGuidance(BaseModel):
    """Navigation guidance for LLM agents."""
    recommended_entry_points: List[str] = Field(default_factory=list, description="Recommended entry symbols")
    high_risk_zones: List[str] = Field(default_factory=list, description="High-risk directories")
    safe_refactor_zones: List[str] = Field(default_factory=list, description="Safe refactor directories")


class CodebaseHologram(BaseModel):
    """Complete codebase holographic view (Phase-3.5 output)."""
    global_metrics: GlobalMetrics = Field(..., description="Global codebase metrics")

    field_maps: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Field maps: density/curvature/stress"
    )

    semantic_folding_regions: List[SemanticFoldingRegion] = Field(
        default_factory=list,
        description="High-complexity folding regions"
    )

    void_regions: List[VoidRegion] = Field(
        default_factory=list,
        description="Semantic void regions"
    )

    architecture_state: ArchitectureState = Field(..., description="Architecture health state")

    navigation_guidance: NavigationGuidance = Field(..., description="Navigation guidance")

    # Field statistics (added from Phase-3.5 Kernel)
    field_statistics: Optional[FieldStatistics] = Field(None, description="Energy field statistics")
    major_attractors: List[MajorAttractor] = Field(default_factory=list, description="Top 5 major attractors")


# =============================================================================
# Phase 3.6: Semantic Centers (Design 99)
# =============================================================================


class TopologicalArchetype(str, Enum):
    """Topological archetype of a semantic center."""

    HUB = "hub"
    SINK = "sink"
    CHAIN = "chain"
    FANOUT = "fanout"
    TRANSITIONAL = "transitional"


class StructureProfile(BaseModel):
    """Structural profile of a semantic center."""

    fan_in: str = Field(..., description="Fan-in level: high/medium/low")
    fan_out: str = Field(..., description="Fan-out level: high/medium/low")
    depth: int = Field(..., description="Maximum depth from entry points within center")
    cohesion: str = Field(..., description="Internal cohesion: high/medium/low")


class NavigationHint(BaseModel):
    """Navigation guidance for entering/exploring a center."""

    suggested_mode: str = Field(
        ...,
        description="Suggested exploration mode: expand_outward/converge_inward/traverse",
    )
    landing_hint: str = Field(
        ...,
        description="Structural affordance description for LLM (how to enter, not what it is)",
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Potential risks or considerations for this center",
    )


class EntryPointInfo(BaseModel):
    """Entry point within a semantic center."""

    symbol: str = Field(..., description="Symbol ID")
    reachability_score: float = Field(
        ..., description="Reachability score [0, 1] (higher = more central)"
    )
    reason: str = Field(
        ..., description="Why this is a good entry point"
    )


class InterCenterEdge(BaseModel):
    """Directed edge between two semantic centers."""

    from_center: str = Field(..., description="Source center ID")
    to_center: str = Field(..., description="Target center ID")
    strength: float = Field(..., description="Connection strength [0, 1] (fraction of crossing edges)")
    direction: str = Field(..., description="Direction: outbound/bidirectional")


class CenterTopology(BaseModel):
    """Topological properties of a semantic center."""

    pattern: str = Field(..., description="Topological archetype: hub/sink/chain/fanout/transitional")
    pattern_confidence: float = Field(..., description="Confidence in archetype classification [0, 1]")
    entry_points: List[EntryPointInfo] = Field(
        default_factory=list,
        description="Recommended entry symbols for this center",
    )
    connected_centers: List[str] = Field(
        default_factory=list,
        description="IDs of connected centers (excluding isolated)",
    )
    connections: List[InterCenterEdge] = Field(
        default_factory=list,
        description="Detailed connection information",
    )


class SemanticCenter(BaseModel):
    """A semantic center representing a partition of the codebase graph."""

    id: str = Field(..., description="Center ID (e.g. C0, C1, ...)")
    size: int = Field(..., description="Number of symbols in this center")
    density: float = Field(..., description="Average semantic density [0, 1]")
    structure: StructureProfile = Field(..., description="Structural profile")
    topology: CenterTopology = Field(..., description="Topological properties")
    navigation: NavigationHint = Field(..., description="Navigation guidance")

    stable_id: str = Field(
        ...,
        description="Content-addressed stable identity: sha256(top3_entry+archetype+size_tier)[:12]. "
                    "Stable across runs when center semantics are unchanged."
    )
    members_hash: str = Field(
        ...,
        description="SHA256 of sorted member symbol IDs. Changes when any member is added/removed."
    )


class CenterGraph(BaseModel):
    """Complete semantic center graph (Phase 3.6 output)."""

    centers: List["SemanticCenterSCG"] = Field(
        default_factory=list,
        description="All detected semantic centers with SCG enrichment",
    )
    total_symbols: int = Field(
        ...,
        description="Total number of symbols in the codebase",
    )
    unassigned_symbols: int = Field(
        ...,
        description="Symbols not assigned to any center (noise/peripheral)",
    )
    partition_coverage: float = Field(
        ...,
        description="Fraction of symbols assigned to centers [0, 1]",
    )

    git_hash: Optional[str] = Field(
        None,
        description="Git commit hash at time of center generation. Metadata only — "
                    "not part of center identity."
    )

    # Structural Coupling Graph (Phase 3.7)
    structural_coupling: Optional["StructuralCouplingReport"] = Field(
        None,
        description="Structural coupling analysis: how dependency flow forces symbols to coexist"
    )


# =============================================================================
# Structural Coupling Graph (SCG) — Phase 3.7
# =============================================================================


class StructuralArchetype(str, Enum):
    """Structural archetype of a coupling cluster.

    These describe HOW symbols are forced to coexist, not WHAT they mean.
    """

    TIGHT_COUPLING = "tight_coupling"    # High density — must change together
    FLOW_CONVERGENT = "flow_convergent"  # Share downstream sinks
    RADIATION = "radiation"              # High fan-out — spreads influence
    LOOSE_COUPLING = "loose_coupling"    # Weakly coupled


class StructuralCluster(BaseModel):
    """A structural cluster — symbols forced to coexist by dependency flow geometry.

    A Structural Cluster is NOT a semantic grouping. It captures the physical
    reality that some symbols MUST change together because they share the same
    dependency flow pressure.

    Source of coupling:
      1. Shared upstream pressure: A ← X → B  (both receive from same source)
      2. Shared downstream sink:  A → Z ← B  (both converge to same drain)
      3. Traversal convergence:  repeated appearance of X in different paths
    """

    id: str = Field(..., description="Cluster ID (SC0, SC1, ...)")
    size: int = Field(..., description="Number of symbols in cluster")
    archetype: StructuralArchetype = Field(..., description="Structural archetype")

    # Coupling metrics
    density: float = Field(
        ...,
        description="Coupling density [0, 1]: fraction of possible edges that exist"
    )
    internal_edges: int = Field(
        ...,
        description="Number of internal undirected coupling edges"
    )

    # Convergence nodes (shared sinks = flow drains)
    shared_sinks: List[str] = Field(
        default_factory=list,
        description="Top sink nodes shared by cluster members (flow drains)"
    )

    # Representative symbols (highest coupling degree)
    hub_symbols: List[str] = Field(
        default_factory=list,
        description="Symbols with highest coupling degree within the cluster"
    )

    # Physical distribution
    physical_modules: List[str] = Field(
        default_factory=list,
        description="Physical modules (directories) that cluster spans"
    )
    is_cross_module: bool = Field(
        ...,
        description="True if cluster spans multiple physical modules"
    )


class CoupledCenters(BaseModel):
    """Coupling relationship between two semantic centers.

    Two semantic centers may be structurally coupled (forced to coexist)
    even if they have different semantic labels. This is a misalignment signal.
    """

    center_a: str = Field(..., description="First center ID (e.g. C0)")
    center_b: str = Field(..., description="Second center ID (e.g. C1)")
    coupling_score: float = Field(
        ...,
        description="Coupling strength [0, 1]: fraction of cross-center pairs that share flow"
    )

    # Coupling mechanism
    shared_sinks: List[str] = Field(
        default_factory=list,
        description="Sink symbols shared by both centers"
    )
    bridge_symbols: List[str] = Field(
        default_factory=list,
        description="Symbols that bridge the two centers (appear in both paths)"
    )

    # LLM-readable
    explanation: str = Field(
        ...,
        description="Plain-language explanation of why these centers are coupled"
    )


class SemanticCenterSCG(BaseModel):
    """SemanticCenter enriched with structural coupling data.

    This extends the base SemanticCenter with three structural dimensions:
      - Which Structural Cluster it belongs to (structural_purity)
      - How it couples with other centers (coupled_centers)
      - Whether it spans physical modules (is_cross_module)
    """

    # --- Base SemanticCenter fields (verbatim) ---
    id: str = Field(..., description="Center ID (C0, C1, ...)")
    size: int = Field(..., description="Number of symbols in this center")
    density: float = Field(..., description="Average semantic density [0, 1]")
    structure: StructureProfile = Field(..., description="Structural profile")
    topology: CenterTopology = Field(..., description="Topological properties")
    navigation: NavigationHint = Field(..., description="Navigation guidance")

    stable_id: str = Field(
        ...,
        description="Content-addressed stable identity: sha256(top3_entry+archetype+size_tier)[:12]. "
                    "Stable across runs when center semantics are unchanged."
    )
    members_hash: str = Field(
        ...,
        description="SHA256 of sorted member symbol IDs. Changes when any member is added/removed."
    )

    # --- Structural Coupling (NEW) ---
    structural_cluster_id: Optional[str] = Field(
        None,
        description="Primary Structural Cluster this center belongs to (SC0, SC1, ...)"
    )
    structural_purity: float = Field(
        ...,
        description="Fraction [0, 1] of center symbols that are in the dominant SC. "
                    "High purity = center maps cleanly to one structural cluster. "
                    "Low purity = center spans multiple structural clusters."
    )
    coupling_archetype: Optional[StructuralArchetype] = Field(
        None,
        description="Structural archetype if center is a SC member"
    )
    coupled_centers: List[CoupledCenters] = Field(
        default_factory=list,
        description="Structural coupling relationships with other centers"
    )
    shared_sinks: List[str] = Field(
        default_factory=list,
        description="Sink symbols shared by this center's members"
    )
    is_cross_module: bool = Field(
        ...,
        description="True if this center spans multiple physical modules. "
                    "Cross-module centers are architectural risk signals."
    )


class StructuralCouplingReport(BaseModel):
    """Complete structural coupling report for Symbol Centers.

    Produced alongside the semantic center graph to give LLM agents
    the third dimension: how dependency flow forces symbols to coexist.
    """

    clusters: List[StructuralCluster] = Field(
        default_factory=list,
        description="All detected structural clusters"
    )
    coupled_centers: List[CoupledCenters] = Field(
        default_factory=list,
        description="All inter-center coupling relationships"
    )
    total_symbols: int = Field(
        ...,
        description="Total symbols in the coupling graph"
    )
    cross_module_clusters: int = Field(
        ...,
        description="Number of clusters that span multiple physical modules"
    )


# =============================================================================
# Progressive Disclosure Models (Design 104)
# =============================================================================


class RoutingRecommendation(BaseModel):
    """Routing recommendation for LLM first-touch."""

    region: str = Field(..., description="Center ID (e.g., C1)")
    reason: str = Field(..., description="Why start here")
    confidence: float = Field(..., description="Confidence [0, 1]")
    entry_points: List[str] = Field(..., description="Top 3 entry symbols")


class RoutingLayer(BaseModel):
    """Routing layer: guides LLM where to start."""

    instruction: str = Field(..., description="How to use this data")
    recommended: List[RoutingRecommendation] = Field(
        ..., description="Recommended starting regions"
    )


class RegionSummary(BaseModel):
    """Compressed region summary for quick scanning."""

    id: str = Field(..., description="Center ID")
    role: str = Field(..., description="Topological role: hub/sink/chain/fanout")
    size: int = Field(..., description="Number of symbols")
    entry_points: List[str] = Field(..., description="Top 3 entry symbols")
    hint: str = Field(..., description="Navigation hint")


class StructuralClusterSummary(BaseModel):
    """Compressed structural cluster summary."""

    id: str = Field(..., description="Cluster ID")
    size: int = Field(..., description="Number of symbols")
    archetype: str = Field(..., description="Coupling archetype")
    centers: List[str] = Field(..., description="Centers in this cluster")
    hint: str = Field(..., description="What this means")


class CouplingCompressed(BaseModel):
    """Compressed coupling relationship."""

    center_a: str
    center_b: str
    score: float
    mechanism: str = Field(..., description="How they're coupled")
    shared_sinks_sample: List[str] = Field(..., description="Top 3 shared sinks")


class StructureLayer(BaseModel):
    """Structure layer: cross-region coupling (last, detailed)."""

    summary: str = Field(..., description="High-level summary")
    clusters: List[StructuralClusterSummary]
    couplings: List[CouplingCompressed]
    details_hint: str = Field(..., description="How to get more detail")


class CodeLandscape(BaseModel):
    """Progressive disclosure code landscape (Design 104).

    Three-stage consumption model:
    1. Routing layer - "Where to go"
    2. Region summary - "What's in this region"
    3. Structure layer - "Cross-region coupling"
    """

    routing: RoutingLayer
    regions: List[RegionSummary]
    structure: StructureLayer
    total_symbols: int
    partition_coverage: float

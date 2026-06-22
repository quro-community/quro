"""
CQE Policy - Configurable behavior layer

@module quro.core.cqe.policy
@intent Define configurable CQE behavior (not hardcoded)
@constraint Data-only, no executable logic

INVARIANT: Policy is Declarative
- NO methods (except dataclass defaults)
- NO control flow (if/else, loops)
- NO side effects
- ONLY data fields (weights, thresholds, flags)

Policy controls:
- Prune: Which paths to prune (tau threshold)
- Boost: Which atoms to boost (future)
- Normalize: How to normalize weights (future)
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PrunePolicy:
    """
    Pruning policy configuration.

    Controls which paths are pruned during traversal.

    INVARIANT: Data-only
    - No methods
    - No control flow
    - Immutable (frozen)
    """

    min_weight: float = 0.05
    """Minimum edge weight threshold (tau)"""

    max_hops: int = 5
    """Maximum traversal depth"""

    max_nodes_visited: int = 2000
    """Maximum nodes to visit (safety limit)"""

    max_category_fanout: int = 200
    """Maximum fan-out for category nodes (prevents hub explosion)"""

    @classmethod
    def default(cls) -> "PrunePolicy":
        """Default pruning policy"""
        return cls(min_weight=0.05, max_hops=5, max_nodes_visited=2000, max_category_fanout=200)

    @classmethod
    def conservative(cls) -> "PrunePolicy":
        """Conservative pruning (higher threshold)"""
        return cls(min_weight=0.1, max_hops=3, max_nodes_visited=1000, max_category_fanout=100)

    @classmethod
    def aggressive(cls) -> "PrunePolicy":
        """Aggressive pruning (lower threshold)"""
        return cls(min_weight=0.01, max_hops=7, max_nodes_visited=5000, max_category_fanout=500)


@dataclass(frozen=True)
class BoostPolicy:
    """
    Boost policy configuration.

    Controls which atoms get weight boosts.

    INVARIANT: Data-only
    - No methods
    - No control flow
    - Immutable (frozen)
    """

    enabled: bool = False
    """Whether boosting is enabled"""

    jaccard_floor: float = 0.05
    """Minimum Jaccard similarity for boost"""

    jaccard_ceiling: float = 0.95
    """Maximum Jaccard similarity for boost"""

    boost_factor: float = 1.2
    """Multiplicative boost factor"""

    @classmethod
    def default(cls) -> "BoostPolicy":
        """Default boost policy (disabled)"""
        return cls(enabled=False)

    @classmethod
    def enabled_default(cls) -> "BoostPolicy":
        """Enabled boost policy with defaults"""
        return cls(
            enabled=True,
            jaccard_floor=0.05,
            jaccard_ceiling=0.95,
            boost_factor=1.2
        )


@dataclass(frozen=True)
class NormalizePolicy:
    """
    Normalization policy configuration.

    Controls how weights are normalized.

    INVARIANT: Data-only
    - No methods
    - No control flow
    - Immutable (frozen)
    """

    method: str = "none"
    """Normalization method: 'none', 'minmax', 'softmax'"""

    preserve_ordering: bool = True
    """Whether to preserve weight ordering"""

    @classmethod
    def default(cls) -> "NormalizePolicy":
        """Default normalization (none)"""
        return cls(method="none", preserve_ordering=True)

    @classmethod
    def minmax(cls) -> "NormalizePolicy":
        """MinMax normalization"""
        return cls(method="minmax", preserve_ordering=True)

    @classmethod
    def softmax(cls) -> "NormalizePolicy":
        """Softmax normalization"""
        return cls(method="softmax", preserve_ordering=True)


@dataclass(frozen=True)
class PathGrammarPolicy:
    """
    Path Grammar & Semantic Layer Constraints.
    Implements transition rules to prevent invalid semantic paths.
    """

    layer_map: dict[str, str] = field(
        default_factory=lambda: {
            "inherits": "structural",
            "calls": "structural",
            "imports": "structural",
            "category": "semantic",
            "semantic_similarity": "semantic",
            "attr_access": "noisy",
        }
    )

    # Define valid transitions: source_layer -> tuple of allowed next_layers
    allowed_transitions: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "START": ("structural", "semantic", "noisy"),
            "structural": ("structural", "semantic", "noisy"),
            "semantic": ("semantic", "noisy"),  # Cannot go back up to structural
            "noisy": ("noisy",)                # Once in noisy layer, stay noisy or terminate
        }
    )

    hub_normalization_enabled: bool = True
    """Whether to softly normalize hub outgoing edges based on out-degree."""

    @classmethod
    def default(cls) -> "PathGrammarPolicy":
        return cls()


@dataclass(frozen=True)
class CQEPolicy:
    """
    Complete CQE policy configuration.

    Combines all policy aspects.

    INVARIANT: Data-only
    - No methods (except classmethod constructors)
    - No control flow
    - Immutable (frozen)
    """

    version: str
    """Policy version identifier"""

    prune: PrunePolicy
    """Pruning policy"""

    boost: BoostPolicy
    """Boost policy"""

    normalize: NormalizePolicy
    """Normalization policy"""

    grammar: PathGrammarPolicy = field(default_factory=PathGrammarPolicy.default)
    """Path grammar constraints"""

    @classmethod
    def default(cls) -> "CQEPolicy":
        """Default CQE policy"""
        return cls(
            version="cqe_policy_v4_grammar",
            prune=PrunePolicy.default(),
            boost=BoostPolicy.default(),
            normalize=NormalizePolicy.default(),
            grammar=PathGrammarPolicy.default()
        )

    @classmethod
    def conservative(cls) -> "CQEPolicy":
        """Conservative policy (higher thresholds)"""
        return cls(
            version="cqe_policy_v4_conservative",
            prune=PrunePolicy.conservative(),
            boost=BoostPolicy.default(),
            normalize=NormalizePolicy.default(),
            grammar=PathGrammarPolicy.default()
        )

    @classmethod
    def aggressive(cls) -> "CQEPolicy":
        """Aggressive policy (lower thresholds)"""
        return cls(
            version="cqe_policy_v4_aggressive",
            prune=PrunePolicy.aggressive(),
            boost=BoostPolicy.default(),
            normalize=NormalizePolicy.default(),
            grammar=PathGrammarPolicy.default()
        )

"""CQE Semantic Scoring Engine

@module quro.core.cqe.scoring
@intent Compute semantic relevance scores from enricher tags
@constraint Pure functions, deterministic scoring
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class SemanticScore:
    """Semantic relevance score for a CQE result node.

    Combines base weight from CQE traversal with semantic adjustments
    from Phase 1 and Phase 2 enrichers.
    """
    base_weight: float
    role_boost: float
    intent_boost: float
    noise_penalty: float
    hub_penalty: float

    @property
    def total(self) -> float:
        """Compute total semantic score.

        Returns:
            Total score (clamped to [0, inf))
        """
        return max(0.0, self.base_weight + self.role_boost + self.intent_boost
                   - self.noise_penalty - self.hub_penalty)


class SemanticScorer:
    """Compute semantic relevance scores from enricher tags.

    Uses Phase 1 (topology) and Phase 2 (semantic) enricher tags to
    adjust raw CQE weights into semantically-aware relevance scores.

    Scoring formula:
        score = base_weight + role_boost + intent_boost - noise_penalty - hub_penalty

    Where:
        - base_weight: Raw CQE traversal weight (from max-product Dijkstra)
        - role_boost: Architectural significance (controller > service > util)
        - intent_boost: Semantic clarity (network/database > logging > test)
        - noise_penalty: Ambiguity penalty (wildcard imports, name collisions)
        - hub_penalty: Generic node penalty (high fanout, e.g., typing.Any)
    """

    # Role importance (architectural significance)
    # Higher values = more architecturally significant
    ROLE_WEIGHTS = {
        "controller": 0.3,   # Request handlers, API endpoints
        "service": 0.25,     # Business logic orchestrators
        "repository": 0.2,   # Data access layer
        "adapter": 0.15,     # Protocol implementations
        "factory": 0.1,      # Object creation patterns
        "worker": 0.1,       # Background tasks
    }

    # Intent importance (semantic clarity)
    # Higher values = more concrete and actionable
    INTENT_WEIGHTS = {
        "network": 0.2,      # HTTP, sockets, requests
        "database": 0.2,     # SQL, queries, ORM
        "io": 0.15,          # File operations
        "async": 0.15,       # Async operations
        "config": 0.1,       # Configuration loading
        "logging": 0.05,     # Logging operations
        "cli": 0.05,         # Command-line interfaces
        "test": 0.0,         # Tests rarely relevant for production queries
        "util": -0.1,        # Utilities are noise unless high weight
    }

    def __init__(
        self,
        role_weights: Dict[str, float] | None = None,
        intent_weights: Dict[str, float] | None = None,
        noise_penalty: float = 0.4,
        hub_penalty: float = 0.2,
    ):
        """Initialize semantic scorer.

        Args:
            role_weights: Custom role weights (default: ROLE_WEIGHTS)
            intent_weights: Custom intent weights (default: INTENT_WEIGHTS)
            noise_penalty: Penalty for noisy symbols (default: 0.4)
            hub_penalty: Penalty for high-fanout hubs (default: 0.2)
        """
        self.role_weights = role_weights or self.ROLE_WEIGHTS
        self.intent_weights = intent_weights or self.INTENT_WEIGHTS
        self.noise_penalty_value = noise_penalty
        self.hub_penalty_value = hub_penalty

    def score(self, node_id: str, weight: float, metadata: Dict[str, Any]) -> SemanticScore:
        """Compute semantic score for a node.

        Args:
            node_id: Node identifier (e.g., "sym::LockManager")
            weight: Base weight from CQE traversal
            metadata: Node metadata from registry (tags, intent, is_noisy)

        Returns:
            SemanticScore with breakdown of score components
        """
        tags = metadata.get("tags", [])
        intent = metadata.get("metadata", {}).get("intent", "Unknown")
        is_noisy = metadata.get("metadata", {}).get("is_noisy", False)

        # Role boost: architectural significance
        role_boost = self._compute_role_boost(tags)

        # Intent boost: semantic clarity
        intent_boost = self._compute_intent_boost(intent)

        # Noise penalty: ambiguity
        noise_penalty = self.noise_penalty_value if is_noisy else 0.0

        # Hub penalty: generic nodes
        hub_penalty = self.hub_penalty_value if "high_fanout" in tags else 0.0

        return SemanticScore(
            base_weight=weight,
            role_boost=role_boost,
            intent_boost=intent_boost,
            noise_penalty=noise_penalty,
            hub_penalty=hub_penalty,
        )

    def _compute_role_boost(self, tags: list) -> float:
        """Compute role boost from architectural tags.

        Args:
            tags: List of semantic tags from enrichers

        Returns:
            Maximum role boost (highest priority role wins)
        """
        role_boost = 0.0
        for role, boost in self.role_weights.items():
            if role in tags:
                role_boost = max(role_boost, boost)
        return role_boost

    def _compute_intent_boost(self, intent: str) -> float:
        """Compute intent boost from semantic intent.

        Args:
            intent: Semantic intent from IntentEnricher

        Returns:
            Intent boost (can be negative for low-value intents)
        """
        return self.intent_weights.get(intent, 0.0)

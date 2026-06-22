"""Field Scorer — Physics-Based Scoring with Intent Field Integration

@module quro.core.cqe.field_scorer
@intent Provide physics-based scoring for next-node selection with intent field guidance.

       Transition cost formula (Design 85 Phase 2):
       cost = ΔE + friction_cost + intent_penalty

       where:
       - ΔE: Energy gradient (natural flow)
       - friction_cost: Resistance based on energy-adjusted friction
       - intent_penalty: Misalignment with user intent

       Scoring formula (for compatibility):
       - Vector alignment: 0.7 (primary: semantic direction)
       - Stability: 0.2 (secondary: field stability)
       - Backward tension: 0.1 (tertiary: upstream pull - LIGHT)

       Critical constraint: backward_weight ≤ 0.15 (hard limit)
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class FieldScorer:
    """Physics-based scoring with intent field integration (Design 85 Phase 2).

    Provides two scoring modes:
    1. Legacy mode: Vector alignment + stability + backward tension
    2. Physics mode: Energy gradient + friction + intent penalty

    The physics mode enables directed navigation with intent guidance.
    """

    def __init__(
        self,
        backward_weight: float = 0.1,
        max_backward_weight: float = 0.15,
        intent_weight: float = 0.8,
        friction_weight: float = 0.4,
    ):
        """Initialize field scorer.

        Args:
            backward_weight: Weight for backward tension (default: 0.1)
            max_backward_weight: Hard limit for backward weight (default: 0.15)
            intent_weight: Weight for intent penalty in physics mode (default: 0.8)
            friction_weight: Weight for friction cost in physics mode (default: 0.4)
        """
        # Enforce hard limit
        if backward_weight > max_backward_weight:
            logger.warning(
                "backward_weight=%.2f exceeds limit %.2f, clamping",
                backward_weight,
                max_backward_weight
            )
            backward_weight = max_backward_weight

        self.backward_weight = backward_weight
        self.max_backward_weight = max_backward_weight
        self.intent_weight = intent_weight
        self.friction_weight = friction_weight

        logger.info(
            "FieldScorer initialized with backward_weight=%.2f, intent_weight=%.2f",
            self.backward_weight,
            self.intent_weight,
        )

    def compute_intent_alignment(
        self,
        symbol_vector: List[float],
        intent_vector: Optional[List[float]]
    ) -> float:
        """Compute alignment between symbol and intent vectors.

        Args:
            symbol_vector: Symbol's semantic vector (128-dim)
            intent_vector: User intent vector (128-dim), None if no intent

        Returns:
            Alignment score [0, 1]
        """
        if intent_vector is None:
            return 1.0  # No intent = perfect alignment (no penalty)

        return self._compute_alignment(symbol_vector, intent_vector)

    def compute_transition_cost(
        self,
        current_energy: float,
        next_energy: float,
        friction: float,
        intent_alignment: float,
    ) -> float:
        """Compute transition cost using physics-based model (Design 85 Phase 2).

        Formula:
        cost = ΔE + friction_cost + intent_penalty

        where:
        - ΔE = next_energy - current_energy (energy gradient)
        - friction_cost = friction × friction_weight
        - intent_penalty = (1 - alignment) × intent_weight

        Lower cost = better transition.

        Args:
            current_energy: Energy at current node
            next_energy: Energy at next node
            friction: Energy-adjusted friction coefficient [0, 1]
            intent_alignment: Alignment with intent vector [0, 1]

        Returns:
            Transition cost (lower = better)
        """
        # Energy gradient (natural flow toward higher energy = attractors)
        delta_E = next_energy - current_energy

        # Friction cost (resistance)
        friction_cost = friction * self.friction_weight

        # Intent penalty (misalignment cost)
        intent_penalty = (1.0 - intent_alignment) * self.intent_weight

        # Total cost
        cost = delta_E + friction_cost + intent_penalty

        return cost

    def compute_transition_score(
        self,
        current_energy: float,
        next_energy: float,
        friction: float,
        intent_alignment: float,
    ) -> float:
        """Compute transition score (inverse of cost) for compatibility.

        Higher score = better transition.

        Args:
            current_energy: Energy at current node
            next_energy: Energy at next node
            friction: Energy-adjusted friction coefficient [0, 1]
            intent_alignment: Alignment with intent vector [0, 1]

        Returns:
            Transition score [0, 1] (higher = better)
        """
        cost = self.compute_transition_cost(
            current_energy,
            next_energy,
            friction,
            intent_alignment
        )

        # Convert cost to score (sigmoid-like normalization)
        # Lower cost → higher score
        import math
        score = 1.0 / (1.0 + math.exp(cost))

        return score

    def score_next_node(
        self,
        candidate: str,
        intent_vector: List[float],
        current_direction: List[float],
        candidate_field: dict,
        use_backward: bool = True,
        use_physics: bool = False,
        current_energy: Optional[float] = None,
        next_energy: Optional[float] = None,
    ) -> float:
        """Score a candidate node for next-step selection.

        Supports two modes:
        1. Legacy mode (use_physics=False): Vector alignment + stability + backward
        2. Physics mode (use_physics=True): Energy gradient + friction + intent

        Args:
            candidate: Candidate node ID
            intent_vector: User intent vector (128-dim)
            current_direction: Current node's forward direction (128-dim)
            candidate_field: Candidate's anisotropic field data
            use_backward: Whether to include backward signal (legacy mode)
            use_physics: Whether to use physics-based scoring (default: False)
            current_energy: Current node energy (required for physics mode)
            next_energy: Next node energy (required for physics mode)

        Returns:
            Composite score [0, 1] (higher = better)
        """
        if use_physics:
            # Physics mode: energy gradient + friction + intent
            if current_energy is None or next_energy is None:
                logger.warning(
                    "Physics mode requires current_energy and next_energy, falling back to legacy"
                )
                use_physics = False
            else:
                friction = candidate_field.get("friction", 0.5)
                candidate_vector = candidate_field.get("forward_direction", [0.0] * 128)
                intent_alignment = self.compute_intent_alignment(candidate_vector, intent_vector)

                return self.compute_transition_score(
                    current_energy,
                    next_energy,
                    friction,
                    intent_alignment
                )

        # Legacy mode: vector alignment + stability + backward
        # Extract field components
        candidate_direction = candidate_field.get("forward_direction", [0.0] * 128)
        candidate_magnitude = candidate_field.get("forward_magnitude", 0.0)
        backward_tension = candidate_field.get("backward_tension", 0.0)

        # 1. Vector alignment (primary: 0.7)
        alignment = self._compute_alignment(
            current_direction,
            candidate_direction
        )

        # 2. Stability (secondary: 0.2)
        # Use magnitude as proxy for stability (high magnitude = stable field)
        stability = min(1.0, candidate_magnitude / 5.0)  # Normalize to [0, 1]

        # 3. Backward tension (tertiary: 0.1)
        if use_backward:
            backward_score = backward_tension
        else:
            backward_score = 0.0

        # Compute weighted score
        score = (
            alignment * 0.7 +
            stability * 0.2 +
            backward_score * self.backward_weight
        )

        return min(1.0, score)

    def _compute_alignment(
        self,
        vec_a: List[float],
        vec_b: List[float]
    ) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec_a: First vector
            vec_b: Second vector

        Returns:
            Cosine similarity [0, 1] (normalized to positive range)
        """
        import math

        # Handle zero vectors
        if all(x == 0 for x in vec_a) or all(x == 0 for x in vec_b):
            return 0.0

        # Compute dot product
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))

        # Compute magnitudes
        mag_a = math.sqrt(sum(x * x for x in vec_a))
        mag_b = math.sqrt(sum(x * x for x in vec_b))

        # Compute cosine similarity
        if mag_a == 0 or mag_b == 0:
            return 0.0

        cosine = dot_product / (mag_a * mag_b)

        # Normalize to [0, 1] range (cosine is in [-1, 1])
        return (cosine + 1.0) / 2.0

    def score_batch(
        self,
        candidates: List[str],
        intent_vector: List[float],
        current_direction: List[float],
        candidate_fields: dict,
        use_backward: bool = True
    ) -> List[tuple[str, float]]:
        """Score a batch of candidates.

        Args:
            candidates: List of candidate node IDs
            intent_vector: User intent vector
            current_direction: Current node's forward direction
            candidate_fields: Dict mapping candidate → field data
            use_backward: Whether to include backward signal

        Returns:
            List of (candidate, score) tuples, sorted by score descending
        """
        scored = []

        for candidate in candidates:
            field = candidate_fields.get(candidate, {})
            score = self.score_next_node(
                candidate,
                intent_vector,
                current_direction,
                field,
                use_backward
            )
            scored.append((candidate, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored

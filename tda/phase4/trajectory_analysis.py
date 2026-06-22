"""Trajectory Analysis and Comparison

@module quro.tda.phase4.trajectory_analysis
@intent Analyze, compare, and rank trajectory plans for quality assessment.
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class TrajectoryQuality:
    """Quality assessment for a trajectory (Phase 4 v2).

    Note: energy_efficiency removed — energy is a hint, not a decision signal.

    Attributes:
        overall_score: Overall quality score [0, 1] (higher = better)
        safety_score: Safety score (1 - friction risk) [0, 1]
        coherence_score: Coherence score [0, 1]
        intent_alignment_score: Intent alignment score [0, 1]
        path_length_score: Path length score [0, 1] (shorter = better)
        diversity_score: Diversity score [0, 1] (for multi-path ranking)
        grade: Quality grade (A/B/C/D/F)
    """
    overall_score: float
    safety_score: float
    coherence_score: float
    intent_alignment_score: float
    path_length_score: float
    diversity_score: float
    grade: str


@dataclass
class TrajectoryComparison:
    """Comparison between two trajectories.

    Attributes:
        better_path: Index of better path (0 or 1)
        score_delta: Score difference (positive = path 0 better)
        risk_delta: Risk difference
        coherence_delta: Coherence difference
        recommendation: Recommendation text
    """
    better_path: int
    score_delta: float
    risk_delta: float
    coherence_delta: float
    recommendation: str


class TrajectoryAnalyzer:
    """Analyze and compare trajectory plans (Phase 4 v2).

    Note: energy weighting removed. Energy is now a hint, not a decision signal.
    """

    def __init__(
        self,
        w_safety: float = 0.35,
        w_coherence: float = 0.25,
        w_intent: float = 0.25,
        w_length: float = 0.15,
    ):
        """Initialize trajectory analyzer.

        Args:
            w_safety: Weight for safety (1 - friction risk)
            w_coherence: Weight for coherence
            w_intent: Weight for intent alignment
            w_length: Weight for path length
        """
        self.w_safety = w_safety
        self.w_coherence = w_coherence
        self.w_intent = w_intent
        self.w_length = w_length

    def assess_quality(self, plan) -> TrajectoryQuality:
        """Assess trajectory quality (Phase 4 v2).

        Energy is no longer a decision signal — removed from scoring.

        Args:
            plan: TrajectoryPlan to assess

        Returns:
            TrajectoryQuality with detailed scores
        """
        # Safety score (lower friction = higher score)
        safety_score = max(0.0, 1.0 - plan.risk_score)

        # Coherence score (already in [0, 1])
        coherence_score = plan.coherence

        # Intent alignment score (already in [0, 1])
        intent_alignment_score = plan.avg_alignment

        # Path length score (shorter = better)
        path_length_score = max(0.0, 1.0 - len(plan.path) / 20.0)

        # Diversity score: use confidence from PathResult if available
        # Fallback to coherence as proxy
        diversity_score = getattr(plan, 'confidence', coherence_score)

        # Overall score (weighted combination, no energy)
        overall_score = (
            self.w_safety * safety_score +
            self.w_coherence * coherence_score +
            self.w_intent * intent_alignment_score +
            self.w_length * path_length_score
        )

        # Grade assignment
        if overall_score >= 0.9:
            grade = "A"
        elif overall_score >= 0.8:
            grade = "B"
        elif overall_score >= 0.7:
            grade = "C"
        elif overall_score >= 0.6:
            grade = "D"
        else:
            grade = "F"

        return TrajectoryQuality(
            overall_score=overall_score,
            safety_score=safety_score,
            coherence_score=coherence_score,
            intent_alignment_score=intent_alignment_score,
            path_length_score=path_length_score,
            diversity_score=diversity_score,
            grade=grade,
        )

    def compare_trajectories(
        self,
        plan1,
        plan2,
    ) -> TrajectoryComparison:
        """Compare two trajectory plans (Phase 4 v2).

        Args:
            plan1: First TrajectoryPlan
            plan2: Second TrajectoryPlan

        Returns:
            TrajectoryComparison with recommendation
        """
        quality1 = self.assess_quality(plan1)
        quality2 = self.assess_quality(plan2)

        score_delta = quality1.overall_score - quality2.overall_score
        risk_delta = plan1.risk_score - plan2.risk_score
        coherence_delta = plan1.coherence - plan2.coherence

        # Determine better path
        better_path = 0 if score_delta > 0 else 1

        # Generate recommendation
        if abs(score_delta) < 0.05:
            recommendation = "Paths are roughly equivalent in quality"
        elif better_path == 0:
            reasons = []
            if risk_delta < -0.1:
                reasons.append("safer")
            if coherence_delta > 0.1:
                reasons.append("more coherent")

            if reasons:
                recommendation = f"Path 1 is better: {', '.join(reasons)}"
            else:
                recommendation = "Path 1 is better overall"
        else:
            reasons = []
            if risk_delta > 0.1:
                reasons.append("safer")
            if coherence_delta < -0.1:
                reasons.append("more coherent")

            if reasons:
                recommendation = f"Path 2 is better: {', '.join(reasons)}"
            else:
                recommendation = "Path 2 is better overall"

        return TrajectoryComparison(
            better_path=better_path,
            score_delta=score_delta,
            risk_delta=risk_delta,
            coherence_delta=coherence_delta,
            recommendation=recommendation,
        )

    def rank_trajectories(self, plans: List) -> List[tuple[int, float]]:
        """Rank multiple trajectory plans by quality.

        Args:
            plans: List of TrajectoryPlan objects

        Returns:
            List of (plan_index, quality_score) tuples, sorted by score (descending)
        """
        scores = []
        for i, plan in enumerate(plans):
            quality = self.assess_quality(plan)
            scores.append((i, quality.overall_score))

        # Sort by score (descending)
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores

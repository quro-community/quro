"""
Adaptive MI-Gate Calculator

Implements Otsu-like MI-gate with local statistics for Phase 3.
Uses μ + k×σ threshold where k adapts to distribution shape.
"""

import math
from typing import Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class MIGateComponents:
    """Components of MI-gate calculation."""

    weights: list[float]  # Edge weights (MI values)
    mean: float  # μ
    std_dev: float  # σ
    k_factor: float  # Adaptive k based on distribution
    threshold: float  # τ = μ + k×σ
    is_uniform: bool  # True if σ ≈ 0 (uniform distribution)


class AdaptiveMIGate:
    """Calculates adaptive MI-gate threshold using local statistics."""

    def __init__(
        self,
        base_k: float = 0.5,
        uniform_threshold: float = 0.01,
    ):
        """Initialize adaptive MI-gate calculator.

        Args:
            base_k: Base k factor for τ = μ + k×σ (default 0.5)
            uniform_threshold: σ threshold for uniform detection (default 0.01)
        """
        self.base_k = base_k
        self.uniform_threshold = uniform_threshold

    def compute_gate(self, weights: list[float]) -> MIGateComponents:
        """Compute adaptive MI-gate threshold from edge weights.

        Formula: τ = μ + k×σ
        - Uniform distribution (σ ≈ 0): τ = μ, k = 0
        - Skewed distribution (high σ): k increases to filter outliers

        Args:
            weights: List of edge weights (MI values)

        Returns:
            MIGateComponents with threshold and metadata
        """
        if not weights:
            raise ValueError("weights cannot be empty")

        # Compute mean and std dev
        mean = sum(weights) / len(weights)
        variance = sum((w - mean) ** 2 for w in weights) / len(weights)
        std_dev = math.sqrt(variance)

        # Detect uniform distribution
        is_uniform = std_dev < self.uniform_threshold

        # Adaptive k factor
        if is_uniform:
            # Uniform distribution: τ = μ (no filtering)
            k_factor = 0.0
        else:
            # Skewed distribution: k increases with σ
            # Use coefficient of variation (CV = σ/μ) to adapt k
            cv = std_dev / mean if mean > 0 else 0
            k_factor = self.base_k * (1 + cv)

        # Compute threshold
        threshold = mean + k_factor * std_dev

        return MIGateComponents(
            weights=weights,
            mean=mean,
            std_dev=std_dev,
            k_factor=k_factor,
            threshold=threshold,
            is_uniform=is_uniform,
        )

    def compute_gate_batch(
        self,
        weight_groups: list[list[float]]
    ) -> list[MIGateComponents]:
        """Compute MI-gate for multiple weight groups.

        Args:
            weight_groups: List of weight lists

        Returns:
            List of MIGateComponents
        """
        return [self.compute_gate(weights) for weights in weight_groups]

    def filter_edges(
        self,
        edges: list[tuple[str, str]],
        weights: list[float]
    ) -> list[tuple[str, str]]:
        """Filter edges by MI-gate threshold.

        Args:
            edges: List of (source, target) tuples
            weights: Corresponding edge weights

        Returns:
            Filtered edges where weight ≥ threshold
        """
        if len(edges) != len(weights):
            raise ValueError("edges and weights must have same length")

        gate = self.compute_gate(weights)
        return [
            edge for edge, weight in zip(edges, weights)
            if weight >= gate.threshold
        ]

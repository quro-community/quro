"""
Friction Mapper

Maps Ricci curvature to edge friction for A* pathfinding.
Uses overflow-safe exponential mapping.
"""

import math
from typing import Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class FrictionComponents:
    """Components of friction calculation."""

    ricci_norm: float  # Normalized Ricci curvature
    friction: float  # Mapped friction value
    exponent: float  # Actual exponent used (after capping)
    was_capped: bool  # True if exponent was capped


class FrictionMapper:
    """Maps curvature to friction with overflow protection."""

    def __init__(
        self,
        base_friction: float = 1.0,
        alpha: float = 0.5,
        beta_cap: float = 5.0,
    ):
        """Initialize friction mapper.

        Args:
            base_friction: Base friction multiplier
            alpha: Curvature sensitivity (higher = more sensitive)
            beta_cap: Exponential cap to prevent overflow
        """
        self.base_friction = base_friction
        self.alpha = alpha
        self.beta_cap = beta_cap

    def compute_friction(self, ricci_norm: float) -> FrictionComponents:
        """Compute friction from normalized curvature.

        Formula: Friction = base × exp(min(β_cap, -α × Ric_norm))

        Positive curvature → negative exponent → friction < base (low friction)
        Negative curvature → positive exponent → friction > base (high friction)

        Args:
            ricci_norm: Normalized Ricci curvature

        Returns:
            FrictionComponents with friction and metadata
        """
        # Compute exponent with capping
        raw_exponent = -self.alpha * ricci_norm
        capped_exponent = min(self.beta_cap, raw_exponent)
        was_capped = raw_exponent > self.beta_cap

        # Compute friction
        friction = self.base_friction * math.exp(capped_exponent)

        return FrictionComponents(
            ricci_norm=ricci_norm,
            friction=friction,
            exponent=capped_exponent,
            was_capped=was_capped,
        )

    def compute_friction_batch(
        self,
        curvatures: list[float]
    ) -> list[FrictionComponents]:
        """Compute friction for multiple curvatures.

        Args:
            curvatures: List of normalized Ricci curvatures

        Returns:
            List of FrictionComponents
        """
        return [self.compute_friction(c) for c in curvatures]

    def get_friction_range(
        self,
        min_curvature: float,
        max_curvature: float,
        num_samples: int = 10
    ) -> list[tuple[float, float]]:
        """Get friction values across a curvature range.

        Args:
            min_curvature: Minimum curvature
            max_curvature: Maximum curvature
            num_samples: Number of samples

        Returns:
            List of (curvature, friction) tuples
        """
        if num_samples < 2:
            raise ValueError("num_samples must be >= 2")

        step = (max_curvature - min_curvature) / (num_samples - 1)
        result = []

        for i in range(num_samples):
            curvature = min_curvature + i * step
            friction_comp = self.compute_friction(curvature)
            result.append((curvature, friction_comp.friction))

        return result

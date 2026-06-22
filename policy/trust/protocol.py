"""Trust Policy Protocol - Pure function contract for trust computation.

@module quro.policy.trust.protocol
@intent Define the contract for trust policy implementations.
"""

from typing import Protocol, Dict, Tuple
from types import (
    TrustSignals,
    TrustRecord,
    TrustWeights,
    TrustComputeRequest,
    TrustPropagationRequest,
    UpstreamDependency,
)


class TrustPolicy(Protocol):
    """Pure function contract for trust computation engines.

    Invariant: All methods perform pure computation (no I/O).

    Implementations MUST:
    - Use frozen dataclasses for inputs/outputs
    - Be deterministic (same input → same output)
    - Handle edge cases gracefully (unknown symbols → 1.0)
    - Be synchronous (pure computation, no async)
    """

    def compute_trust(
        self,
        request: TrustComputeRequest,
        weights: TrustWeights,
    ) -> TrustRecord:
        """Compute trust score from individual signals.

        Args:
            request: Symbol and signals (frozen dataclass)
            weights: Trust formula weights (frozen dataclass)

        Returns:
            TrustRecord with computed trust score

        Invariant: Pure computation, deterministic.

        Formula:
            trust = w_f * freshness + w_r * recency + w_u * upstream_trust
                  + w_d * drift_stability + w_c * consumer_health

        All signals are clamped to [0, 1] before computation.
        """
        ...

    def propagate_upstream_trust(
        self,
        request: TrustPropagationRequest,
        weights: TrustWeights,
    ) -> Tuple[TrustRecord, ...]:
        """Propagate trust through dependency graph.

        Args:
            request: Records and dependencies (frozen dataclass)
            weights: Trust formula weights (frozen dataclass)

        Returns:
            Updated records with upstream trust propagated

        Invariant: Pure computation, no I/O.

        Algorithm:
            For each symbol:
                1. Find upstream dependencies (non-HERITAGE edges)
                2. Compute min trust of upstream deps
                3. Recompute trust with updated upstream_trust signal
        """
        ...

    def clamp_signal(self, value: float, lo: float = 0.0, hi: float = 1.0) -> float:
        """Clamp a signal value to [lo, hi].

        Args:
            value: Signal value to clamp
            lo: Lower bound (default 0.0)
            hi: Upper bound (default 1.0)

        Returns:
            Clamped value

        Invariant: Pure computation, deterministic.
        """
        ...

    def get_trust(
        self,
        symbol: str,
        records: Dict[str, TrustRecord],
        default: float = 1.0,
    ) -> float:
        """Get trust score for a symbol.

        Args:
            symbol: Symbol name
            records: Map of symbol → TrustRecord
            default: Default trust if symbol not found (default 1.0)

        Returns:
            Trust score [0, 1]

        Invariant: Pure computation, no side effects.
        """
        ...

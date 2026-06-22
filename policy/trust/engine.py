"""Trust Policy Engine - Pure trust computation implementation.

@module quro.policy.trust.engine
@intent Pure implementation of trust scoring logic with non-linear penalties.
"""

from typing import Dict, Tuple
from types import (
    TrustSignals,
    TrustRecord,
    TrustWeights,
    TrustComputeRequest,
    TrustPropagationRequest,
    UpstreamDependency,
)
from protocol import TrustPolicy
import time


# Trust policy constants
UNKNOWN_TRUST_DEFAULT = 0.5  # Neutral trust for unknown symbols (changed from 1.0)
UNVERIFIED_PENALTY = 0.2  # 20% penalty for unverified symbols


class TrustEngine:
    """Pure trust computation engine with non-linear penalties.

    Computes trust scores from staleness signals without I/O.

    Trust formula:
        Step 1: base_trust = weighted sum of freshness, recency, upstream_trust, consumer_health
        Step 2: stability_factor = drift_stability^4 (non-linear penalty)
        Step 3: verification_factor = (1 - UNVERIFIED_PENALTY) if not verified else 1.0
        Step 4: trust = min(base_trust * stability_factor * verification_factor, semantic_gravity)
    """

    def compute_trust(
        self,
        request: TrustComputeRequest,
        weights: TrustWeights,
    ) -> TrustRecord:
        """Compute trust score from individual signals with non-linear penalties.

        Args:
            request: Symbol and signals
            weights: Trust formula weights

        Returns:
            TrustRecord with computed trust score
        """
        signals = request.signals

        # Clamp all signals to [0, 1]
        f = self.clamp_signal(signals.freshness)
        r = self.clamp_signal(signals.recency)
        u = self.clamp_signal(signals.upstream_trust)
        d = self.clamp_signal(signals.drift_stability)
        # Consumer health must be > 0 to avoid division by zero
        c = self.clamp_signal(max(signals.consumer_health, 0.001))
        g = self.clamp_signal(signals.semantic_gravity)

        # Step 1: Compute base trust (linear weighted sum, excluding drift)
        base_trust = (
            weights.freshness * f
            + weights.recency * r
            + weights.upstream_trust * u
            + weights.consumer_health * c
        )

        # Step 2: Apply non-linear stability penalty (drift^4)
        stability_factor = self._compute_stability_factor(d)

        # Step 3: Apply verification penalty
        verification_factor = 1.0 if signals.verified else (1.0 - UNVERIFIED_PENALTY)

        # Step 4: Compute trust with penalties
        trust = base_trust * stability_factor * verification_factor

        # Step 5: Apply semantic gravity ceiling
        trust = min(trust, g)

        return TrustRecord(
            symbol=request.symbol,
            trust=round(trust, 4),
            freshness=f,
            recency=r,
            upstream_trust=u,
            drift_stability=d,
            consumer_health=c,
            computed_at=time.time(),
            signals_frozen=False,
        )

    def _compute_stability_factor(self, drift_stability: float) -> float:
        """Compute non-linear stability penalty factor.

        Formula: stability_factor = drift_stability^4

        This creates exponential trust decay when drift increases:
        - drift_stability=1.0 → factor=1.0 (no penalty)
        - drift_stability=0.9 → factor=0.66 (moderate penalty)
        - drift_stability=0.7 → factor=0.24 (severe penalty)
        - drift_stability=0.5 → factor=0.06 (catastrophic)
        - drift_stability=0.0 → factor=0.0 (total collapse)

        Args:
            drift_stability: Drift stability signal [0, 1]

        Returns:
            Stability penalty factor [0, 1]
        """
        return drift_stability ** 4

    def propagate_upstream_trust(
        self,
        request: TrustPropagationRequest,
        weights: TrustWeights,
    ) -> Tuple[TrustRecord, ...]:
        """Propagate trust through dependency graph.

        Args:
            request: Records and dependencies
            weights: Trust formula weights

        Returns:
            Updated records with upstream trust propagated
        """
        # Build map: symbol → TrustRecord
        records_map: Dict[str, TrustRecord] = {
            r.symbol: r for r in request.records
        }

        # Build upstream dependency map: symbol → set of upstream symbols
        upstream_map: Dict[str, set] = {}
        for dep in request.dependencies:
            # Only consider non-HERITAGE edges (semantic ordering)
            if dep.edge_type != "HERITAGE":
                upstream_map.setdefault(dep.to_symbol, set()).add(dep.from_symbol)

        # Recompute trust with upstream propagation
        updated_records: list[TrustRecord] = []
        now = time.time()

        for record in request.records:
            upstream_deps = upstream_map.get(record.symbol, set())

            if upstream_deps:
                # Compute min trust of upstream dependencies
                min_upstream = min(
                    records_map.get(
                        dep,
                        TrustRecord(
                            symbol=dep,
                            trust=1.0,
                            freshness=1.0,
                            recency=1.0,
                            upstream_trust=1.0,
                            drift_stability=1.0,
                            consumer_health=1.0,
                            computed_at=now,
                            signals_frozen=True,
                        ),
                    ).trust
                    for dep in upstream_deps
                )

                # Recompute with updated upstream_trust
                updated_signals = TrustSignals(
                    freshness=record.freshness,
                    recency=record.recency,
                    upstream_trust=min_upstream,
                    drift_stability=record.drift_stability,
                    consumer_health=record.consumer_health,
                )

                compute_request = TrustComputeRequest(
                    symbol=record.symbol,
                    signals=updated_signals,
                )

                updated_record = self.compute_trust(compute_request, weights)
                updated_records.append(updated_record)
            else:
                # No upstream deps, keep original record
                updated_records.append(record)

        return tuple(updated_records)

    def clamp_signal(self, value: float, lo: float = 0.0, hi: float = 1.0) -> float:
        """Clamp a signal value to [lo, hi].

        Args:
            value: Signal value to clamp
            lo: Lower bound
            hi: Upper bound

        Returns:
            Clamped value
        """
        return max(lo, min(hi, value))

    def get_trust(
        self,
        symbol: str,
        records: Dict[str, TrustRecord],
        default: float = UNKNOWN_TRUST_DEFAULT,
    ) -> float:
        """Get trust score for a symbol.

        Args:
            symbol: Symbol name
            records: Map of symbol → TrustRecord
            default: Default trust if symbol not found (0.5 = neutral)

        Returns:
            Trust score [0, 1]

        Rationale:
            Unknown symbols are neither trustworthy nor untrustworthy.
            Neutral default (0.5) forces verification before high-trust operations.
        """
        record = records.get(symbol)
        return record.trust if record else default

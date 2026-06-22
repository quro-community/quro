"""Trust Policy Types - Frozen dataclasses for trust scoring.

@module quro.policy.trust.types
@intent Define immutable data structures for trust computation.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class TrustSignals:
    """Observable staleness signals for a single symbol.

    All values are clamped to [0, 1] except consumer_health which is (0, 1].

    Invariant: All fields are immutable.
    """

    freshness: float  # {0.0, 1.0} from CRC32 checksum comparison
    recency: float  # [0, 1] linear decay over 7 days from shadow mtime
    upstream_trust: float  # [0, 1] min trust of upstream deps
    drift_stability: float  # [0, 1] 1 - lsh_drift / threshold
    consumer_health: float  # (0, 1] 1 / (1 + downstream_quarantined)
    verified: bool = True  # Has this symbol been verified?
    semantic_gravity: float = 1.0  # [0, 1] Coupling-based complexity penalty


@dataclass(frozen=True)
class TrustRecord:
    """Immutable snapshot of a symbol's trust state.

    Invariant: All fields are immutable.
    """

    symbol: str
    trust: float
    freshness: float
    recency: float
    upstream_trust: float
    drift_stability: float
    consumer_health: float
    computed_at: float
    signals_frozen: bool


@dataclass(frozen=True)
class TrustWeights:
    """Configurable weights for trust formula.

    Note: drift_stability is now applied as a non-linear penalty factor,
    not as part of the weighted sum. Only the first 4 weights are summed.

    Base trust formula:
        base_trust = 0.40 * freshness + 0.30 * recency + 0.20 * upstream_trust
                   + 0.10 * consumer_health

    Final trust formula:
        trust = min(base_trust * (drift_stability^4) * verification_factor, semantic_gravity)

    Invariant: freshness + recency + upstream_trust + consumer_health must sum to 1.0.
    """

    freshness: float = 0.40
    recency: float = 0.30
    upstream_trust: float = 0.20
    consumer_health: float = 0.10

    def __post_init__(self):
        """Validate weights sum to 1.0 (excluding drift_stability)."""
        total = (
            self.freshness
            + self.recency
            + self.upstream_trust
            + self.consumer_health
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Trust weights must sum to 1.0, got {total}")


@dataclass(frozen=True)
class TrustComputeRequest:
    """Request to compute trust for a symbol.

    Invariant: All fields are immutable.
    """

    symbol: str
    signals: TrustSignals


@dataclass(frozen=True)
class UpstreamDependency:
    """Upstream dependency for trust propagation.

    Invariant: All fields are immutable.
    """

    from_symbol: str
    to_symbol: str
    edge_type: str  # "SEMANTIC" | "HERITAGE"


@dataclass(frozen=True)
class TrustPropagationRequest:
    """Request to propagate trust through dependency graph.

    Invariant: All fields are immutable.
    """

    records: Tuple[TrustRecord, ...]
    dependencies: Tuple[UpstreamDependency, ...]

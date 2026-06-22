"""Self-Heal Policy Types - Frozen dataclasses for autonomous refactoring.

@module quro.policy.self_heal.types
@intent Define immutable data structures for self-healing proposals.
"""

from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass(frozen=True)
class AtomPatchOp:
    """Single atomic patch operation.

    Invariant: All fields are immutable.
    """

    action: str  # "REPLACE" | "INSERT" | "DELETE"
    target_line: int  # Line number to target
    new_atom: Optional[str]  # New atom text (for REPLACE/INSERT)
    insert_after: Optional[int]  # Line to insert after (for INSERT)


@dataclass(frozen=True)
class AtomPatch:
    """Collection of atomic patch operations for a symbol.

    Invariant: All fields are immutable.
    """

    symbol: str
    expected_checksum: str  # CRC32 checksum from qss file
    ops: Tuple[AtomPatchOp, ...]


@dataclass(frozen=True)
class HealProposal:
    """Autonomous refactoring proposal.

    Invariant: All fields are immutable.
    """

    proposal_id: str
    symbol: str
    description: str
    atom_patch: AtomPatch
    predicted_risk_delta: float  # Negative = improvement
    high_risk: bool  # Crosses STA boundary?
    validation_trials: int  # Number of Monte Carlo trials used


@dataclass(frozen=True)
class HealDecision:
    """Decision on whether to apply a heal proposal.

    Invariant: All fields are immutable.
    """

    proposal_id: str
    approved: bool
    reason: str  # Why approved/rejected
    trust_score: float  # Trust score of target symbol
    nrt_breach: bool  # Does symbol have NRT breach?


@dataclass(frozen=True)
class HealResult:
    """Result of applying a heal proposal.

    Invariant: All fields are immutable.
    """

    proposal_id: str
    success: bool
    error: Optional[str]
    new_risk_score: float
    applied_at: float


@dataclass(frozen=True)
class HealRequest:
    """Request to evaluate heal proposals.

    Invariant: All fields are immutable.
    """

    proposals: Tuple[HealProposal, ...]
    trust_scores: Tuple[Tuple[str, float], ...]  # (symbol, trust) pairs
    nrt_breaches: Tuple[str, ...]  # Symbols with NRT breaches
    force_high_risk: bool = False

"""Self-Heal Policy Protocol - Pure function contract for heal decisions.

@module quro.policy.self_heal.protocol
@intent Define the contract for self-heal policy implementations.
"""

from typing import Protocol, Tuple
from types import (
    HealProposal,
    HealDecision,
    HealRequest,
)


class SelfHealPolicy(Protocol):
    """Pure function contract for self-heal decision engines.

    Invariant: All methods perform pure computation (no I/O).

    Implementations MUST:
    - Use frozen dataclasses for inputs/outputs
    - Be deterministic (same input → same output)
    - Handle edge cases gracefully
    - Be synchronous (pure computation, no async)
    """

    def evaluate_proposal(
        self,
        proposal: HealProposal,
        trust_score: float,
        nrt_breach: bool,
        force_high_risk: bool = False,
    ) -> HealDecision:
        """Evaluate a single heal proposal.

        Args:
            proposal: Heal proposal to evaluate
            trust_score: Trust score of target symbol [0, 1]
            nrt_breach: Does symbol have NRT breach?
            force_high_risk: Override high-risk rejection?

        Returns:
            HealDecision with approval status and reason

        Invariant: Pure computation, deterministic.

        Decision Logic:
            1. If nrt_breach → REJECT (symbol has active breach)
            2. If trust_score < 0.5 → REJECT (low trust)
            3. If high_risk and not force_high_risk → REJECT (crosses STA)
            4. If predicted_risk_delta >= 0 → REJECT (no improvement)
            5. Otherwise → APPROVE
        """
        ...

    def evaluate_batch(
        self,
        request: HealRequest,
    ) -> Tuple[HealDecision, ...]:
        """Evaluate multiple heal proposals.

        Args:
            request: Batch heal request with proposals and context

        Returns:
            Tuple of HealDecision objects

        Invariant: Pure computation, no I/O.
        """
        ...

    def filter_approved(
        self,
        decisions: Tuple[HealDecision, ...],
    ) -> Tuple[str, ...]:
        """Filter approved proposal IDs.

        Args:
            decisions: Tuple of HealDecision objects

        Returns:
            Tuple of approved proposal IDs

        Invariant: Pure computation, deterministic.
        """
        ...

    def compute_risk_threshold(
        self,
        trust_score: float,
        nrt_breach: bool,
    ) -> float:
        """Compute risk improvement threshold based on trust.

        Args:
            trust_score: Trust score of target symbol [0, 1]
            nrt_breach: Does symbol have NRT breach?

        Returns:
            Minimum risk improvement required (negative value)

        Invariant: Pure computation, deterministic.

        Formula:
            If nrt_breach: threshold = -inf (reject all)
            If trust < 0.5: threshold = -0.1 (require 10% improvement)
            If trust < 0.7: threshold = -0.05 (require 5% improvement)
            Otherwise: threshold = -0.01 (require 1% improvement)
        """
        ...

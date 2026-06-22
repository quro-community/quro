"""Self-Heal Policy Engine - Pure heal decision implementation.

@module quro.policy.self_heal.engine
@intent Pure implementation of self-heal decision logic.
"""

from typing import Tuple
from types import (
    HealProposal,
    HealDecision,
    HealRequest,
)
from protocol import SelfHealPolicy
import time


# Decision thresholds
MIN_TRUST_THRESHOLD = 0.5  # Minimum trust to approve heal
LOW_TRUST_THRESHOLD = 0.7  # Trust below this requires higher risk improvement


class SelfHealEngine:
    """Pure self-heal decision engine.

    Evaluates heal proposals based on trust, NRT breaches, and risk improvement.
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
        """
        # Rule 1: Reject if symbol has active NRT breach
        if nrt_breach:
            return HealDecision(
                proposal_id=proposal.proposal_id,
                approved=False,
                reason="Symbol has active NRT breach - fix breach first",
                trust_score=trust_score,
                nrt_breach=True,
            )

        # Rule 2: Reject if trust score too low
        if trust_score < MIN_TRUST_THRESHOLD:
            return HealDecision(
                proposal_id=proposal.proposal_id,
                approved=False,
                reason=f"Trust score {trust_score:.2f} below minimum {MIN_TRUST_THRESHOLD}",
                trust_score=trust_score,
                nrt_breach=False,
            )

        # Rule 3: Reject high-risk proposals unless forced
        if proposal.high_risk and not force_high_risk:
            return HealDecision(
                proposal_id=proposal.proposal_id,
                approved=False,
                reason="Proposal crosses STA boundary (high risk) - requires manual approval",
                trust_score=trust_score,
                nrt_breach=False,
            )

        # Rule 4: Check risk improvement threshold
        risk_threshold = self.compute_risk_threshold(trust_score, nrt_breach)
        if proposal.predicted_risk_delta >= risk_threshold:
            return HealDecision(
                proposal_id=proposal.proposal_id,
                approved=False,
                reason=(
                    f"Insufficient risk improvement: delta={proposal.predicted_risk_delta:.4f}, "
                    f"required<{risk_threshold:.4f}"
                ),
                trust_score=trust_score,
                nrt_breach=False,
            )

        # Rule 5: Approve
        return HealDecision(
            proposal_id=proposal.proposal_id,
            approved=True,
            reason=(
                f"Approved: trust={trust_score:.2f}, "
                f"risk_delta={proposal.predicted_risk_delta:.4f}, "
                f"high_risk={proposal.high_risk}"
            ),
            trust_score=trust_score,
            nrt_breach=False,
        )

    def evaluate_batch(
        self,
        request: HealRequest,
    ) -> Tuple[HealDecision, ...]:
        """Evaluate multiple heal proposals.

        Args:
            request: Batch heal request with proposals and context

        Returns:
            Tuple of HealDecision objects
        """
        # Build trust score lookup
        trust_map = dict(request.trust_scores)

        # Build NRT breach set
        breach_set = set(request.nrt_breaches)

        # Evaluate each proposal
        decisions = []
        for proposal in request.proposals:
            trust_score = trust_map.get(proposal.symbol, 0.5)  # Default to neutral
            nrt_breach = proposal.symbol in breach_set

            decision = self.evaluate_proposal(
                proposal=proposal,
                trust_score=trust_score,
                nrt_breach=nrt_breach,
                force_high_risk=request.force_high_risk,
            )
            decisions.append(decision)

        return tuple(decisions)

    def filter_approved(
        self,
        decisions: Tuple[HealDecision, ...],
    ) -> Tuple[str, ...]:
        """Filter approved proposal IDs.

        Args:
            decisions: Tuple of HealDecision objects

        Returns:
            Tuple of approved proposal IDs
        """
        return tuple(d.proposal_id for d in decisions if d.approved)

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

        Formula:
            If nrt_breach: threshold = 0.0 (reject all - handled by Rule 1)
            If trust < 0.5: threshold = 0.0 (reject all - handled by Rule 2)
            If trust < 0.7: threshold = -0.05 (require 5% improvement)
            Otherwise: threshold = -0.01 (require 1% improvement)
        """
        if nrt_breach:
            return 0.0  # Will be rejected by Rule 1

        if trust_score < MIN_TRUST_THRESHOLD:
            return 0.0  # Will be rejected by Rule 2

        if trust_score < LOW_TRUST_THRESHOLD:
            return -0.05  # Require 5% risk improvement

        return -0.01  # Require 1% risk improvement

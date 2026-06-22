"""Fix Plan Stability Layer

@module quro.pipeline.cqe.stability
@intent SOFT CONTROL: Prevent oscillation, redundant fixes, and micro-optimizations
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict, Set
from dataclasses import dataclass, field
from .types import FixPlanAction, GraphEntropyMetrics

logger = logging.getLogger(__name__)


@dataclass
class StabilityState:
    """Persistent state for the Stability Layer to track historical modifications.

    This is serialized to disk as JSON and survives across index builds.

    Attributes:
        applied_hashes: Set of action hashes that have been applied historically
        node_modified_counts: Dict mapping node → modification count
        last_entropy_score: Last recorded entropy score
        entropy_history: Sliding window of recent entropy scores (last 5 builds)
    """
    applied_hashes: Set[str] = field(default_factory=set)
    node_modified_counts: Dict[str, int] = field(default_factory=dict)
    last_entropy_score: float = 0.0
    entropy_history: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "applied_hashes": sorted(self.applied_hashes),
            "node_modified_counts": self.node_modified_counts,
            "last_entropy_score": self.last_entropy_score,
            "entropy_history": self.entropy_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StabilityState":
        """Deserialize from JSON-compatible dict."""
        return cls(
            applied_hashes=set(data.get("applied_hashes", [])),
            node_modified_counts=data.get("node_modified_counts", {}),
            last_entropy_score=data.get("last_entropy_score", 0.0),
            entropy_history=data.get("entropy_history", []),
        )

    @classmethod
    def load(cls, state_path: Path) -> "StabilityState":
        """Load stability state from disk. Returns fresh state if file missing."""
        if not state_path.exists():
            logger.debug("No stability state found at %s, starting fresh", state_path)
            return cls()
        try:
            data = json.loads(state_path.read_text())
            state = cls.from_dict(data)
            logger.info(
                "Loaded stability state: %d applied hashes, "
                "%.2f last entropy",
                len(state.applied_hashes),
                state.last_entropy_score,
            )
            return state
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Corrupt stability state, starting fresh: %s", e)
            return cls()

    def save(self, state_path: Path) -> None:
        """Persist stability state to disk."""
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(self.to_dict(), indent=2))
        logger.debug("Saved stability state to %s", state_path)

    def should_skip_detox(
        self,
        current_entropy: float,
        window_size: int = 5,
        epsilon: float = 5.0,
    ) -> bool:
        """Check if system is stable (entropy unchanged in sliding window).

        Uses sliding window entropy tracking to detect stable systems.
        If entropy hasn't changed significantly in recent builds, skip detox.

        Args:
            current_entropy: Current entropy score
            window_size: Number of recent builds to consider (default: 5)
            epsilon: Minimum entropy change threshold (default: 5.0)

        Returns:
            True if system is stable (skip detox), False otherwise
        """
        if len(self.entropy_history) < window_size:
            return False  # Not enough history, run detox

        recent_window = self.entropy_history[-window_size:]
        avg_entropy = sum(recent_window) / window_size
        delta = abs(current_entropy - avg_entropy)

        return delta < epsilon  # System stable if Δ < ε

    def record_entropy(self, entropy_score: float, max_history: int = 10) -> None:
        """Record entropy score in sliding window.

        Args:
            entropy_score: Entropy score to record
            max_history: Maximum history size (default: 10)
        """
        self.entropy_history.append(entropy_score)
        # Keep only recent history
        if len(self.entropy_history) > max_history:
            self.entropy_history = self.entropy_history[-max_history:]


class FixPlanStabilityLayer:
    """Fix Plan Stability Layer - SOFT CONTROL.

    Prevents oscillation, redundant fixes, and micro-optimizations.

    Mechanisms:
    1. Plan Deduplication: Skip actions that have been applied historically
    2. Structural Inertia: Freeze nodes after max_modifications
    3. Diff Threshold Gate: Skip fixes if entropy hasn't changed significantly
    """

    def __init__(
        self,
        state: StabilityState,
        max_modifications: int = 3,
        entropy_diff_threshold: float = 5.0,
    ):
        """Initialize stability layer.

        Args:
            state: Persistent stability state
            max_modifications: Max modifications per node before freezing
            entropy_diff_threshold: Min entropy change to allow fixes
        """
        self.state = state
        self.max_modifications = max_modifications
        self.entropy_diff_threshold = entropy_diff_threshold

    def filter_plan(
        self,
        current_plan: List[FixPlanAction],
        current_entropy: GraphEntropyMetrics,
    ) -> List[FixPlanAction]:
        """Filter raw fix plan based on stability mechanisms.

        Args:
            current_plan: Raw fix plan from detox scanner
            current_entropy: Current graph entropy metrics

        Returns:
            Filtered fix plan (may be empty if no significant drift)

        Filtering stages:
        1. Diff Threshold Gate: Skip all fixes if entropy hasn't changed
        2. Plan Deduplication: Skip actions applied historically
        3. Structural Inertia: Skip nodes modified too many times
        """
        # 1. Diff Threshold Gate
        # If the graph entropy hasn't changed significantly, reject all fixes
        # to prevent micro-oscillations
        if self.state.last_entropy_score > 0:
            entropy_diff = abs(
                current_entropy.entropy_score - self.state.last_entropy_score
            )
            if entropy_diff < self.entropy_diff_threshold:
                logger.info(
                    "Entropy diff %.2f < threshold %.2f, skipping fixes",
                    entropy_diff,
                    self.entropy_diff_threshold,
                )
                return []  # No significant drift, skip fixes

        stable_plan = []
        for action in current_plan:
            # 2. Plan Deduplication
            action_hash = self._hash_action(action)
            if action_hash in self.state.applied_hashes:
                logger.debug(
                    "Skipping duplicate action: %s on %s",
                    action.action_type,
                    action.target,
                )
                continue  # Already applied historically

            # 3. Structural Inertia
            mod_count = self.state.node_modified_counts.get(action.target, 0)
            if mod_count >= self.max_modifications:
                logger.debug(
                    "Skipping frozen node: %s (modified %d times)",
                    action.target,
                    mod_count,
                )
                continue  # Node is frozen due to too many historical modifications

            stable_plan.append(action)

        logger.info(
            "Stability filter: %d/%d actions passed",
            len(stable_plan),
            len(current_plan),
        )
        return stable_plan

    def commit_plan(
        self,
        applied_plan: List[FixPlanAction],
        new_entropy: GraphEntropyMetrics,
    ) -> None:
        """Update stability state after Indexer successfully applies the plan.

        Args:
            applied_plan: Actions that were successfully applied
            new_entropy: New graph entropy metrics after applying plan
        """
        self.state.last_entropy_score = new_entropy.entropy_score
        for action in applied_plan:
            self.state.applied_hashes.add(self._hash_action(action))
            self.state.node_modified_counts[action.target] = (
                self.state.node_modified_counts.get(action.target, 0) + 1
            )
        logger.info(
            "Committed %d actions, new entropy: %.2f",
            len(applied_plan),
            new_entropy.entropy_score,
        )

    def _hash_action(self, action: FixPlanAction) -> str:
        """Create deterministic hash for an action.

        Args:
            action: Fix plan action

        Returns:
            SHA256 hash of action (action_type:target:details)
        """
        # Sort details to ensure stable hashing
        details_str = json.dumps(action.details, sort_keys=True)
        raw_str = f"{action.action_type}:{action.target}:{details_str}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

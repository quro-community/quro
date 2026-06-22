"""NRT Policy Protocol - Pure function contract.

@module quro.policy.nrt.protocol
@intent Define the contract for NRT policy implementations.
"""

from typing import Protocol, List
from types import (
    NRTResult,
    ShadowRule,
    CrossSTAConflict,
    PatchSuggestion,
    BreachCheckRequest,
    RuleLoadRequest,
)


class NRTPolicy(Protocol):
    """Pure function contract for NRT policy engines.

    Invariant: All methods perform pure computation (no I/O).

    Implementations MUST:
    - Use frozen dataclasses for inputs/outputs
    - Be deterministic (same input → same output)
    - Handle edge cases gracefully
    - Be synchronous (pure computation, no async)
    """

    def check_breach(
        self,
        request: BreachCheckRequest,
        atoms: List[dict],
        rules: List[ShadowRule],
    ) -> NRTResult:
        """Check shadow atoms against NRT rules.

        Args:
            request: Breach check request (frozen dataclass)
            atoms: List of atom dicts (from shadow file)
            rules: List of compiled rules to evaluate

        Returns:
            NRTResult with breach status

        Invariant: Pure computation, no I/O.
        """
        ...

    def evaluate_predicate(
        self,
        predicate: str,
        atoms: List[dict],
    ) -> tuple[bool, str]:
        """Evaluate a single NPL predicate against atoms.

        Args:
            predicate: NPL predicate string (e.g., "no ACQ(X)")
            atoms: List of atom dicts

        Returns:
            (passed, error_message) tuple

        Invariant: Pure computation, deterministic.
        """
        ...

    def detect_cross_sta_conflicts(
        self,
        atoms_by_symbol: dict[str, List[dict]],
        edges: List[tuple[str, str]],
    ) -> List[CrossSTAConflict]:
        """Detect cross-symbol state conflicts (data races).

        Args:
            atoms_by_symbol: Map of symbol name to atom list
            edges: List of (from_symbol, to_symbol) edges

        Returns:
            List of detected conflicts

        Invariant: Pure computation, no I/O.
        """
        ...

    def generate_patch_suggestion(
        self,
        symbol: str,
        atoms: List[dict],
        missing_resource: str,
    ) -> PatchSuggestion | None:
        """Generate auto-fix patch suggestion for missing REL.

        Args:
            symbol: Symbol name
            atoms: List of atom dicts
            missing_resource: Resource missing REL

        Returns:
            PatchSuggestion if fixable, None otherwise

        Invariant: Pure computation, deterministic.
        """
        ...

"""NRT Policy Types - Immutable data structures for NRT breach detection.

@module quro.policy.nrt.types
@intent Define pure data contracts for NRT policy operations.
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Literal


BreachType = Literal["CRITICAL_LOGIC_BREACH", "UPSTREAM_TAMPERED", "CLEAR"]
Severity = Literal["CRITICAL", "WARNING", "INFO"]


@dataclass(frozen=True)
class NRTResult:
    """Pure data: NRT check result (immutable).

    Represents the outcome of a single NRT breach detection check.
    """
    symbol: str
    qss_path: str
    qra_path: Optional[str]
    breach_type: BreachType
    predicate: str
    note: str
    severity: Severity


@dataclass(frozen=True)
class ShadowRule:
    """Pure data: compiled NRT predicate (immutable).

    Represents a compiled rule derived from qra @INVARIANT field.
    """
    rule_for: str
    source_qra_ck: str
    predicate: str
    severity: Severity
    note: str


@dataclass(frozen=True)
class CrossSTAConflict:
    """Pure data: cross-symbol state conflict (immutable).

    Represents a detected data race between two symbols.
    """
    symbol_a: str
    symbol_b: str
    variable: str
    note: str


@dataclass(frozen=True)
class PatchSuggestion:
    """Pure data: auto-fix patch suggestion (immutable).

    Represents a suggested fix for a detected breach.
    """
    symbol: str
    insert_after_line: int
    atom_to_insert: str
    rationale: str


@dataclass(frozen=True)
class BreachCheckRequest:
    """Pure data: breach check request (immutable).

    Request to check a shadow file for breaches.
    """
    symbol: str
    qss_path: str
    qra_path: Optional[str] = None


@dataclass(frozen=True)
class RuleLoadRequest:
    """Pure data: rule load request (immutable).

    Request to load compiled rules for a symbol.
    """
    symbol: str

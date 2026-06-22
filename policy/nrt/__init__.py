"""NRT Policy - Public API.

@module quro.policy.nrt
@intent Expose clean NRT breach detection via Protocol-driven design.
"""

from types import (
    NRTResult,
    ShadowRule,
    CrossSTAConflict,
    PatchSuggestion,
    BreachCheckRequest,
    RuleLoadRequest,
    BreachType,
    Severity,
)
from protocol import NRTPolicy
from engine import NRTEngine

__all__ = [
    # Types
    "NRTResult",
    "ShadowRule",
    "CrossSTAConflict",
    "PatchSuggestion",
    "BreachCheckRequest",
    "RuleLoadRequest",
    "BreachType",
    "Severity",
    # Protocol
    "NRTPolicy",
    # Implementation
    "NRTEngine",
]

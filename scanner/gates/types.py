"""Scanner v3 - Gate Types

@module quro.scanner.gates.types
@intent Stateless gate operators for filtering
@constraint Pure functions, no I/O, immutable results
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class GateResult:
    """Immutable gate validation result.

    Used by all gates to return validation status.
    """

    passed: bool
    """True if validation passed, False if rejected"""

    reason: Optional[str] = None
    """Rejection reason (e.g., 'file_too_large', 'blacklisted_symbol')"""

    modified_data: Optional[Dict[str, Any]] = None
    """Modified data for transform gates (e.g., capped features)"""

    metadata: Dict[str, Any] = None
    """Optional metadata (e.g., file size, symbol count)"""

    def __post_init__(self):
        """Initialize metadata if None."""
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})

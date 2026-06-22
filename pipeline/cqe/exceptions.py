"""CQE Pipeline Gate Exceptions

@module quro.pipeline.cqe.exceptions
@intent Specialized exception hierarchy for gate violations
"""


class CQEGateError(Exception):
    """Base exception for CQE gate violations."""
    pass


class HardGateViolation(CQEGateError):
    """Hard gate violation - blocks publication immediately.

    Raised when:
    - Alias consistency violations (I2)
    - Catastrophic topology changes
    - Data corruption detected

    System behavior: STOP - do not publish index
    """
    pass


class AdvisoryGateWarning(CQEGateError):
    """Advisory gate warning - logged, system continues with degraded mode.

    Raised when:
    - God nodes detected (I1)
    - Path decay violations (I3)
    - Non-critical detox issues

    System behavior: LOG + CONTINUE - publish index with advisory flag
    """
    pass


class InputGateRejection(CQEGateError):
    """Input gate rejection - atom/morphism filtered at extraction.

    Raised when:
    - Blacklisted symbol name
    - File not found
    - .quroignore match
    - Flat path (no directory)

    System behavior: SKIP - atom not added to index
    """
    pass

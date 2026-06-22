"""Scanner v3 - Fingerprint Computation

@module quro.scanner.core.fingerprint
@intent Pure content-based fingerprinting (SHA256)
@constraint No I/O, deterministic
"""

import hashlib


def compute_fingerprint(content: str) -> str:
    """Compute SHA256 fingerprint of content.

    Pure function: same content → same fingerprint

    Args:
        content: Text content to fingerprint

    Returns:
        Hex-encoded SHA256 hash

    Example:
        >>> compute_fingerprint("hello world")
        'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9'
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_symbol_fingerprint(
    name: str,
    kind: str,
    signature: str | None,
    source_snippet: str,
) -> str:
    """Compute fingerprint for a symbol.

    Combines symbol metadata + source snippet for stable identity.

    Args:
        name: Symbol name
        kind: Symbol kind
        signature: Function/method signature
        source_snippet: Source code snippet (normalized)

    Returns:
        Hex-encoded SHA256 hash
    """
    parts = [
        name,
        kind,
        signature or "",
        source_snippet,
    ]
    combined = "|".join(parts)
    return compute_fingerprint(combined)

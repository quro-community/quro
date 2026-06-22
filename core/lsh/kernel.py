"""LSH Kernel Protocol - Pure function contract.

@module quro.core.lsh.kernel
@intent Define the contract for LSH kernel implementations.
"""

from typing import Protocol, Set
from types import LSHSignature


class LSHKernel(Protocol):
    """Pure function contract for LSH kernel.

    Invariant: All methods are pure (no side effects).

    Implementations MUST NOT:
    - Perform I/O (file, database, network)
    - Mutate input arguments
    - Access global state
    - Call logging functions
    """

    def compute_signature(self, tokens: Set[str]) -> LSHSignature:
        """Pure: tokens → LSH signature.

        Args:
            tokens: Set of tokens (words, n-grams, behavioral tags)

        Returns:
            LSHSignature with hash_values and bands

        Invariant: Same tokens always produce same signature (deterministic).
        """
        ...

    def compute_similarity(self, sig1: LSHSignature, sig2: LSHSignature) -> float:
        """Pure: (sig1, sig2) → Jaccard similarity estimate.

        Args:
            sig1: First signature
            sig2: Second signature

        Returns:
            Estimated Jaccard similarity ∈ [0.0, 1.0]

        Invariant: Symmetric (similarity(A, B) == similarity(B, A)).
        """
        ...

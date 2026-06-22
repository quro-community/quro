"""MinHash LSH Implementation - Pure kernel (database-blind, file-blind).

@module quro.core.lsh.minhash
@intent Concrete implementation of LSHKernel protocol.
        Pure MinHash + banding algorithm with no side effects.
"""

import hashlib
import struct
from typing import List, Set, Tuple
import numpy as np

from types import LSHConfig, LSHSignature


class MinHashLSH:
    """MinHash LSH kernel - pure implementation.

    Invariants:
    - All methods are pure (no side effects)
    - Deterministic (same input → same output)
    - No I/O (no file, database, network access)
    - No logging (pure computation only)

    Time complexity: O(k*n) where k=num_hashes, n=|tokens|
    Space complexity: O(k) for signature storage
    """

    def __init__(self, config: LSHConfig):
        """Initialize MinHash LSH kernel.

        Args:
            config: LSH configuration (immutable)
        """
        self.config = config
        self.hash_functions = self._generate_hash_functions()
        # Pre-compute numpy arrays for vectorized operations
        self._a = np.array([a for a, _ in self.hash_functions], dtype=np.int64)
        self._b = np.array([b for _, b in self.hash_functions], dtype=np.int64)

    def _generate_hash_functions(self) -> List[Tuple[int, int]]:
        """Generate hash function parameters (a, b) for MinHash.

        Each hash function is: h(x) = (a*x + b) mod prime

        Returns:
            List of (a, b) tuples for each hash function

        Invariant: Deterministic (uses fixed seed=42).
        """
        prime = 2**31 - 1

        # Deterministic seed for reproducibility
        np.random.seed(42)
        hash_functions = []

        for _ in range(self.config.num_hashes):
            a = np.random.randint(1, prime)
            b = np.random.randint(0, prime)
            hash_functions.append((a, b))

        return hash_functions

    def compute_signature(self, tokens: Set[str]) -> LSHSignature:
        """Pure: tokens → LSH signature.

        Args:
            tokens: Set of tokens (words, n-grams, behavioral tags)

        Returns:
            LSHSignature with hash_values and bands

        Invariant: Same tokens always produce same signature.
        """
        if not tokens:
            # Empty token set → zero signature
            hash_values = np.zeros(self.config.num_hashes, dtype=np.uint32)
            bands = [0] * self.config.num_bands
            return LSHSignature(
                hash_values=hash_values,
                bands=bands,
                config=self.config
            )

        # Convert tokens to integer hashes
        token_hashes = [self._hash_token(token) for token in tokens]

        # Compute MinHash signature
        hash_values = self._compute_minhash(token_hashes)

        # Compute band hashes
        bands = self._compute_bands_from_signature(hash_values)

        return LSHSignature(
            hash_values=hash_values,
            bands=bands,
            config=self.config
        )

    def _hash_token(self, token: str) -> int:
        """Hash a token to an integer.

        Args:
            token: Token string

        Returns:
            Integer hash value (uint32)

        Invariant: Deterministic (SHA256-based).
        """
        hash_bytes = hashlib.sha256(token.encode("utf-8")).digest()[:4]
        return struct.unpack("I", hash_bytes)[0]

    def _compute_minhash(self, token_hashes: List[int]) -> np.ndarray:
        """Compute MinHash signature from token hashes.

        Args:
            token_hashes: List of integer token hashes

        Returns:
            MinHash signature as numpy array of shape (num_hashes,)

        Invariant: Pure computation (no side effects).
        """
        if not token_hashes:
            return np.full(
                self.config.num_hashes,
                np.iinfo(np.uint32).max,
                dtype=np.uint32
            )

        prime = 2**31 - 1

        # Reshape token hashes to (N, 1) to broadcast over Hash functions (1, K)
        t_array = np.array(token_hashes, dtype=np.int64)[:, np.newaxis]

        # Calculate all hashes across all tokens and hash functions: (N, K)
        hashes = (t_array * self._a + self._b) % prime

        # To get the final Minhash signature, take the min along the token axis
        return np.min(hashes, axis=0).astype(np.uint32)

    def _compute_bands_from_signature(self, signature: np.ndarray) -> List[int]:
        """Compute band hashes from MinHash signature.

        Args:
            signature: MinHash signature

        Returns:
            List of band hashes (one per band)

        Invariant: Pure computation (no side effects).
        """
        band_hashes = []

        for band_idx in range(self.config.num_bands):
            start = band_idx * self.config.rows_per_band
            end = start + self.config.rows_per_band

            # Extract band rows
            band_rows = signature[start:end]

            # Hash the band
            band_hash = self._hash_band(band_rows)
            band_hashes.append(band_hash)

        return band_hashes

    def _hash_band(self, band_rows: np.ndarray) -> int:
        """Hash a band (multiple rows) to a single integer.

        Args:
            band_rows: Array of hash values in the band

        Returns:
            Band hash as integer (uint64)

        Invariant: Deterministic (SHA256-based).
        """
        band_bytes = band_rows.tobytes()
        hash_bytes = hashlib.sha256(band_bytes).digest()[:8]
        return struct.unpack("Q", hash_bytes)[0]

    def compute_similarity(self, sig1: LSHSignature, sig2: LSHSignature) -> float:
        """Pure: (sig1, sig2) → Jaccard similarity estimate.

        Args:
            sig1: First signature
            sig2: Second signature

        Returns:
            Estimated Jaccard similarity ∈ [0.0, 1.0]

        Invariant: Symmetric (similarity(A, B) == similarity(B, A)).
        """
        if len(sig1.hash_values) != len(sig2.hash_values):
            raise ValueError("Signatures must have same length")

        # Count matching hash values
        matches = np.sum(sig1.hash_values == sig2.hash_values)

        # Jaccard similarity ≈ fraction of matching hashes
        return float(matches) / len(sig1.hash_values)

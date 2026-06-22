"""LSH Types - Immutable data structures for LSH kernel.

@module quro.core.lsh.types
@intent Define pure data contracts for LSH inputs/outputs.
"""

from dataclasses import dataclass
from typing import List
import numpy as np


@dataclass(frozen=True)
class LSHConfig:
    """LSH configuration parameters (immutable).

    Invariants:
    - num_hashes must be divisible by num_bands
    - rows_per_band = num_hashes / num_bands
    - threshold ∈ [0.0, 1.0]
    """
    num_hashes: int = 128
    num_bands: int = 16
    threshold: float = 0.3

    @property
    def rows_per_band(self) -> int:
        """Computed property: rows per band."""
        return self.num_hashes // self.num_bands

    def __post_init__(self):
        """Validate configuration invariants."""
        if self.num_hashes % self.num_bands != 0:
            raise ValueError(
                f"num_hashes ({self.num_hashes}) must be divisible by "
                f"num_bands ({self.num_bands})"
            )

        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(
                f"threshold ({self.threshold}) must be in [0.0, 1.0]"
            )


@dataclass(frozen=True)
class LSHSignature:
    """MinHash signature output (immutable).

    Pure data: result of MinHash computation.
    """
    hash_values: np.ndarray  # Shape: (num_hashes,), dtype: uint32
    bands: List[int]  # Band hashes (one per band)
    config: LSHConfig  # Configuration used to generate this signature

    def __post_init__(self):
        """Validate signature invariants."""
        if len(self.hash_values) != self.config.num_hashes:
            raise ValueError(
                f"hash_values length ({len(self.hash_values)}) must match "
                f"config.num_hashes ({self.config.num_hashes})"
            )

        if len(self.bands) != self.config.num_bands:
            raise ValueError(
                f"bands length ({len(self.bands)}) must match "
                f"config.num_bands ({self.config.num_bands})"
            )

    def to_bytes(self) -> bytes:
        """Serialize signature to bytes for storage."""
        return self.hash_values.tobytes()

    @staticmethod
    def from_bytes(signature_bytes: bytes, config: LSHConfig) -> "LSHSignature":
        """Deserialize signature from bytes."""
        hash_values = np.frombuffer(signature_bytes, dtype=np.uint32)

        # Recompute bands (we don't store them separately)
        from minhash import MinHashLSH
        engine = MinHashLSH(config)
        bands = engine._compute_bands_from_signature(hash_values)

        return LSHSignature(
            hash_values=hash_values,
            bands=bands,
            config=config
        )

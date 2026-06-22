"""Manifold Adapter Types - Immutable data structures for manifold operations.

@module quro.adapters.manifold.types
@intent Define pure data contracts for manifold I/O operations.
"""

from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass(frozen=True)
class ManifoldNode:
    """Pure data: manifold node record (immutable).

    Represents a symbol's position in the semantic manifold with LSH fingerprint.
    """
    symbol_uid: str
    lsh_bands: Tuple[int, ...]
    manifold_x: float = 0.0
    manifold_y: float = 0.0
    behavioral_tags: Tuple[str, ...] = ()
    last_convergence: str = ""
    updated_at: float = 0.0


@dataclass(frozen=True)
class DriftResult:
    """Pure data: drift detection result (immutable).

    Represents the result of comparing old and new LSH fingerprints.
    """
    symbol_uid: str
    drift: float
    is_stable: bool
    old_lsh: Tuple[int, ...]
    new_lsh: Tuple[int, ...]
    threshold: float
    detected_at: float = 0.0


@dataclass(frozen=True)
class NodeInsertRequest:
    """Pure data: node insert request (immutable).

    Request to insert or update a manifold node.
    """
    symbol_uid: str
    lsh_bands: Tuple[int, ...]
    manifold_x: float = 0.0
    manifold_y: float = 0.0
    behavioral_tags: Tuple[str, ...] = ()
    last_convergence: str = ""

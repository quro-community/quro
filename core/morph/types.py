"""Morph Types - Immutable data structures for manifold analysis.

@module quro.core.morph.types
@intent Define pure data contracts for drift detection inputs/outputs.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class ManifoldNode:
    """Pure data: manifold state snapshot (immutable).

    Represents a symbol's position in the semantic manifold.
    """
    symbol_uid: str
    lsh_bands: List[int]  # LSH band hashes
    manifold_x: float  # 2D projection coordinate
    manifold_y: float  # 2D projection coordinate
    behavioral_tags: List[str]  # Semantic tags
    last_convergence: str  # Checksum of last stable state
    updated_at: float  # Unix timestamp


@dataclass(frozen=True)
class DriftResult:
    """Pure data: drift detection output (immutable).

    Result of comparing old and new LSH signatures.
    """
    symbol_uid: str
    drift: float  # Jaccard distance ∈ [0.0, 1.0]
    is_stable: bool  # True if drift < threshold
    old_lsh: List[int]  # Previous LSH bands
    new_lsh: List[int]  # Current LSH bands
    threshold: float  # Drift threshold used


@dataclass(frozen=True)
class TopologicalHole:
    """Pure data: low-density region in manifold (immutable).

    Represents a "hole" in the semantic manifold where logic is sparse.
    """
    center_x: float
    center_y: float
    density: float  # Relative density (0.0 = empty, 1.0 = average)
    grid_index: tuple  # (xi, yi) grid cell index


@dataclass(frozen=True)
class BettiResult:
    """Pure data: Betti number computation result (immutable).

    Topological invariant: β₁ = number of 1-dimensional holes (cycles).
    """
    betti_1: int  # First Betti number (cycle count)
    num_nodes: int  # Number of nodes in graph
    num_edges: int  # Number of edges in graph
    num_components: int  # Number of connected components

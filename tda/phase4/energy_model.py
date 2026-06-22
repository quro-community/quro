"""Energy Model — Utility Functions

@module quro.tda.phase4.energy_model
@intent Compute physics-based utility values for TDA navigation.

IMPORTANT: All functions in this module are HINTS only, not decision signals.
Phase 4 v2 uses intent alignment as the sole decision axis.
Energy values are used for ranking tie-breaking and transparency only.

DEPRECATED: compute_transition_energy() — no longer used in Phase 4 v2.
The A* cost model has been replaced by Beam Search exploration.
"""

import logging
import math
import warnings
from typing import List, Optional

import numpy as np


# Design 87 Parameters (Production-Ready)
LAMBDA_UPHILL = 0.40        # Potential gradient (uphill penalty)
LAMBDA_ALIGN = 0.35         # Direction alignment
LAMBDA_FRICTION = 0.25      # Friction resistance
LAMBDA_DISTANCE = 0.15      # Manifold distance
LAMBDA_INTENT = 0.55        # Intent force (increased from 0.4)
LAMBDA_CENTRALITY_BOOST = 0.20  # Attractor creation
LAMBDA_TAU_SHARPNESS = 0.30     # Noise pruning


def compute_vector_alignment(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Alignment score in [0, 1] (1 = perfectly aligned)
    """
    if not vec1 or not vec2:
        return 0.0

    arr1 = np.array(vec1)
    arr2 = np.array(vec2)

    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    # Cosine similarity: [-1, 1] → [0, 1]
    cos_sim = np.dot(arr1, arr2) / (norm1 * norm2)
    return (cos_sim + 1.0) / 2.0


def compute_intent_alignment(
    direction: List[float],
    intent_vector: Optional[List[float]]
) -> float:
    """Compute alignment between symbol direction and user intent.

    Note: Direction is 3-dim (manifold), intent is 128-dim (semantic).
    We use the first 3 dimensions of intent for alignment.

    Args:
        direction: Symbol's field direction vector (3-dim)
        intent_vector: User intent vector (128-dim)

    Returns:
        Intent alignment score in [0, 1]
    """
    if intent_vector is None:
        return 1.0  # No intent penalty

    # Project intent to 3D manifold space (use first 3 dimensions)
    intent_3d = intent_vector[:3] if len(intent_vector) >= 3 else intent_vector

    return compute_vector_alignment(direction, intent_3d)


def manifold_distance(pos1: List[float], pos2: List[float]) -> float:
    """Compute Euclidean distance on manifold.

    Args:
        pos1: First position (3D manifold coordinates)
        pos2: Second position (3D manifold coordinates)

    Returns:
        Euclidean distance
    """
    arr1 = np.array(pos1)
    arr2 = np.array(pos2)
    return float(np.linalg.norm(arr1 - arr2))


def normalize_distance(distance: float, max_distance: float = 10.0) -> float:
    """Normalize distance using log transform (Design 87).

    Formula: log(1 + distance) / log(1 + max_distance)

    Args:
        distance: Raw manifold distance
        max_distance: Maximum expected distance (default: 10.0)

    Returns:
        Normalized distance in [0, 1]
    """
    return math.log1p(distance) / math.log1p(max_distance)


def normalize_centrality(centrality: float, max_centrality: float = 1.0) -> float:
    """Normalize centrality using log transform (Design 87).

    Prevents main/entry points from becoming black holes.

    Formula: log(1 + centrality) / log(1 + max_centrality)

    Args:
        centrality: Raw centrality score
        max_centrality: Maximum expected centrality (default: 1.0)

    Returns:
        Normalized centrality in [0, 1]
    """
    return math.log1p(centrality) / math.log1p(max_centrality)


def normalize_friction(friction: float) -> float:
    """Normalize friction using sigmoid (Design 87).

    Formula: 1 / (1 + exp(-3 * (friction - 0.5)))

    Separates middle range for better discrimination.

    Args:
        friction: Raw friction coefficient [0, 1]

    Returns:
        Normalized friction in [0, 1]
    """
    return 1.0 / (1.0 + math.exp(-3.0 * (friction - 0.5)))


def compute_transition_energy(
    src_state: dict,
    dst_state: dict,
    intent_vector: Optional[List[float]] = None,
    w_alignment: float = LAMBDA_ALIGN,
    w_friction: float = LAMBDA_FRICTION,
    w_distance: float = LAMBDA_DISTANCE,
    w_intent: float = LAMBDA_INTENT,
    w_uphill: float = LAMBDA_UPHILL,
    w_centrality_boost: float = LAMBDA_CENTRALITY_BOOST,
    w_tau_sharpness: float = LAMBDA_TAU_SHARPNESS,
) -> float:
    """DEPRECATED: Phase 4 v2 uses Beam Search with intent alignment.

    This function is kept for backward compatibility with the legacy A* planner.
    Use ExplorationEngine.explore() instead.

    Compute transition energy (edge cost) for A* pathfinding.

    Enhanced Formula (Design 87):
    E_transition = λ_uphill · max(0, ΔU)
                 + λ_align · (1 - alignment)
                 + λ_friction · friction_norm
                 + λ_distance · distance_norm
                 - λ_intent · intent_force

    Structural amplification:
    E_transition *= (1 + λ_tau_sharpness · (1 - tau_norm))
    E_transition /= (1 + λ_centrality_boost · centrality_norm)

    Args:
        src_state: Source symbol state with keys:
            - direction: Field direction vector
            - position: Manifold position (3D)
            - energy: Total energy (potential)
            - friction: Energy-adjusted friction
        dst_state: Destination symbol state with keys:
            - direction: Field direction vector
            - position: Manifold position (3D)
            - energy: Total energy (potential)
            - friction: Energy-adjusted friction
        intent_vector: User intent vector (128-dim), optional
        w_alignment: Weight for direction alignment term
        w_friction: Weight for friction term
        w_distance: Weight for distance term
        w_intent: Weight for intent force term
        w_uphill: Weight for uphill penalty (Design 87)
        w_centrality_boost: Weight for centrality boost (Design 87)
        w_tau_sharpness: Weight for tau sharpness (Design 87)

    Returns:
        Transition energy (lower = better, non-negative)
    """
    # 1. Potential difference (Design 87 - KEY INNOVATION)
    src_energy = src_state.get("energy", 0.0)
    dst_energy = dst_state.get("energy", 0.0)
    delta_U = dst_energy - src_energy
    uphill_penalty = w_uphill * max(0.0, delta_U)

    # 2. Direction alignment (semantic coherence)
    alignment = compute_vector_alignment(
        src_state["direction"],
        dst_state["direction"]
    )

    # 3. Friction (resistance) - normalized
    friction_raw = dst_state["friction"]
    friction_norm = normalize_friction(friction_raw)

    # 4. Manifold distance (geometric cost) - normalized
    distance_raw = manifold_distance(
        src_state["position"],
        dst_state["position"]
    )
    distance_norm = normalize_distance(distance_raw, max_distance=10.0)

    # 5. Intent force (Design 87 - enhanced from bias to force)
    intent_alignment = compute_intent_alignment(
        dst_state["direction"],
        intent_vector
    )

    # Base energy
    E = (
        uphill_penalty +
        w_alignment * (1.0 - alignment) +
        w_friction * friction_norm +
        w_distance * distance_norm -
        w_intent * intent_alignment
    )

    # Structural amplification (Design 87)
    # High tau (low friction) → lower cost (noise pruning)
    tau_norm = 1.0 - friction_raw  # tau = 1 - friction
    E *= (1.0 + w_tau_sharpness * (1.0 - tau_norm))

    # High centrality → lower cost (attractor creation)
    # Note: centrality not in state yet, will be added in Phase 2
    # For now, skip centrality boost
    # centrality_norm = normalize_centrality(dst_state.get("centrality", 0.5))
    # E /= (1.0 + w_centrality_boost * centrality_norm)

    return max(0.0, E)  # Ensure non-negative

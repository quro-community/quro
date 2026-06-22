"""Pass 4: Field Initialization (Physics-Based Recalibration)

@module quro.tda.phase2_5.pass4_field_initialization
@intent Initialize energy field using non-linear potential functions to create
        strong gradients and natural attractors. Replaces linear normalization
        with log-based transforms and structural gravity injection.

        Energy formula (Design 85):
        E_total(s) = E_potential(s) + G_structural(s) + H_entropy(s)

        where:
        - E_potential: Non-linear potential from metrics (log transforms)
        - G_structural: Injected gravity based on topology
        - H_entropy: Information entropy amplification

        Field vector:
        F(x) = -∇E(x) = sum over neighbors of: (E_neighbor - E_self) * direction * edge_weight
"""

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


# Energy formula coefficients (Design 85)
W_CENTRALITY = 0.4      # Centrality weight in potential
W_FREQUENCY = 0.3       # Frequency weight in potential
W_STABILITY = 0.3       # Stability weight in potential
ALPHA_CENTRALITY = 1000 # Centrality amplification factor
BETA_FREQUENCY = 1      # Frequency amplification factor
GAMMA_STABILITY = 3     # Stability exponent
W_IN_DEGREE = 0.5       # In-degree weight in structural gravity
W_DIVERSITY = 0.7       # Caller diversity weight in structural gravity
W_ENTROPY = 0.3         # Entropy weight


@dataclass(frozen=True)
class OfflineEnergyState:
    """Offline-computed energy state for a symbol (Physics-Based Model).

    Attributes:
        symbol: Symbol ID
        potential: Non-linear potential energy (log-based)
        structural_gravity: Injected gravity from topology
        entropy_bonus: Information entropy amplification
        total: Total energy (potential + gravity + entropy)
        friction: Friction coefficient [0, 1]
        mass: Mass (centrality) [0, 1]
        field_magnitude: Field vector magnitude
        field_direction: Field vector direction (3D)
        field_role: Emergent role (attractor, repeller, saddle_point)
    """
    symbol: str
    potential: float
    structural_gravity: float
    entropy_bonus: float
    total: float
    friction: float
    mass: float
    field_magnitude: float
    field_direction: Tuple[float, float, float]
    field_role: str


def compute_potential_energy(
    centrality: float,
    frequency: float,
    tau_persistence: float,
) -> float:
    """Compute non-linear potential energy using log transforms.

    Formula (Design 85):
    E_potential = w_c · log(1 + α·centrality)
                + w_f · log(1 + β·frequency)
                + w_τ · (tau)^γ

    Args:
        centrality: Centrality score (from gravity_score)
        frequency: Frequency score (from heat)
        tau_persistence: Stability score (from friction inverse)

    Returns:
        Potential energy ∈ [0, ~5]
    """
    # Non-linear transforms
    E_c = W_CENTRALITY * math.log1p(centrality * ALPHA_CENTRALITY)
    E_f = W_FREQUENCY * math.log1p(frequency * BETA_FREQUENCY)
    E_t = W_STABILITY * (tau_persistence ** GAMMA_STABILITY)

    return round(E_c + E_f + E_t, 4)


def compute_structural_gravity(
    in_degree: int,
    incoming_edges: List[Tuple[str, float]],
) -> float:
    """Compute structural gravity from topology.

    Formula (Design 85):
    G_structural = α · log(1 + in_degree)
                 + β · log(1 + caller_diversity)

    where caller_diversity = entropy(incoming_source_distribution)

    Args:
        in_degree: Number of incoming edges
        incoming_edges: List of (source, weight) tuples

    Returns:
        Structural gravity ∈ [0, ~3]
    """
    # In-degree component
    G_in = W_IN_DEGREE * math.log1p(in_degree)

    # Caller diversity component
    if not incoming_edges:
        G_div = 0.0
    else:
        # Compute entropy of source distribution
        total_weight = sum(w for _, w in incoming_edges)
        if total_weight > 0:
            probs = [w / total_weight for _, w in incoming_edges]
            entropy = -sum(p * math.log(p + 1e-9) for p in probs)
            max_entropy = math.log(len(incoming_edges)) if len(incoming_edges) > 1 else 1.0
            normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0
            G_div = W_DIVERSITY * normalized_entropy
        else:
            G_div = 0.0

    return round(G_in + G_div, 4)


def compute_entropy_bonus(
    category_coupling: Dict[str, float]
) -> float:
    """Compute entropy bonus from category distribution.

    Formula (Design 85):
    H_entropy = w_H · entropy(category_coupling)

    Low entropy → single responsibility → stable → attractor
    High entropy → multiple responsibilities → unstable → saddle

    Args:
        category_coupling: Dict mapping category → coupling strength

    Returns:
        Entropy bonus ∈ [0, ~2]
    """
    if not category_coupling:
        return 0.0

    # Normalize to probability distribution
    total = sum(category_coupling.values())
    if total == 0:
        return 0.0

    probs = [v / total for v in category_coupling.values()]

    # Shannon entropy
    entropy = -sum(p * math.log(p + 1e-9) for p in probs)

    # Weight and return
    return round(W_ENTROPY * entropy, 4)


def apply_energy_soft_cap(energy: float, cap: float = 10.0) -> float:
    """Apply soft cap to prevent energy explosion.

    Formula: cap · tanh(E / cap)

    This creates a sigmoid-like soft limit that:
    - Preserves gradient structure for E < cap
    - Asymptotically approaches cap for E >> cap
    - Prevents scorer weight overflow

    Args:
        energy: Raw energy value
        cap: Soft cap value (default: 10.0)

    Returns:
        Capped energy ∈ [0, cap]
    """
    return cap * math.tanh(energy / cap)


def compute_energy_adjusted_friction(
    base_friction: float,
    total_energy: float,
    energy_weight: float = 0.3,
) -> float:
    """Adjust friction based on energy (gravitational acceleration effect).

    Logic:
    - High-energy nodes (e.g., main) → smoother spacetime → lower friction
    - Low-energy nodes (e.g., transient) → muddy terrain → higher friction

    Formula:
    friction_adjusted = base_friction · (1 - energy_weight · normalized_energy)

    Purpose: Creates gravitational acceleration - agents are pulled faster
    toward cores, but become cautious at edges.

    Args:
        base_friction: Base friction from complexity
        total_energy: Total energy of the node
        energy_weight: Weight of energy adjustment (default: 0.3)

    Returns:
        Adjusted friction ∈ [0, 1]
    """
    # Normalize energy to [0, 1] assuming max energy ~10
    normalized_energy = min(1.0, total_energy / 10.0)

    # Reduce friction for high-energy nodes
    adjusted = base_friction * (1.0 - energy_weight * normalized_energy)

    return max(0.0, min(1.0, adjusted))


def compute_offline_energy(
    gravity: float,
    heat: float,
    friction: float,
) -> Tuple[float, float, float]:
    """Compute offline energy from static metrics (DEPRECATED - kept for compatibility).

    This function is deprecated in favor of compute_potential_energy,
    compute_structural_gravity, and compute_entropy_bonus.

    Formula:
    - Potential = α * (1 - gravity)  # Deep well = low potential
    - Kinetic = β * heat             # High heat = high kinetic
    - Total = Potential + Kinetic

    Args:
        gravity: Gravity score [0, 1]
        heat: Heat score [0, 1]
        friction: Friction coefficient [0, 1]

    Returns:
        Tuple of (potential, kinetic, total)
    """
    # Legacy formula - kept for backward compatibility
    potential = 0.4 * (1.0 - gravity)
    kinetic = 0.4 * heat
    total = potential + kinetic

    return (
        round(potential, 4),
        round(kinetic, 4),
        round(total, 4),
    )


def compute_field_vector(
    symbol_id: str,
    energy_map: Dict[str, float],
    position_map: Dict[str, Tuple[float, float, float]],
    edge_weights: Dict[str, float],
    adapter,
) -> Tuple[float, Tuple[float, float, float]]:
    """Compute field vector via gradient descent.

    F(x) = -∇E(x) = sum over neighbors of:
        (E_neighbor - E_self) * direction * edge_weight

    Args:
        symbol_id: Symbol ID
        energy_map: Map of symbol → total energy
        position_map: Map of symbol → manifold position (3D)
        edge_weights: Map of edge_key → weight
        adapter: Registry adapter

    Returns:
        Tuple of (magnitude, direction)
    """
    symbol_energy = energy_map.get(symbol_id, 0.0)
    symbol_position = position_map.get(symbol_id, (0.0, 0.0, 0.0))

    # Get neighbors
    edges = adapter.get_edges_from(symbol_id)

    if not edges:
        return (0.0, (0.0, 0.0, 0.0))

    # Accumulate gradient
    gradient = [0.0, 0.0, 0.0]

    for edge in edges:
        neighbor_id = edge.dst
        neighbor_energy = energy_map.get(neighbor_id, 0.0)
        neighbor_position = position_map.get(neighbor_id, (0.0, 0.0, 0.0))

        # Energy difference
        delta_E = neighbor_energy - symbol_energy

        # Direction vector (normalized)
        direction = [
            neighbor_position[0] - symbol_position[0],
            neighbor_position[1] - symbol_position[1],
            neighbor_position[2] - symbol_position[2],
        ]

        # Normalize direction
        norm = math.sqrt(sum(d**2 for d in direction))
        if norm > 0:
            direction = [d / norm for d in direction]

        # Edge weight
        edge_key = f"{symbol_id}→{neighbor_id}"
        weight = edge_weights.get(edge_key, 0.5)

        # Accumulate gradient
        for i in range(3):
            gradient[i] += delta_E * direction[i] * weight

    # Compute magnitude
    magnitude = math.sqrt(sum(g**2 for g in gradient))

    # Normalize direction
    if magnitude > 0:
        direction_normalized = tuple(g / magnitude for g in gradient)
    else:
        direction_normalized = (0.0, 0.0, 0.0)

    return (round(magnitude, 4), direction_normalized)


def classify_field_role(
    total_energy: float,
    field_magnitude: float,
    friction: float,
    out_degree: int = 0,
    in_degree: int = 0,
    tags: set = None,
) -> str:
    """Classify field role based on physics-based energy model with attractor bias.

    Classification based on total energy and field magnitude:

    Attractor: High energy + low field magnitude + terminal characteristics
      - High total energy (>5.0): deep potential well
      - Low field magnitude (<2.0): stable basin
      - Low friction (<0.3): easy to reach
      - OR: Terminal node (out_degree==0, in_degree>0) with persistence tags

    Repeller: Low energy + high field magnitude
      - Low total energy (<1.0): shallow potential
      - High field magnitude (>5.0): strong gradient away
      - High friction (>0.5): hard to traverse

    Saddle Point: Medium energy + medium field
      - Medium total energy (2.0-5.0): transitional
      - Medium field magnitude (2.0-5.0): moderate gradient

    Args:
        total_energy: Total energy (potential + gravity + entropy)
        field_magnitude: Field magnitude
        friction: Friction coefficient
        out_degree: Number of outgoing edges (for terminal detection)
        in_degree: Number of incoming edges (for terminal detection)
        tags: Set of behavioral tags (for persistence detection)

    Returns:
        Field role string
    """
    tags = tags or set()

    # Terminal tags that indicate persistence/completion
    terminal_tags = {
        "database", "serialize", "snapshot", "persist",
        "commit", "write", "save", "store", "flush", "finalize"
    }

    # Check for terminal node characteristics
    is_terminal = out_degree == 0 and in_degree > 0
    has_persistence_tags = bool(terminal_tags & tags)

    # Attractor: high energy, stable basin, OR terminal with persistence
    if total_energy > 5.0 and field_magnitude < 2.0 and friction < 0.3:
        return "attractor"

    # Attractor bias: terminal nodes with persistence tags
    if is_terminal and has_persistence_tags and total_energy > 2.0:
        return "attractor"

    # Repeller: low energy, strong gradient
    if total_energy < 1.0 and field_magnitude > 5.0:
        return "repeller"

    # Saddle point: medium energy, moderate gradient
    if 2.0 <= total_energy <= 5.0 and 2.0 <= field_magnitude <= 5.0:
        return "saddle_point"

    # Not a critical point
    return "not_critical_point"


def initialize_field(
    workspace_root: Path,
    git_heat_path: Path,
    structural_metrics_path: Path,
    edge_weights_path: Path,
    manifold_states_path: Path,
    output_path: Path,
) -> Dict[str, OfflineEnergyState]:
    """Initialize energy field using physics-based potential model (Design 85).

    Args:
        workspace_root: Workspace root
        git_heat_path: Path to symbol_heat.json
        structural_metrics_path: Path to structural_metrics.json
        edge_weights_path: Path to edge_weights.json
        manifold_states_path: Path to manifold_states.jsonl (for positions)
        output_path: Output path for offline_energy.json

    Returns:
        Dict mapping symbol → OfflineEnergyState
    """
    logger.info("Initializing energy field using physics-based model (Design 85)")

    # Load git heat
    with open(git_heat_path) as f:
        git_heat_data = json.load(f)
    heat_map = {
        symbol: data["heat_score"]
        for symbol, data in git_heat_data["metrics"].items()
    }

    # Load structural metrics
    with open(structural_metrics_path) as f:
        structural_data = json.load(f)
    gravity_map = {
        symbol: data["gravity_score"]
        for symbol, data in structural_data["metrics"].items()
    }
    friction_map = {
        symbol: data["friction"]
        for symbol, data in structural_data["metrics"].items()
    }
    mass_map = {
        symbol: data["mass"]
        for symbol, data in structural_data["metrics"].items()
    }
    in_degree_map = {
        symbol: data["in_degree"]
        for symbol, data in structural_data["metrics"].items()
    }

    # Load edge weights
    with open(edge_weights_path) as f:
        edge_weights_data = json.load(f)
    edge_weights = {
        edge_key: data["weight"]
        for edge_key, data in edge_weights_data["weights"].items()
    }

    # Load manifold positions
    position_map: Dict[str, Tuple[float, float, float]] = {}
    with open(manifold_states_path) as f:
        for line in f:
            if line.strip():
                state = json.loads(line)
                symbol = state["symbol"]
                pos_data = state["manifold_position"]

                # Extract embedding (it's a dict with "embedding" key)
                if isinstance(pos_data, dict) and "embedding" in pos_data:
                    embedding = pos_data["embedding"]
                    # Take first 3 dimensions
                    position_map[symbol] = (
                        float(embedding[0]) if len(embedding) > 0 else 0.0,
                        float(embedding[1]) if len(embedding) > 1 else 0.0,
                        float(embedding[2]) if len(embedding) > 2 else 0.0,
                    )
                else:
                    # Fallback: assume it's already a list
                    position_map[symbol] = (
                        float(pos_data[0]) if len(pos_data) > 0 else 0.0,
                        float(pos_data[1]) if len(pos_data) > 1 else 0.0,
                        float(pos_data[2]) if len(pos_data) > 2 else 0.0,
                    )

    logger.info("Loaded metrics for %d symbols", len(position_map))

    # Load registry adapter for incoming edges and category coupling
    from index_builder.adapters.sqlite import SQLiteRegistryAdapter
    registry_db_path = workspace_root / ".quro_context" / "registry.db"
    adapter = SQLiteRegistryAdapter(db_path=registry_db_path)

    # Build incoming edges map
    incoming_edges_map: Dict[str, List[Tuple[str, float]]] = {
        symbol: [] for symbol in position_map.keys()
    }

    for symbol in position_map.keys():
        out_edges = adapter.get_edges_from(symbol)
        for edge in out_edges:
            target_id = edge.dst
            if target_id in incoming_edges_map:
                edge_key = f"{symbol}→{target_id}"
                weight = edge_weights.get(edge_key, 0.5)
                incoming_edges_map[target_id].append((symbol, weight))

    # Build category coupling map (from registry node metadata)
    category_coupling_map: Dict[str, Dict[str, float]] = {}
    for symbol in position_map.keys():
        node = adapter.get_node(symbol)
        if node and node.metadata:
            # Extract category coupling from metadata
            # Assuming metadata has "categories" or similar field
            categories = node.metadata.get("categories", {})
            if isinstance(categories, dict):
                category_coupling_map[symbol] = categories
            else:
                category_coupling_map[symbol] = {}
        else:
            category_coupling_map[symbol] = {}

    # Compute energy for all symbols using physics-based model
    energy_map: Dict[str, float] = {}
    for symbol in position_map.keys():
        centrality = gravity_map.get(symbol, 0.5)
        frequency = heat_map.get(symbol, 0.0)
        friction = friction_map.get(symbol, 0.5)
        tau_persistence = 1.0 - friction  # Inverse of friction
        in_degree = in_degree_map.get(symbol, 0)
        incoming_edges = incoming_edges_map.get(symbol, [])
        category_coupling = category_coupling_map.get(symbol, {})

        # Compute components
        potential = compute_potential_energy(centrality, frequency, tau_persistence)
        structural_gravity = compute_structural_gravity(in_degree, incoming_edges)
        entropy_bonus = compute_entropy_bonus(category_coupling)

        # Total energy with soft cap to prevent explosion
        total_raw = potential + structural_gravity + entropy_bonus
        total = apply_energy_soft_cap(total_raw, cap=10.0)

        energy_map[symbol] = total

    logger.info("Computed physics-based energy for %d symbols", len(energy_map))

    # Compute field vectors and classify roles
    energy_states: Dict[str, OfflineEnergyState] = {}

    for symbol in position_map.keys():
        centrality = gravity_map.get(symbol, 0.5)
        frequency = heat_map.get(symbol, 0.0)
        friction = friction_map.get(symbol, 0.5)
        tau_persistence = 1.0 - friction
        mass = mass_map.get(symbol, 0.0)
        in_degree = in_degree_map.get(symbol, 0)
        incoming_edges = incoming_edges_map.get(symbol, [])
        category_coupling = category_coupling_map.get(symbol, {})

        # Compute energy components
        potential = compute_potential_energy(centrality, frequency, tau_persistence)
        structural_gravity = compute_structural_gravity(in_degree, incoming_edges)
        entropy_bonus = compute_entropy_bonus(category_coupling)

        # Total energy with soft cap
        total_raw = potential + structural_gravity + entropy_bonus
        total = apply_energy_soft_cap(total_raw, cap=10.0)

        # Adjust friction based on energy (gravitational acceleration)
        friction_adjusted = compute_energy_adjusted_friction(friction, total, energy_weight=0.3)

        # Compute field vector
        field_magnitude, field_direction = compute_field_vector(
            symbol, energy_map, position_map, edge_weights, adapter
        )

        # Query tags for attractor bias
        node = adapter.get_node(symbol)
        tags = set()
        if node and node.metadata:
            tags = set(node.metadata.get("tags", []))

        # Classify field role using physics-based criteria with attractor bias
        field_role = classify_field_role(
            total, field_magnitude, friction_adjusted,
            out_degree=len(list(adapter.get_edges_from(symbol))),
            in_degree=in_degree,
            tags=tags
        )

        energy_states[symbol] = OfflineEnergyState(
            symbol=symbol,
            potential=potential,
            structural_gravity=structural_gravity,
            entropy_bonus=entropy_bonus,
            total=total,
            friction=friction_adjusted,
            mass=mass,
            field_magnitude=field_magnitude,
            field_direction=field_direction,
            field_role=field_role,
        )

    # Statistics
    attractors = sum(1 for s in energy_states.values() if s.field_role == "attractor")
    repellers = sum(1 for s in energy_states.values() if s.field_role == "repeller")
    saddle_points = sum(1 for s in energy_states.values() if s.field_role == "saddle_point")

    # Energy distribution statistics
    energies = [s.total for s in energy_states.values()]
    min_energy = min(energies) if energies else 0.0
    max_energy = max(energies) if energies else 0.0
    avg_energy = sum(energies) / len(energies) if energies else 0.0

    logger.info(
        "Field initialized: %d symbols (attractors: %d, repellers: %d, saddle_points: %d)",
        len(energy_states), attractors, repellers, saddle_points,
    )
    logger.info(
        "Energy distribution: min=%.2f, max=%.2f, avg=%.2f (expected range: [0.1, 8.0])",
        min_energy, max_energy, avg_energy,
    )

    # Write to file
    output_data = {
        "metadata": {
            "source": "physics_based_model",
            "design": "Design 85 - Field Recalibration",
            "total_symbols": len(energy_states),
            "attractor_count": attractors,
            "repeller_count": repellers,
            "saddle_point_count": saddle_points,
            "energy_range": {
                "min": round(min_energy, 4),
                "max": round(max_energy, 4),
                "avg": round(avg_energy, 4),
            },
            "coefficients": {
                "w_centrality": W_CENTRALITY,
                "w_frequency": W_FREQUENCY,
                "w_stability": W_STABILITY,
                "alpha_centrality": ALPHA_CENTRALITY,
                "beta_frequency": BETA_FREQUENCY,
                "gamma_stability": GAMMA_STABILITY,
                "w_in_degree": W_IN_DEGREE,
                "w_diversity": W_DIVERSITY,
                "w_entropy": W_ENTROPY,
            },
        },
        "states": {
            symbol: {
                "potential": s.potential,
                "structural_gravity": s.structural_gravity,
                "entropy_bonus": s.entropy_bonus,
                "total": s.total,
                "friction": s.friction,
                "mass": s.mass,
                "field_magnitude": s.field_magnitude,
                "field_direction": list(s.field_direction),
                "field_role": s.field_role,
            }
            for symbol, s in energy_states.items()
        }
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info("Wrote physics-based energy states to %s", output_path)
    return energy_states

---
type: Guide
title: Physics & Mathematics in TDA: Theory and Problem Mapping
description: Maps the mathematical and physical theories used in the TDA system to specific code navigation problems.
tags: [tda, physics, mathematics, theory, guide]
---

# Physics & Mathematics in TDA: Theory and Problem Mapping

> This document maps the mathematical and physical theories used in the TDA system to the specific problems they solve in code navigation.

---

## Table of Contents

1. [Overview: Why Physics/Math?](#1-overview-why-physicsmath)
2. [Differential Geometry](#2-differential-geometry)
3. [Dynamical Systems Theory](#3-dynamical-systems-theory)
4. [Statistical Physics / Energy-Based Models](#4-statistical-physics--energy-based-models)
5. [Classical Mechanics](#5-classical-mechanics)
6. [Information Theory](#6-information-theory)
7. [Graph Theory & Network Science](#7-graph-theory--network-science)
8. [Algebraic Topology](#8-algebraic-topology)
9. [Control Theory & Optimal Pathfinding](#9-control-theory--optimal-pathfinding)
10. [Probability & Statistics](#10-probability--statistics)
11. [Calculus / Real Analysis](#11-calculus--real-analysis)
12. [Summary: Theory → Problem Matrix](#12-summary-theory--problem-matrix)

---

## 1. Overview: Why Physics/Math?

The TDA system maps a **discrete, symbolic code graph** into a **continuous geometric space** where physics-like metaphors enable intuitive navigation. The key insight: code has structure that behaves like physical systems.

| Physical Concept | Code Equivalent |
|-----------------|----------------|
| Terrain | Code structure (files, modules) |
| Gravity well | Popular/important functions |
| Friction | Complexity/resistance to change |
| Attractor | Stable destination points |
| Repeller | Volatile/transient code |
| Field | Direction of decreasing energy |

---

## 2. Differential Geometry

**What it is**: The mathematics of smooth curves, surfaces, and manifolds. Studies properties preserved under continuous deformations.

### 2.1 Manifold Space

**Problem Solved**: How do we represent code elements in a continuous space where "distance" and "direction" have semantic meaning?

**Implementation**:
```python
# Each symbol gets a position in manifold space (128-dim embedding)
manifold_position:
  embedding: List[float]  # 128-dimensional vector
  norm: float             # Vector magnitude
```

**Why it matters**: Manifold positions enable geometric operations:
- Euclidean distance between symbols → semantic similarity
- Vector direction → semantic relationship
- Gradient → navigation direction

### 2.2 Gradient and Field Vector

**Problem Solved**: What direction should an agent move to reach better code?

**Theory**: The gradient ∇E(x) points in the direction of steepest increase. The field F(x) = -∇E(x) points toward lower energy (better code).

**Implementation** (`phase3_5_kernel/field_kernel.py`):
```python
def compute_field_vector(self, symbol, sms, neighbors) -> FieldVector:
    gradient = self.compute_gradient(symbol, sms, neighbors)
    # Field = negative gradient (toward lower energy)
    direction = -gradient / |gradient|
    magnitude = |gradient|
    return FieldVector(direction, magnitude)
```

### 2.3 Hessian and Curvature

**Problem Solved**: Is a code element a stable destination (attractor), a volatile zone (repeller), or a transition point (saddle)?

**Theory**: The Hessian matrix H = ∇²E contains second derivatives. Its eigenvalues reveal the local curvature:

| Eigenvalues | Type | Meaning |
|-------------|------|---------|
| All > 0 | Local minimum | **Stable Attractor** - navigation target |
| All < 0 | Local maximum | **Unstable Repeller** - avoid |
| Mixed | Saddle point | **Transitional zone** - can go either way |

**Implementation** (`phase3_5_kernel/field_kernel.py`):
```python
def detect_attractor_type(self, symbol, sms, neighbors) -> str:
    hessian = self._compute_hessian(symbol, sms, neighbors)
    eigenvalues = np.linalg.eigvals(hessian)
    if all(ev > 0): return "stable_attractor"
    elif all(ev < 0): return "unstable_repeller"
    else: return "saddle_point"
```

### 2.4 Finite Differences

**Problem Solved**: How do we compute gradients when we don't have an analytical function?

**Theory**: Approximate derivatives using discrete sampling:
```
d²E/dx² ≈ (E(x+h) - 2E(x) + E(x-h)) / h²
```

**Implementation** (`phase3_5_kernel/field_kernel.py`):
```python
def _compute_hessian(self, symbol, sms, neighbors) -> np.ndarray:
    E_current = self.energy.compute_energy(sms)
    for i, (neighbor_id, neighbor_sms) in enumerate(neighbors):
        E_neighbor = self.energy.compute_energy(neighbor_sms)
        hessian[i, i] = E_neighbor - E_current
```

---

## 3. Dynamical Systems Theory

**What it is**: Studies systems that evolve over time according to fixed rules. Focuses on long-term behavior, stability, and attractors.

### 3.1 Energy Landscape Dynamics

**Problem Solved**: Where will navigation naturally flow to? What are stable endpoints?

**Theory**: A dynamical system on an energy landscape evolves toward local minima (attractors). The system is described by:
```
dx/dt = F(x) = -∇E(x)
```

**Implementation** (`phase2_5/pass4_field_initialization.py`):
```python
# Field vector: direction of flow
F(x) = -∇E(x) = Σ (E_neighbor - E_self) × direction × edge_weight
```

### 3.2 Attractor Types

**Problem Solved**: What kinds of stable destinations exist?

| Attractor Type | Condition | Example |
|---------------|-----------|---------|
| **Point Attractor** | Energy local minimum | Stable entry point |
| **Basin Attractor** | High in/out convergence ratio | Many callers, moderate callees |
| **Line Attractor** | Degenerate minimum | Multiple equivalent paths |
| **Chaotic Attractor** | Strange attractor | Unpredictable code paths |

**Implementation** (`phase2_5/pass6_attractor_bias.py`):
```python
def is_basin_attractor(out_degree, in_degree, energy, energy_rank):
    convergence_ratio = in_degree / (out_degree + 1)
    return (
        convergence_ratio > 2.0
        and in_degree >= 3
        and out_degree <= 20
        and energy_rank <= 0.3  # Top 30% energy
    )
```

### 3.3 Lyapunov Stability

**Problem Solved**: If we perturb a path slightly, does it still converge to the same destination?

**Theory**: A fixed point is Lyapunov stable if nearby trajectories stay nearby. Used to validate trajectory robustness.

**Implementation** (`phase3_5_kernel/trajectory_simulator.py`):
```python
def check_lyapunov_stability(self, trajectory) -> bool:
    """Check if trajectory is Lyapunov stable."""
    # Measures trajectory divergence under perturbations
```

---

## 4. Statistical Physics / Energy-Based Models

**What it is**: Studies systems with many degrees of freedom. Uses energy functions to describe macroscopic behavior from microscopic interactions.

### 4.1 Energy Landscape Metaphor

**Problem Solved**: How do we assign scalar "importance" values to code elements that capture both structural and behavioral properties?

**Theory**: Every code element has an energy value E. Lower energy = more stable/important. The Boltzmann distribution describes probability:
```
P(state) ∝ exp(-E/kT)
```

**Implementation** (`phase2_5/pass4_field_initialization.py`):
```python
# Total energy = potential + structural gravity + entropy bonus
E_total(s) = E_potential(s) + G_structural(s) + H_entropy(s)
```

### 4.2 Non-Linear Potential Functions

**Problem Solved**: Linear functions can't capture the true importance structure. We need non-linear transforms to amplify differences.

**Theory**: Log transforms prevent high-centrality nodes from becoming "black holes":
```
E_potential = w_c · log(1 + α·centrality)
```

**Implementation** (`phase2_5/pass4_field_initialization.py`):
```python
def compute_potential_energy(centrality, frequency, tau_persistence):
    E_c = W_CENTRALITY * math.log1p(centrality * ALPHA_CENTRALITY)
    E_f = W_FREQUENCY * math.log1p(frequency * BETA_FREQUENCY)
    E_t = W_STABILITY * (tau_persistence ** GAMMA_STABILITY)
    return E_c + E_f + E_t
```

### 4.3 Soft Caps (Sigmoid/Tanh Normalization)

**Problem Solved**: How do we prevent energy values from exploding while preserving gradient structure?

**Theory**: The tanh function creates a soft sigmoid that saturates at boundaries:
```
E_capped = cap × tanh(E_raw / cap)
```

**Implementation** (`phase2_5/pass4_field_initialization.py`):
```python
def apply_energy_soft_cap(energy, cap=10.0):
    return cap * math.tanh(energy / cap)
    # Asymptotically approaches cap without hard discontinuity
```

### 4.4 Entropy Maximization

**Problem Solved**: How do we measure the "complexity" of a code element's responsibilities?

**Theory**: Shannon entropy measures uncertainty. High entropy = many responsibilities = unstable. Low entropy = single focus = stable.

```
H = -Σ p_i · log(p_i)
```

**Implementation** (`phase2_5/pass4_field_initialization.py`):
```python
def compute_entropy_bonus(category_coupling):
    probs = [v / sum(categories.values()) for v in categories.values()]
    entropy = -sum(p * math.log(p + 1e-9) for p in probs)
    return W_ENTROPY * entropy
```

---

## 5. Classical Mechanics

**What it is**: Newton's laws of motion, force, mass, friction, and gravity. Provides intuitive metaphors for navigation.

### 5.1 Force = Mass × Acceleration

**Problem Solved**: How do we model the "effort" required to traverse code?

**Theory**: F = ma. In code space, force is the navigation push, mass is importance, acceleration is the rate of change.

**Implementation** (`phase3_5_kernel/field_kernel.py`):
```python
def compute_dynamics_state(self, sms, field_vector):
    mass = self.energy.compute_mass(sms)
    # F = ma → a = F/m
    force = field_vector.magnitude * field_vector.direction
    acceleration = force / (mass + 1e-10)
    return DynamicsState(mass=mass, friction=friction, acceleration=acceleration)
```

### 5.2 Gravitational Fields

**Problem Solved**: How do we create attractive "gravity wells" for important code elements?

**Theory**: Gravitational potential φ = -GM/r. Objects are attracted toward lower potential.

**Implementation** (`phase2_5/pass2_structural_analysis.py`):
```python
def compute_gravity_score(in_degree):
    # Sigmoid: high in-degree → high gravity
    return 1.0 / (1.0 + math.exp(-in_degree / 10.0))
```

### 5.3 Black Hole Gravity (Anti-Gravity)

**Problem Solved**: How do we prevent navigation from being "sucked into" low-value utility functions?

**Theory**: Black holes have intense gravity that light (and paths) cannot escape. We apply exponential penalty to low-mass + high-friction nodes.

**Implementation** (`phase4/heuristic.py`):
```python
def compute_gravity_penalty(self, symbol, friction):
    if not is_black_hole(symbol, friction):
        return 1.0
    # Exponential penalty for black hole nodes
    penalty = np.exp(friction * GRAVITY_CONSTANT)  # G = 3.0
    return penalty
```

### 5.4 Friction / Resistance

**Problem Solved**: How do we model the difficulty of traversing complex code?

**Theory**: Friction resists motion. High complexity = high friction = hard to traverse.

**Implementation** (`phase3/friction_mapper.py`):
```python
def compute_friction(self, ricci_norm):
    # Positive curvature → low friction (easy traversal)
    # Negative curvature → high friction (hard traversal)
    exponent = -self.alpha * ricci_norm
    friction = base_friction * math.exp(min(beta_cap, exponent))
```

### 5.5 Gravitational Acceleration

**Problem Solved**: How do we model the observation that agents move faster toward cores?

**Theory**: Objects in gravitational fields accelerate toward massive bodies. High-energy nodes should reduce friction.

**Implementation** (`phase2_5/pass4_field_initialization.py`):
```python
def compute_energy_adjusted_friction(base_friction, total_energy):
    normalized_energy = min(1.0, total_energy / 10.0)
    # High energy → lower friction (gravitational acceleration)
    adjusted = base_friction * (1.0 - energy_weight * normalized_energy)
```

---

## 6. Information Theory

**What it is**: The mathematics of information, entropy, and channel capacity. Founded by Shannon in 1948.

### 6.1 Mutual Information (MI) Gating

**Problem Solved**: Which graph edges represent real semantic relationships vs. noise?

**Theory**: MI measures how much knowing one variable reduces uncertainty about another. Edges with MI below threshold are noise.

```
I(X;Y) = Σ p(x,y) log(p(x,y) / (p(x)p(y)))
```

**Implementation** (`phase3/adaptive_mi_gate.py`):
```python
def compute_gate(self, weights):
    mean = sum(weights) / len(weights)
    std_dev = math.sqrt(variance)
    # Adaptive threshold: τ = μ + k×σ
    # Uniform distribution (σ≈0): τ = μ (no filtering)
    # Skewed distribution: k increases to filter outliers
    threshold = mean + k_factor * std_dev
```

### 6.2 Shannon Entropy for Source Diversity

**Problem Solved**: How diverse are the callers of a function? Single caller = fragile. Many callers = robust.

**Theory**: Entropy measures the spread of a distribution. Higher entropy = more diverse.

```
H = -Σ p_i log(p_i) / log(n)  # Normalized to [0,1]
```

**Implementation** (`phase2_5/pass5_backward_tension.py`):
```python
def compute_source_diversity(incoming_edges):
    probs = [weight / sum(weights) for _, weight in incoming_edges]
    entropy = -sum(p * math.log(p) for p in probs if p > 0)
    max_entropy = math.log(len(incoming_edges))
    return entropy / max_entropy if max_entropy > 0 else 0.0
```

### 6.3 TF-IDF (Term Frequency - Inverse Document Frequency)

**Problem Solved**: Which symbols are important vs. ubiquitous infrastructure?

**Theory**: Popular symbols called by many modules are important. Ubiquitous symbols (like `logging.info`) are not valuable navigation targets.

**Implementation** (`phase2/cognitive_mass.py`):
```python
def compute_mass(self, symbol_id):
    mass_tf = math.log(1 + in_degree)              # Term frequency
    mass_idf = math.log(1 + total_modules / (calling_modules + 1))  # IDF
    mass_hub_correction = 1 + math.log(1 + out_degree)  # Hub bonus
    return mass_tf * mass_idf * mass_hub_correction
```

---

## 7. Graph Theory & Network Science

**What it is**: The mathematics of graphs - nodes connected by edges. Studies structural properties of networks.

### 7.1 Centrality Measures

**Problem Solved**: Which nodes are most important in the graph?

**Theory**: Different centrality measures capture different aspects of importance:

| Measure | Formula | Captures |
|---------|---------|----------|
| **Degree** | Count of connections | Popularity |
| **Betweenness** | Fraction of shortest paths through node | Bridge importance |
| **Clustering** | Triangles / possible triangles | Community structure |
| **Eigenvector** | Principal eigenvector of adjacency | Influence propagation |

**Implementation** (`phase2/pass2_topology.py`):
```python
# Degree centrality
centrality = adjacency.get_weighted_out_degree(node)

# Betweenness proxy
betweenness = (in_degree * out_degree) / total_degree

# Clustering coefficient
edges_between = len(neighbors & neighbors_of_neighbors)
max_edges = len(neighbors) * (len(neighbors) - 1)
clustering = edges_between / max_edges
```

### 7.2 Role Inference

**Problem Solved**: What is the "personality" of each code element?

**Theory**: Nodes can be classified by structural patterns:

| Role | Characteristics |
|------|----------------|
| **Hub** | High out-degree, high centrality, low clustering |
| **Bridge** | High betweenness, balanced in/out |
| **Sink** | High in-degree, low out-degree |
| **Leaf** | Low total degree |

**Implementation** (`phase2/pass2_topology.py`):
```python
def _infer_role(self, node):
    scores = {"hub": 0.0, "bridge": 0.0, "sink": 0.0, "leaf": 0.0}
    if out_degree > 10 and centrality > 0.7 and clustering < 0.3:
        scores["hub"] += 0.4
    # ... scoring logic
    return max(scores.items(), key=lambda x: x[1])
```

### 7.3 Sparse Matrices

**Problem Solved**: How do we efficiently store and query large graphs?

**Theory**: Most real graphs are sparse (few connections). Store only non-zero entries.

**Implementation** (`phase2/pass1_distill.py`):
```python
class SparseAdjacencyMatrix:
    # Forward index: src → dst → weight
    matrix: Dict[str, Dict[str, float]]
    # Reverse index: dst → src → weight (O(1) in-neighbor lookup)
    in_matrix: Dict[str, Dict[str, float]]
```

---

## 8. Algebraic Topology

**What it is**: Studies properties preserved under continuous deformations - holes, voids, connectivity, loops.

### 8.1 Triangle Counting (Simplicial Complexes)

**Problem Solved**: How do we detect cyclic dependencies and transitive relationships?

**Theory**: Triangles (3-cycles) in graphs indicate:
- Transitive relationships (A→B→C, A→C)
- Feedback loops (A→B→C→A)

**Implementation** (`phase2/triangle_counter.py`):
```python
def count_triangles(self, source, target):
    # Transitive: u→v→w and u→w
    transitive = len(successors_source & successors_target)
    # Feedback: u→v→w→u
    feedback = len(successors_target & predecessors_source)
```

### 8.2 Directed Cycles

**Problem Solved**: Where are circular dependencies in the code?

**Theory**: Feedback triangles u→v→w→u indicate cyclic dependencies - architectural problems.

**Formula**:
```
Δ_feedback = |{w : (v,w) ∈ E ∧ (w,u) ∈ E}|
```

### 8.3 Forman-Ricci Curvature on Graphs

**Problem Solved**: How curved is the "surface" of the code graph? Where are architectural boundaries?

**Theory**: Ricci curvature on graphs measures how much the local geometry deviates from flat (Euclidean).

| Curvature | Meaning |
|-----------|---------|
| **Positive** | Like a sphere - locally clustered |
| **Zero** | Like a plane - flat, Euclidean |
| **Negative** | Like a hyperbola - sparse, boundary-like |

**Implementation** (`phase2/ricci_curvature.py`):
```python
# Forman-Ricci curvature formula
def compute_ricci_raw(deg_source, deg_target, triangle_count):
    Ric(e) = 4 - deg(u) - deg(v) + 3 × Δ(e)

# Normalized to prevent overflow
Ric_norm(e) = Ric_raw(e) / (1 + deg_max)
```

**Boundary Detection**: `is_boundary = ricci_norm < -0.5`

---

## 9. Control Theory & Optimal Pathfinding

**What it is**: Studies how to guide systems toward goals while minimizing cost. A* is a classic algorithm.

### 9.1 A* Algorithm

**Problem Solved**: What's the optimal path from entry point to target?

**Theory**: A* combines actual cost (g) with estimated remaining cost (h):
```
f(n) = g(n) + h(n)
```

- g(n): Cost from start to n
- h(n): Heuristic estimate from n to goal
- f(n): Estimated total cost

**Properties**:
- **Admissible**: h(n) ≤ actual cost (never overestimates)
- **Consistent**: h(n) ≤ cost(n,n') + h(n') (triangle inequality)

**Implementation** (`phase4/trajectory_planner.py`):
```python
while open_set:
    current = heapq.heappop(open_set)  # Node with lowest f
    if current == goal:
        return reconstruct_path(came_from, current)
    for neighbor in neighbors:
        tentative_g = g_score[current] + transition_cost(neighbor)
        if tentative_g < g_score[neighbor]:
            came_from[neighbor] = current
            g_score[neighbor] = tentative_g
            f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
            heapq.heappush(open_set, (f_score[neighbor], neighbor))
```

### 9.2 Weighted A*

**Problem Solved**: A* is optimal but slow. Can we trade optimality for speed?

**Theory**: Multiply heuristic by weight w ≥ 1:
```
f_w(n) = g(n) + w × h(n)
```

- w = 1: Standard A* (optimal)
- w > 1: Weighted A* (faster, suboptimal)

**Implementation** (`phase4/heuristic.py`):
```python
HEURISTIC_WEIGHT = 1.3  # 30% faster convergence
if weighted:
    h *= HEURISTIC_WEIGHT
```

### 9.3 Transition Energy as Control Signal

**Problem Solved**: How do we model the "cost" of traversing between code elements?

**Theory**: In physics, energy is the control signal. Transition energy combines multiple factors:

**Implementation** (`phase4/energy_model.py`):
```python
E_transition = λ_uphill · max(0, ΔU)
             + λ_align · (1 - alignment)
             + λ_friction · friction_norm
             + λ_distance · distance_norm
             - λ_intent · intent_force
```

### 9.4 Tensor Path Integral

**Problem Solved**: How do we measure overall path quality, not just total cost?

**Theory**: Use multiplicative integration along path:
```
Q = ∏ᵢ (1 - friction_i) × alignment_factor_i
coherence = Q^(1/n)  # Geometric mean
```

**Implementation** (`phase4/trajectory_planner.py`):
```python
def _compute_tensor_path_integral(self, path, intent_vector):
    tensor_quality = 1.0
    for i in range(len(path) - 1):
        curvature_factor = 1.0 - dst_friction
        alignment_factor = alignment(src_direction, intent_vector)
        tensor_quality *= curvature_factor * alignment_factor
    n_edges = len(path) - 1
    return tensor_quality ** (1.0 / n_edges)
```

---

## 10. Probability & Statistics

**What it is**: The mathematics of uncertainty, randomness, and data analysis.

### 10.1 Percentile Ranks

**Problem Solved**: How does a symbol compare to others in the codebase?

**Implementation** (`phase2/schema.py`):
```python
percentiles: Dict[str, float]  # metric → percentile rank [0,100]
```

### 10.2 Sigmoid / Logistic Function

**Problem Solved**: How do we map any value to [0,1] with saturation at extremes?

**Theory**:
```
σ(x) = 1 / (1 + e^(-x))
```

**Implementation** (`phase4/energy_model.py`):
```python
def normalize_friction(friction):
    # Sigmoid centered at 0.5: discriminates middle range
    return 1.0 / (1.0 + math.exp(-3.0 * (friction - 0.5)))
```

### 10.3 Log-Normal Distribution

**Problem Solved**: Many natural quantities follow log-normal distribution (e.g., income, file sizes). We use log transforms to handle skewed data.

**Theory**: If X ~ LogNormal(μ, σ), then log(X) ~ Normal(μ, σ)

**Implementation** (`phase4/energy_model.py`):
```python
def normalize_distance(distance):
    # Log transform: prevents distance explosion
    return math.log1p(distance) / math.log1p(max_distance)
```

### 10.4 Coefficient of Variation

**Problem Solved**: How skewed is the distribution of edge weights? Used for adaptive gating.

**Theory**: CV = σ/μ. High CV = skewed = more aggressive filtering.

**Implementation** (`phase3/adaptive_mi_gate.py`):
```python
cv = std_dev / mean if mean > 0 else 0
k_factor = base_k * (1 + cv)  # Adaptive filtering
```

### 10.5 Burstiness

**Problem Solved**: Is a symbol visited in bursts or evenly spread?

**Theory**: High frequency in short time = bursty = volatile.

**Implementation** (`phase2/pass1_distill.py`):
```python
def get_burstiness(self, symbol):
    avg_interval = duration / frequency
    # Shorter intervals = higher burstiness
    return min(1.0, 1.0 / (1.0 + avg_interval / 1e6))
```

---

## 11. Calculus / Real Analysis

**What it is**: Studies limits, derivatives, integrals, and infinite series.

### 11.1 Gradient Descent (Numerical)

**Problem Solved**: How do we find the direction of steepest descent on a discrete manifold?

**Theory**: The gradient ∇E points in the direction of steepest increase. Negative gradient points toward lower energy.

**Implementation** (`phase3_5_kernel/field_kernel.py`):
```python
def compute_gradient(self, symbol, sms, neighbors):
    E_current = self.energy.compute_energy(sms)
    gradient = []
    for neighbor_id, neighbor_sms in neighbors:
        E_neighbor = self.energy.compute_energy(neighbor_sms)
        dE = E_neighbor - E_current
        gradient.append(dE)
    return np.array(gradient)
```

### 11.2 Taylor Series Approximation

**Problem Solved**: How do we approximate a function's behavior near a point?

**Theory**:
```
f(x + h) ≈ f(x) + f'(x)h + ½f''(x)h² + ...
```

**Implementation** (used in Hessian computation):
```python
# Second derivative approximation
d²E/dx² ≈ (E(x+h) - 2E(x) + E(x-h)) / h²
```

### 11.3 Geometric Mean

**Problem Solved**: How do we aggregate multiplicative factors without underflow?

**Theory**: For product P = a₁ × a₂ × ... × aₙ:
```
P^(1/n) = (a₁ × a₂ × ... × aₙ)^(1/n)
```

**Implementation** (`phase4/trajectory_planner.py`):
```python
# Apply geometric mean to prevent underflow on long paths
coherence = tensor_quality ** (1.0 / n_edges)
```

---

## 12. Summary: Theory → Problem Matrix

| Theory | Problems Solved | Key Formulas |
|--------|----------------|--------------|
| **Differential Geometry** | Semantic space representation, navigation direction, attractor classification | ∇E, Hessian eigenvalues, F = -∇E |
| **Dynamical Systems** | Stable destinations, convergence behavior, basin detection | dx/dt = F(x), Lyapunov stability |
| **Statistical Physics** | Energy assignment, importance scaling, entropy-based complexity | E_total = E_pot + G_struct + H_ent, tanh soft-cap |
| **Classical Mechanics** | Effort modeling, gravity wells, friction, black hole avoidance | F=ma, φ = -GM/r, exp penalty |
| **Information Theory** | Edge filtering, source diversity, importance vs ubiquity | τ = μ + k×σ, H = -Σp·log(p), TF-IDF |
| **Graph Theory** | Structural analysis, role inference, centrality | degree, betweenness, clustering |
| **Algebraic Topology** | Cyclic dependency detection, curvature/boundary | Forman-Ricci, triangle counting |
| **Control Theory** | Optimal pathfinding, heuristic search, cost modeling | A* f=g+h, weighted A* |
| **Probability/Statistics** | Distribution handling, adaptive thresholds, comparison | sigmoid, log-normal, CV |
| **Calculus** | Gradient computation, stability analysis, numerical methods | ∇, Hessian, Taylor series |

---

## Appendix: Key Parameters Reference

| Parameter | Value | Theory |
|-----------|-------|--------|
| `HEURISTIC_WEIGHT` | 1.3 | Weighted A* (30% speedup) |
| `GRAVITY_CONSTANT` | 3.0 | Black hole exponential penalty |
| `ALPHA_CENTRALITY` | 1000 | Centrality amplification |
| `ATTRACTOR_BIAS` | 0.3 | Terminal node attraction |
| `BASIN_CONVERGENCE_RATIO` | 2.0 | Basin attractor threshold |
| `λ_uphill` | 0.40 | Potential gradient weight |
| `λ_align` | 0.35 | Direction alignment weight |
| `λ_friction` | 0.25 | Friction resistance weight |
| `λ_distance` | 0.15 | Manifold distance weight |
| `λ_intent` | 0.55 | Intent force weight |

---

## Appendix: Code → Theory Reference

| File | Theories Applied |
|------|------------------|
| `phase2/ricci_curvature.py` | Graph theory, Algebraic topology |
| `phase2/cognitive_mass.py` | Information theory (TF-IDF) |
| `phase2/pass1_distill.py` | Graph theory, Statistics |
| `phase2/pass2_topology.py` | Graph theory, Centrality |
| `phase2_5/pass1_git_heat.py` | Statistical physics (tanh) |
| `phase2_5/pass2_structural_analysis.py` | Classical mechanics (gravity) |
| `phase2_5/pass4_field_initialization.py` | Statistical physics, Calculus |
| `phase2_5/pass5_backward_tension.py` | Information theory (entropy) |
| `phase2_5/pass6_attractor_bias.py` | Dynamical systems |
| `phase3_5_kernel/field_kernel.py` | Differential geometry, Calculus |
| `phase3/adaptive_mi_gate.py` | Statistics, Information theory |
| `phase3/friction_mapper.py` | Classical mechanics, Calculus |
| `phase3/geometric_pathfinder.py` | Control theory (A*) |
| `phase4/energy_model.py` | Statistical physics, Mechanics |
| `phase4/heuristic.py` | Control theory, Classical mechanics |
| `phase4/trajectory_planner.py` | Control theory, Calculus |

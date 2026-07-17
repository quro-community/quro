---
type: Guide
title: TDA (Topological Data Analysis) System Guide
description: Comprehensive guide to the TDA system architecture, phases, physics model, and data schema for semantic topology analysis.
tags: [tda, topology, guide, system]
---

# TDA (Topological Data Analysis) System Guide

> **Mental Model**: The codebase is terrain. CQE is a map index. TDA is the topography. Execution is the actual roads.
>
> The TDA system models the **semantic topology** of a codebase — not execution flow. Edges represent semantic relationships, not function calls. Paths represent navigation possibilities, not runtime traces.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Phase 1: Observation Layer](#2-phase-1-observation-layer)
3. [Phase 2: Inference Layer](#3-phase-2-inference-layer)
4. [Phase 2.5: Energy Calibration](#4-phase-25-energy-calibration)
5. [Phase 3: LLM Enrichment](#5-phase-3-llm-enrichment)
6. [Phase 3.5: Holographic View](#6-phase-35-holographic-view)
7. [Phase 4: Trajectory Planning](#7-phase-4-trajectory-planning)
8. [Physics Model Reference](#8-physics-model-reference)
9. [Data Schema Reference](#9-data-schema-reference)

---

## 1. Architecture Overview

### 1.1 Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Phase 1: Observation Layer                   │
│         (raw graph event log from query execution)              │
│                  Input: Query events → graph_events.jsonl        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Phase 2: Inference Layer                     │
│         (Riemannian manifold analysis of symbol space)          │
│            Input: Phase1 → manifold_states.jsonl                 │
│        Algorithms: Ricci curvature, cognitive mass, topology    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Phase 2.5: Energy Calibration                │
│       (Physics-based potential field initialization)            │
│    Input: Phase2 + Git heat + edge weights → anisotropic_fields  │
│  Algorithms: Non-linear potential, structural gravity, backward  │
│             tension, attractor bias injection                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Phase 3: LLM Enrichment                       │
│          (Adaptive gating and friction mapping)                 │
│           Input: Phase2.5 → context-aware navigation            │
│         Algorithms: Adaptive MI gate, risk mapping, affordance   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Phase 3.5: Holographic View                   │
│        (Global codebase topology and navigation guidance)       │
│      Algorithms: Field aggregation, density mapping, void        │
│                 detection, folding regions                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Phase 4: Trajectory Planning                  │
│          (A* pathfinding on semantic energy field)             │
│         Input: Field data → optimal navigation paths            │
│    Algorithms: A*, tensor path integral, escape mechanism,       │
│               landing hints, alternative paths                   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Summary

```
Events (Phase1) → Distillation → Topology (Phase2) → Energy (Phase2.5)
    → Adaptation (Phase3) → Hologram (Phase3.5) → Trajectory (Phase4)
```

---

## 2. Phase 1: Observation Layer

**Location**: `quro_v3/tda/phase1/`

### 2.1 Purpose

Captures raw execution traces from query traversal as graph events.

### 2.2 Event Types

| Event Type | Description | Key Fields |
|------------|-------------|------------|
| `NODE_VISIT` | Symbol visited during traversal | `node.id`, `depth`, `predecessor` |
| `EDGE_TRAVERSE` | Edge traversed between symbols | `src`, `dst`, `weight`, `passed_gate` |
| `PATH_COMPLETE` | Complete traversal path | `nodes`, `total_length`, `entry_point` |

### 2.3 Schema (Phase 1 Event Schema)

```python
# Key models in schema.py
class NodeVisitEvent:
    node: NodeInfo  # id, kind, file_path, line_number
    visit_context: VisitContext  # depth, predecessor, via_edge_type

class EdgeTraverseEvent:
    edge: EdgeInfo  # src, dst, edge_type, weight, direction
    traverse_context: TraverseContext  # depth, tau_threshold, passed_gate

class PathCompleteEvent:
    path: PathInfo  # nodes[], edges[], total_length
    path_context: PathContext  # entry_point, target, is_shortest
```

### 2.4 Edge Types

| Type | Description |
|------|-------------|
| `CALL` | Direct function call |
| `IMPORT` | Import statement |
| `CATEGORY` | Semantic category relationship |
| `LOCK` | Synchronization primitive |
| `INHERIT` | Class inheritance |
| `ASYNC_CALL` | Async function call |
| `AWAIT` | Await expression |

### 2.5 Output

```
.quro_context/tda/phase1/graph_events.jsonl
```

Each line is a JSON event with `record_type` or `event_type` discriminator.

---

## 3. Phase 2: Inference Layer

**Location**: `quro_v3/tda/phase2/`

### 3.1 Purpose

Analyzes the event stream to extract topological properties and infer the Riemannian manifold structure of the symbol space.

### 3.2 Pass 1: Atomic Feature Distillation

**File**: `pass1_distill.py`

Scans Phase-1 event stream and builds statistical structures.

#### Core Classes

**SparseAdjacencyMatrix**
- Maintains both forward and reverse indices for O(1) in-neighbor lookup
- Methods: `add_edge()`, `get_neighbors()`, `get_in_neighbors()`, `get_weighted_out_degree()`

**SymbolFrequencyMap**
- Tracks symbol visit frequency across queries
- Computes burstiness coefficient: `min(1.0, 1.0 / (1.0 + avg_interval / 1e6))`

**TauSurvivalTable**
- Tracks edge survival across tau thresholds
- `get_persistence()`: Returns ratio of passed traversals to total attempts

**EdgeTypeDistribution**
- Tracks edge type distribution per symbol
- `get_dominant_type()`: Returns most common edge type

### 3.3 Pass 2: Topology Inference

**File**: `pass2_topology.py`

Computes topological properties from distilled features.

#### Metrics

| Metric | Formula | Meaning |
|--------|---------|---------|
| **Centrality** | `weighted_out_degree` | Importance/influence |
| **Betweenness** | `(in × out) / total_degree` | Bridge behavior |
| **Clustering** | `edges_between_neighbors / max_possible` | Local density |
| **Role** | Heuristic scoring | hub/bridge/sink/leaf |

#### Role Inference Heuristics

```python
Hub:       out_degree > 10 AND centrality > 0.7 AND clustering < 0.3
Bridge:    betweenness > 0.5 AND balanced in/out degree
Sink:      in_degree > 5 AND out_degree < 3
Leaf:      total_degree <= 2
```

### 3.4 Pass 3: Manifold Projection

**File**: `pass3_project.py`

Projects symbols into low-dimensional manifold space (currently 128-dim embedding).

### 3.5 Pass 4: Field Enrichment

**File**: `pass4_field_enrichment.py`

Adds physics-based field metrics to manifold states using the Phase-3.5 Kernel.

### 3.6 Forman-Ricci Curvature

**File**: `ricci_curvature.py`

Calculates edge curvature for boundary detection.

#### Formula

```
Ric(e) = 4 - deg(source) - deg(target) + 3 × Δ(e)
Ric_norm(e) = Ric_raw(e) / (1 + deg_max)
```

Where Δ(e) is the directed triangle count (transitive + feedback cycles).

**Boundary Detection**: Edge is a boundary if `ricci_norm < -0.5`

### 3.7 Cognitive Mass (TF-IDF with Hub Correction)

**File**: `cognitive_mass.py`

Calculates symbol importance using a TF-IDF-inspired formula.

#### Formula

```
TF = log(1 + in_degree)
IDF = log(1 + total_modules / (calling_modules + 1))
Hub_correction = 1 + log(1 + out_degree)
mass_cognitive = TF × IDF × Hub_correction
```

- **High mass**: Popular targets called from many modules
- **Hub correction**: Distinguishes hubs (high out-degree) from pure sinks

### 3.8 Phase 2 Output Schema

**File**: `schema.py`

```python
class SymbolManifoldState:
    symbol: str
    manifold_position: ManifoldPosition  # embedding, norm
    topology: TopologyMetrics  # centrality, betweenness, clustering
    stability: StabilityMetrics  # tau_persistence, entry_variance, structural_noise
    role: RoleInfo  # type, confidence
    category_coupling: Dict[str, float]  # category → coupling strength
    temporal_signature: TemporalSignature  # first_seen, frequency, burstiness
    percentiles: Dict[str, float]  # metric → percentile rank

    # Field metrics (added by pass4_field_enrichment)
    energy: Dict[str, float]  # potential, kinetic, total
    field_role: str  # attractor/repeller/saddle_point/not_critical
    field_magnitude: float  # ||∇E(x)||
    mass: float  # (centrality + frequency) / 2
    friction: float  # (1 - stability) × (1 + noise)
```

---

## 4. Phase 2.5: Energy Calibration

**Location**: `quro_v3/tda/phase2_5/`

### 4.1 Purpose

Initializes the physics-based energy field with non-linear potentials, structural gravity, and attractor bias.

### 4.2 Pass 1: Git Heat Extraction

**File**: `pass1_git_heat.py`

Extracts modification frequency from git history.

#### Heat Score Formula

```
heat_score = tanh(commits_30d / 10) × 0.6 + tanh(lines_changed / 100) × 0.4
```

- **High heat**: Frequently modified = volatile = high kinetic energy
- **Low heat**: Stable = low kinetic energy

### 4.3 Pass 2: Structural Analysis

**File**: `pass2_structural_analysis.py`

Computes structural gravity scores from graph topology.

### 4.4 Pass 3: Asymmetric Edge Weighting

**File**: `pass3_edge_weighting.py`

Assigns asymmetric weights based on relationship type.

#### Edge Weight Constants

| Edge Type | Weight | Description |
|-----------|--------|-------------|
| `composition` | 0.9 | Class → Method |
| `inheritance` | 0.85 | Parent → Child |
| `dependency` | 0.5 | Module → Module |
| `utility_call` | 0.3 | Business → Utility |
| `data_flow_complex` | 0.7 | Passing DTO/Class |
| `data_flow_simple` | 0.4 | Passing primitive |

### 4.5 Pass 4: Field Initialization (Design 85)

**File**: `pass4_field_initialization.py`

**Core Formula (Design 85)**:

```
E_total(s) = E_potential(s) + G_structural(s) + H_entropy(s)
```

#### Energy Components

**Potential Energy**:
```
E_potential = w_c · log(1 + α·centrality)
            + w_f · log(1 + β·frequency)
            + w_τ · (tau_persistence)^γ

Coefficients:
- w_c = 0.4 (centrality weight)
- α = 1000 (centrality amplification)
- w_f = 0.3 (frequency weight)
- β = 1 (frequency amplification)
- w_τ = 0.3 (stability weight)
- γ = 3 (stability exponent)
```

**Structural Gravity**:
```
G_structural = w_in · log(1 + in_degree)
             + w_div · caller_diversity

Coefficients:
- w_in = 0.5
- w_div = 0.7
```

**Entropy Bonus**:
```
H_entropy = w_H · entropy(category_coupling)
- w_H = 0.3
- Low entropy → single responsibility → attractor
- High entropy → multiple responsibilities → saddle
```

#### Soft Cap (Energy Explosion Prevention)

```
E_capped = cap × tanh(E_raw / cap)
# cap = 10.0
```

#### Energy-Adjusted Friction

```
friction_adjusted = base_friction × (1 - energy_weight × normalized_energy)
# energy_weight = 0.3
# High-energy nodes (e.g., main) → lower friction → smoother spacetime
# Low-energy nodes (e.g., transient) → higher friction → muddy terrain
```

#### Field Vector Computation

```
F(x) = -∇E(x) = Σ over neighbors of: (E_neighbor - E_self) × direction × edge_weight
```

### 4.6 Pass 5: Backward Tension (Anisotropic Field Model)

**File**: `pass5_backward_tension.py`

Creates anisotropic field model enabling controlled upstream navigation.

#### Backward Tension Formula

```
tension = Σ(edge_weight × source_gravity) / in_degree
```

#### Source Diversity Formula

```
diversity = -Σ(p_i × log(p_i)) / log(n)
# High diversity = many balanced sources
# Low diversity = single dominant source
```

### 4.7 Pass 6: Attractor Bias Injection (Design 90)

**File**: `pass6_attractor_bias.py`

Adds terminal node weighting to create stable destination points.

#### Bias Criteria

| Condition | Bias | Reason |
|-----------|------|--------|
| Terminal node (out_degree=0, in_degree>0) | 0.3 | Terminal sink |
| Terminal tags (database, serialize, persist...) | 0.21 | Persistence semantics |
| Utility tags (helper, util, format...) | 0.0 | Excluded |

#### Terminal Tags

```python
TERMINAL_TAGS = {
    "database", "serialize", "snapshot", "persist",
    "commit", "write", "save", "store", "flush", "finalize"
}
```

#### Basin Attractor Detection (Annotation Layer Only)

```
is_basin = convergence_ratio > 2.0
         AND in_degree >= 3
         AND out_degree <= 20
         AND energy_rank <= 0.3  # Top 30%

convergence_ratio = in_degree / (out_degree + 1)
```

---

## 5. Phase 3: LLM Enrichment

**Location**: `quro_v3/tda/phase3/`

### 5.1 Adaptive MI Gate

**File**: `adaptive_mi_gate.py`

Dynamically adjusts the Mutual Information threshold based on traversal context.

### 5.2 Friction Mapper

**File**: `friction_mapper.py`

Maps symbol complexity to friction coefficients.

### 5.3 Geometric Pathfinder

**File**: `geometric_pathfinder.py`

Implements geometry-aware pathfinding using manifold distances.

### 5.4 Role Interpreter

**File**: `pass1_role_interpreter.py`

Interprets symbol roles for navigation decisions.

### 5.5 Risk Mapper

**File**: `pass2_risk_mapper.py`

Maps traversal risk based on edge types and node properties.

### 5.6 Affordance Engine

**File**: `pass3_affordance_engine.py`

Generates navigation affordances for available actions.

---

## 6. Phase 3.5: Holographic View

**Location**: `quro_v3/tda/phase3_5/`

### 6.1 Purpose

Assembles a global holographic view of the codebase topology.

### 6.2 Pass 1: Field Aggregator

**File**: `pass1_field_aggregator.py`

Aggregates discrete SMS points into spatial grid based on directory structure.

```python
class GridCell:
    path: str  # Directory path
    symbols: List[SymbolManifoldState]  # Symbols in this cell
    density: float  # Symbol density
```

### 6.3 Pass 2: Field Mapper

**File**: `pass2_field_mapper.py`

Computes semantic density, curvature, and stress fields.

```python
class ManifoldFieldMapper:
    density_field: Dict[str, float]   # Symbol density per region
    curvature_field: Dict[str, float] # Manifold curvature
    stress_field: Dict[str, float]    # Coupling pressure
```

### 6.4 Pass 3: Void Detector & Hologram Assembler

**File**: `pass3_hologram_assembler.py`

Detects semantic voids and assembles the complete holographic view.

#### Global Metrics

```python
class GlobalMetrics:
    center_of_mass: str      # Region with highest density
    dominant_axis: str       # Dominant coupling (e.g., "async ↔ database")
    coherence: float         # 1 - fragmentation
    fragmentation: float     # Coefficient of variation in density
    coupling_pressure: float # Average stress
```

#### Void Detection

```
void_score = 1.0 - density
recommendation = "candidate_for_removal" if void_score > 0.9
               else "review_needed" if void_score > 0.7
               else "keep"
```

#### Semantic Folding Detection

```
folding = curvature > 0.7 AND density > 0.7
```

### 6.5 Phase 3.5 Kernel

**Location**: `phase3_5_kernel/`

#### Field Kernel (field_kernel.py)

Core physics implementation.

```python
class FieldKernel:
    def compute_field_vector(self, symbol, sms, neighbors) -> FieldVector:
        """F(x) = -∇E(x)"""
        gradient = self.compute_gradient(symbol, sms, neighbors)
        direction = -gradient / |gradient|  # Toward lower energy
        magnitude = |gradient|
        return FieldVector(direction, magnitude)

    def detect_attractor_type(self, symbol, sms, neighbors) -> str:
        """Classify using Hessian eigenvalues"""
        # Hessian: d²E/dx² via finite differences
        eigenvalues = np.linalg.eigvals(hessian)
        if all(eigenvalues > 0): return "stable_attractor"    # Local minimum
        if all(eigenvalues < 0): return "unstable_repeller"   # Local maximum
        else: return "saddle_point"                            # Mixed
```

#### Energy Functional

```python
class EnergyFunctional:
    def compute_energy(self, sms) -> float:
        """E(x) = potential + kinetic"""
        # Potential from manifold position
        # Kinetic from frequency (proxy for velocity)
        return potential + 0.5 * mass * velocity²

    def compute_mass(self, sms) -> float:
        """mass = (centrality + frequency) / 2"""

    def compute_friction(self, sms) -> float:
        """friction = (1 - stability) × (1 + noise)"""
```

#### Trajectory Simulator

**File**: `phase3_5_kernel/trajectory_simulator.py`

Energy-conserving trajectory simulation with Lyapunov stability checks.

---

## 7. Phase 4: Trajectory Planning

**Location**: `quro_v3/tda/phase4/`

### 7.1 Overview

A* pathfinding on the semantic energy field for optimal navigation.

### 7.2 Field Data Loading

**File**: `trajectory_planner.py` (FieldData class)

Loads manifold states from Phase 2 and adjacency from Phase 1.

```python
class FieldData:
    states: Dict[str, dict]  # symbol → {position, direction, friction, energy}
    adjacency: Dict[str, List[str]]  # symbol → neighbors

    # Pickle caching for ~10× faster loading
```

### 7.3 Energy Model (Design 87)

**File**: `energy_model.py`

#### Transition Energy Formula

```
E_transition = λ_uphill · max(0, ΔU)
             + λ_align · (1 - alignment)
             + λ_friction · friction_norm
             + λ_distance · distance_norm
             - λ_intent · intent_force

Structural amplification:
E_transition *= (1 + λ_tau_sharpness · (1 - tau_norm))
```

#### Coefficients

| Parameter | Value | Description |
|-----------|-------|-------------|
| `λ_uphill` | 0.40 | Potential gradient penalty |
| `λ_align` | 0.35 | Direction alignment |
| `λ_friction` | 0.25 | Friction resistance |
| `λ_distance` | 0.15 | Manifold distance |
| `λ_intent` | 0.55 | Intent force bonus |
| `λ_centrality_boost` | 0.20 | Attractor creation |
| `λ_tau_sharpness` | 0.30 | Noise pruning |

#### Normalization Functions

**Distance** (log transform):
```python
normalize_distance(d) = log(1 + d) / log(1 + max_distance)
```

**Friction** (sigmoid):
```python
normalize_friction(f) = 1 / (1 + exp(-3 × (f - 0.5)))
```

**Centrality** (log transform):
```python
normalize_centrality(c) = log(1 + c) / log(1 + max_centrality)
```

### 7.4 Heuristic Function (Design 87 + Phase 2)

**File**: `heuristic.py`

#### Formula

```
h(n) = w_manifold · normalize_distance(manifold_distance)
     + w_direction · direction_difference
     × HEURISTIC_WEIGHT
     × gravity_penalty(n)
```

**Coefficients**:
| Parameter | Value | Description |
|-----------|-------|-------------|
| `HEURISTIC_WEIGHT` | 1.3 | Weighted A* multiplier |
| `w_manifold` | 0.15 | Matches λ_distance |
| `w_direction` | 0.30 | Slightly below λ_align |

#### Black Hole Gravity Field

Nodes with **low mass + high friction** (bottom-layer utilities) are penalized.

```
Black hole = mass < 5.0 AND friction > 0.5
gravity_penalty = exp(friction × 3.0) if black_hole else 1.0
```

### 7.5 A* Trajectory Planner

**File**: `trajectory_planner.py`

```python
class TrajectoryPlanner:
    def plan_trajectory(self, request: TrajectoryRequest) -> TrajectoryPlan:
        # A* search with:
        # - g_score: cumulative transition energy
        # - h_score: heuristic to goal
        # - f_score = g + h
        # - Constraints: max_energy, max_friction, max_hops
        pass
```

#### Constraints

```python
@dataclass
class TrajectoryConstraints:
    max_energy: float = 10.0      # Maximum total energy budget
    max_friction: float = 0.8    # Maximum friction threshold
    max_hops: int = 20           # Maximum path length
    avoid_symbols: List[str] = [] # Symbols to avoid
```

### 7.6 Tensor Path Integral (Coherence)

**File**: `trajectory_planner.py`

Measures path quality via multiplicative integration.

```python
def _compute_tensor_path_integral(path, intent_vector) -> float:
    """
    Formula: ∏ ((1 - friction) × alignment_factor) along each edge
    Then apply geometric mean: result^(1/(n-1)) to prevent underflow

    Higher friction (bottom layer, architectural boundary) = lower quality
    """
    tensor_quality = 1.0
    for each edge (src → dst):
        curvature_factor = 1.0 - dst_friction
        alignment_factor = alignment(src_direction, intent_vector)
        edge_quality = curvature_factor * alignment_factor
        tensor_quality *= edge_quality
    return tensor_quality ** (1.0 / n_edges)
```

### 7.7 Escape Mechanism

**File**: `escape_mechanism.py`

Sink escape using upstream navigation (deprecated in Phase 3 for natural backtracking).

```python
class EscapeMechanism:
    def is_sink(self, symbol, neighbors) -> bool:
        """Sink = no neighbors OR (backward_tension > 0.7 AND forward_magnitude < 0.3)"""

    def find_escape_target(self, symbol, intent_vector) -> str:
        """
        Strategy:
        1. Get upstream sources (incoming edges)
        2. Rank by: backward_tension × source_diversity × edge_weight
        3. Filter by intent alignment
        4. Return top candidate
        """
```

### 7.8 Alternative Paths (Yen's Algorithm)

**File**: `alternative_paths.py`

Generates k-shortest paths for comparison.

```python
class AlternativePathGenerator:
    def generate_k_shortest_paths(self, start, goal, intent_vector, k=3):
        """
        Yen's algorithm:
        1. Find first shortest path
        2. For each node in path:
           - Spur node = current node
           - Root path = path to spur
           - Find spur path avoiding excluded edges
           - Add total path to candidates
        3. Pop best candidate as next shortest
        """
```

### 7.9 Intent Encoder

**File**: `intent_encoder.py`

Encodes natural language intent to 128-dim semantic vectors using Ollama `qwen3-embedding:8b`.

### 7.10 Landing Hints (Design 98)

**File**: `landing_hint.py`

Generates landing hints for trajectory paths — suggesting optimal entry points into code.

**Observer pattern**: Pure observer with zero graph mutation.

**Scoring factors**:
- Energy score: Based on field magnitude
- Fanout score: Based on out-degree
- Convergence score: Based on in/out ratio
- Position bias: Based on path position

---

## 8. Physics Model Reference

### 8.1 Energy Landscape

```
E_total(s) = E_potential(s) + G_structural(s) + H_entropy(s)

E_potential:  Non-linear from centrality, frequency, stability
G_structural: Injected gravity from in-degree and caller diversity
H_entropy:   Information entropy from category coupling
```

### 8.2 Field Dynamics

```
F(x) = -∇E(x) = Σ (E_neighbor - E_self) × direction × weight
```

### 8.3 Attractor Classification

| Type | Condition | Behavior |
|------|-----------|----------|
| **Stable Attractor** | Hessian eigenvalues all positive | Local minimum, navigation target |
| **Unstable Repeller** | Hessian eigenvalues all negative | Local maximum, avoid |
| **Saddle Point** | Mixed eigenvalues | Transitional zone |
| **Basin Attractor** | high in/out ratio, top energy | Annotation only, high-convergence node |

### 8.4 Transition Physics

```
Transition barrier = friction × |ΔE|
```

High friction nodes resist transitions. Energy-adjusted friction reduces friction for high-energy nodes (gravitational acceleration toward cores).

### 8.5 Black Hole Prevention

```
Black hole nodes (low mass + high friction) receive exponential gravity penalty:
penalty = exp(friction × GRAVITY_CONSTANT)

This prevents A* from being attracted to bottom-layer utilities.
```

---

## 9. Data Schema Reference

### 9.1 Phase 1 Events

```json
// NODE_VISIT
{"event_type": "NODE_VISIT", "node": {"id": "sym::foo", "kind": "method"}, "visit_context": {"depth": 2}}

// EDGE_TRAVERSE
{"event_type": "EDGE_TRAVERSE", "edge": {"src": "sym::A", "dst": "sym::B", "weight": 0.8}}

// PATH_COMPLETE
{"event_type": "PATH_COMPLETE", "path": {"nodes": ["sym::A", "sym::B"]}}
```

### 9.2 Phase 2 Manifold States

```json
{
  "symbol": "sym::main",
  "manifold_position": {"embedding": [0.1, 0.2, ...], "norm": 1.0},
  "topology": {"centrality": 0.8, "betweenness": 0.3, "clustering_coeff": 0.2},
  "stability": {"tau_persistence": 0.9, "entry_variance": 0.1, "structural_noise": 0.05},
  "role": {"type": "hub", "confidence": 0.85},
  "category_coupling": {"cat::async": 0.7, "cat::database": 0.3},
  "temporal_signature": {"first_seen": 1699900000000, "frequency": 42, "burstiness": 0.6},
  "energy": {"potential": 2.5, "kinetic": 0.8, "total": 3.3},
  "field_role": "attractor",
  "field_magnitude": 1.2,
  "mass": 0.65,
  "friction": 0.35
}
```

### 9.3 Phase 2.5 Anisotropic Fields

```json
{
  "symbol": "sym::main",
  "forward_direction": [0.1, 0.2, ...],
  "forward_magnitude": 0.8,
  "backward_tension": 0.3,
  "source_diversity": 0.7,
  "in_degree": 10,
  "out_degree": 5,
  "field_type": "anisotropic"
}
```

### 9.4 Phase 3.5 Hologram

```json
{
  "global_metrics": {
    "center_of_mass": "src/api",
    "dominant_axis": "async ↔ database",
    "coherence": 0.75,
    "fragmentation": 0.25,
    "coupling_pressure": 0.4
  },
  "field_statistics": {
    "energy_distribution": {"mean": 3.2, "std": 1.5, "min": 0.1, "max": 8.0},
    "attractor_count": 42,
    "repeller_count": 15,
    "saddle_count": 88
  },
  "void_regions": [...],
  "semantic_folding_regions": [...],
  "navigation_guidance": {
    "recommended_entry_points": ["sym::main", "sym::run"],
    "high_risk_zones": ["src/legacy"],
    "safe_refactor_zones": ["src/new"]
  }
}
```

### 9.5 Phase 4 Trajectory Plan

```python
@dataclass
class TrajectoryPlan:
    path: List[str]                    # List of symbol IDs
    total_energy: float                 # Cumulative transition energy
    avg_alignment: float                # Average intent alignment
    risk_score: float                   # Average friction along path
    coherence: float                    # Tensor path integral quality
    is_valid: bool                      # Passes validation thresholds
    landing_hints: Optional[List[dict]] # Top-K landing hints
```

---

## Appendix A: Key Files

| File | Purpose |
|------|---------|
| `phase1/schema.py` | Event schemas |
| `phase2/pass1_distill.py` | Feature distillation |
| `phase2/pass2_topology.py` | Topology inference |
| `phase2/ricci_curvature.py` | Forman-Ricci curvature |
| `phase2/cognitive_mass.py` | TF-IDF mass calculation |
| `phase2_5/pass4_field_initialization.py` | Energy field init |
| `phase2_5/pass5_backward_tension.py` | Anisotropic fields |
| `phase2_5/pass6_attractor_bias.py` | Attractor bias |
| `phase3_5_kernel/field_kernel.py` | F(x) = -∇E(x) |
| `phase4/energy_model.py` | Transition energy |
| `phase4/heuristic.py` | A* heuristic |
| `phase4/trajectory_planner.py` | A* planner |
| `phase4/landing_hint.py` | Landing hints |

## Appendix B: Design References

| Design | Name | Purpose |
|--------|------|---------|
| Design 85 | Field Recalibration | Physics-based energy model |
| Design 87 | Non-linear Potential | Enhanced transition costs |
| Design 88 | Natural Backtracking | Phase 3 escape mechanism |
| Design 90 | Fix No Attractors | Terminal node weighting |
| Design 94 | Basin Annotations | Convergence point detection |
| Design 98 | Landing Hint System | Trajectory entry points |

## Appendix C: Mental Model Reminders

> **CRITICAL**: Edges ≠ calls. Weights ≠ probability. Paths ≠ execution. No path ≠ no relation.

- **Edge**: Semantic relationship (statistical association, similarity, proximity)
- **Weight**: Strength of semantic connection, not execution likelihood
- **Attractor**: Navigation target (can be execution sink or basin)
- **Field vector**: Direction of decreasing energy (navigation gradient)

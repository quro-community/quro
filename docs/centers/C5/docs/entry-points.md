# C5 Entry Point Analysis

## Entry Points (from landscape)

### 1. `sym::MorphismInsertRequest::types::132`

- **Location**: `adapters/registry/types.py:132`
- **Role**: EMITTER (forward_magnitude=2.00, backward_tension=0.075)
- **In-degree**: 4 | **Out-degree**: 7
- **Type**: Frozen dataclass
- **Purpose**: Request to insert or update a morphism (edge) between two symbols in the registry.
- **Fields**: `from_symbol_name`, `to_symbol_name`, `morphism_type="CALLS"`, `weight=0.8`, `metadata`
- **Post-init**: Sets default metadata dict to `{}` if None
- **Consumed by**: RegistryAdapter (C4), orchestration layer (C0)
- **Impact**: Part of SC480 tight coupling cluster with C4 — changes may affect both centers

### 2. `sym::TrustWeights::types::48`

- **Location**: `policy/trust/types.py:48`
- **Role**: EMITTER (forward_magnitude=2.08, backward_tension=0.075)
- **In-degree**: 4 | **Out-degree**: 7
- **Type**: Frozen dataclass
- **Purpose**: Configurable weights for trust formula. Validates that weights sum to 1.0.
- **Fields**: `freshness=0.40`, `recency=0.30`, `upstream_trust=0.20`, `consumer_health=0.10`
- **Trust formula**: `base_trust = 0.40*freshness + 0.30*recency + 0.20*upstream_trust + 0.10*consumer_health`
- **Final formula**: `trust = min(base_trust * drift_stability^4 * verification_factor, semantic_gravity)`
- **Consumed by**: TrustEngine (compute_trust), C0 orchestration

### 3. `sym::PathGrammarPolicy::policy::141`

- **Location**: `core/cqe/policy.py:141`
- **Role**: EMITTER (forward_magnitude=1.67, backward_tension=0.075)
- **In-degree**: 4 | **Out-degree**: 7
- **Type**: Frozen dataclass (part of CQEPolicy composition)
- **Purpose**: Defines valid semantic layer transitions for path grammar. Prevents invalid semantic paths during traversal.
- **Layer map**:
  - `inherits`, `calls`, `imports` → `"structural"`
  - `category`, `semantic_similarity` → `"semantic"`
  - `attr_access` → `"noisy"`
- **Allowed transitions**: START → (structural, semantic, noisy); structural → structural/semantic/noisy; semantic → semantic/noisy (cannot go back up); noisy → noisy
- **Consumed by**: CQE Kernel (C0) for path validation during traversal
- **Flag**: `hub_normalization_enabled=True` — softly normalizes hub outgoing edges

## High-Energy Symbols (forward_magnitude > 1.5)

| Symbol | Role | Forward Mag | Backward Tension | Description |
|--------|------|-------------|------------------|-------------|
| `NormalizePolicy::policy::106` | EMITTER | 5.17 | 0.075 | CQE normalization configuration |
| `CQEPolicy::policy::177` | EMITTER | 5.17 | 0.075 | Complete CQE policy container |
| `TrajectoryRequest::trajectory_planner::61` | TRANSIENT | 2.79 | 0.412 | Trajectory planning request |
| `TrustWeights::types::48` | EMITTER | 2.08 | 0.075 | Trust formula weights |
| `MorphismInsertRequest::types::132` | EMITTER | 2.00 | 0.075 | Registry morphism insert request |
| `TrustComputeRequest::types::82` | EMITTER | 1.84 | 0.267 | Trust computation request |
| `ShadowWriteRequest::types::54` | EMITTER | 1.84 | 0.267 | Shadow file write request |
| `CrossSTAConflict::types::44` | EMITTER | 1.84 | 0.267 | Cross-symbol conflict detection |
| `HealDecision::types::53` | TRANSIENT | 1.84 | 0.305 | Self-heal approval decision |

## Entry Strategy

C5 is a **top-down hub archetype**. Exploration strategy:
1. Start from the 3 entry points (MorphismInsertRequest, TrustWeights, PathGrammarPolicy)
2. Expand outward by following EMITTER edges to their consumers (primarily C0)
3. Catalog TRANSIENT nodes as pass-through types consumed along the way
4. Pay special attention to SC480 cluster types shared with C4

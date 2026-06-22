# C5 API Surface

## Trust Policy (`policy/trust/`)

### Types (`policy/trust/types.py`)

| Class | Kind | Description | Key Fields |
|-------|------|-------------|------------|
| `TrustSignals` | Frozen dataclass | Observable staleness signals | freshness, recency, upstream_trust, drift_stability, consumer_health, verified, semantic_gravity |
| `TrustRecord` | Frozen dataclass | Immutable trust state snapshot | symbol, trust, freshness, recency, upstream_trust, drift_stability, consumer_health, computed_at, signals_frozen |
| `TrustWeights` | Frozen dataclass | Configurable trust weights | freshness=0.40, recency=0.30, upstream_trust=0.20, consumer_health=0.10 |
| `TrustComputeRequest` | Frozen dataclass | Trust computation request | symbol, signals |
| `TrustPropagationRequest` | Frozen dataclass | Trust propagation request | records, dependencies |
| `UpstreamDependency` | Frozen dataclass | Dependency edge | from_symbol, to_symbol, edge_type |

### TrustEngine (`policy/trust/engine.py`)

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `compute_trust` | (request: TrustComputeRequest, weights: TrustWeights) | TrustRecord | Compute trust from signals with non-linear penalties |
| `propagate_upstream_trust` | (request: TrustPropagationRequest, weights: TrustWeights) | Tuple[TrustRecord, ...] | Propagate trust through dependency graph |
| `clamp_signal` | (value, lo=0.0, hi=1.0) | float | Clamp signal to [lo, hi] |
| `get_trust` | (symbol, records, default=0.5) | float | Get trust score for a symbol |

### Protocol (`policy/trust/protocol.py`)

| Protocol Method | Signature | Description |
|----------------|-----------|-------------|
| `compute_trust` | (request, weights) -> TrustRecord | Pure trust computation contract |
| `propagate_upstream_trust` | (request, weights) -> Tuple[TrustRecord] | Upstream propagation contract |
| `clamp_signal` | (value, lo, hi) -> float | Signal clamping contract |
| `get_trust` | (symbol, records, default) -> float | Trust lookup contract |

## Self-Heal Policy (`policy/self_heal/`)

### Types (`policy/self_heal/types.py`)

| Class | Kind | Description | Key Fields |
|-------|------|-------------|------------|
| `AtomPatchOp` | Frozen dataclass | Single atomic patch operation | action, target_line, new_atom, insert_after |
| `AtomPatch` | Frozen dataclass | Patch operations collection | symbol, expected_checksum, ops |
| `HealProposal` | Frozen dataclass | Autonomous refactoring proposal | proposal_id, symbol, description, atom_patch, predicted_risk_delta, high_risk, validation_trials |
| `HealDecision` | Frozen dataclass | Heal approval decision | proposal_id, approved, reason, trust_score, nrt_breach |
| `HealResult` | Frozen dataclass | Heal application result | proposal_id, success, error, new_risk_score, applied_at |
| `HealRequest` | Frozen dataclass | Heal evaluation request | proposals, trust_scores, nrt_breaches, force_high_risk |

## NRT Policy (`policy/nrt/`)

### Types (`policy/nrt/types.py`)

| Class | Kind | Description | Key Fields |
|-------|------|-------------|------------|
| `NRTResult` | Frozen dataclass | NRT check result | symbol, qss_path, qra_path, breach_type, predicate, note, severity |
| `ShadowRule` | Frozen dataclass | Compiled NRT predicate | rule_for, source_qra_ck, predicate, severity, note |
| `CrossSTAConflict` | Frozen dataclass | Cross-symbol state conflict | symbol_a, symbol_b, variable, note |
| `PatchSuggestion` | Frozen dataclass | Auto-fix patch suggestion | symbol, insert_after_line, atom_to_insert, rationale |
| `BreachCheckRequest` | Frozen dataclass | Breach check request | symbol, qss_path, qra_path |
| `RuleLoadRequest` | Frozen dataclass | Rule load request | symbol |

## CQE Policy (`core/cqe/policy.py`)

| Class | Kind | Description | Key Fields/Defaults |
|-------|------|-------------|---------------------|
| `PrunePolicy` | Frozen dataclass | Pruning config | min_weight=0.05, max_hops=5, max_nodes_visited=2000, max_category_fanout=200 |
| `BoostPolicy` | Frozen dataclass | Weight boost config | enabled=False, jaccard_floor=0.05, jaccard_ceiling=0.95, boost_factor=1.2 |
| `NormalizePolicy` | Frozen dataclass | Normalization config | method="none", preserve_ordering=True |
| `PathGrammarPolicy` | Frozen dataclass | Path grammar constraints | layer_map, allowed_transitions, hub_normalization_enabled=True |
| `CQEPolicy` | Frozen dataclass | Complete CQE policy | version, prune, boost, normalize, grammar |

Constructors: `CQEPolicy.default()`, `CQEPolicy.conservative()`, `CQEPolicy.aggressive()`

## CQE Types (`core/cqe/types.py`)

| Class | Description | Key Fields |
|-------|-------------|------------|
| `CanonicalResult` | Canonicalization result | status, token, candidates |
| `CQEResult` | CQE Kernel output | max_weights, predecessors |
| `CQERefinedResult` | Context-safe refined result | primary_structural, secondary_structural, related_concepts, metadata, strict_token_budget_est, truncated, advisory |
| `CQETier` | Single tier at tau threshold | tau, node_count, refined, advisory |
| `CQEMultiTierResult` | Multi-tier CQE results | core(tau=0.3), extended(tau=0.1), exploratory(tau=0.05), recommendation, entry_token |
| `GraphProtocol` | Pure graph access protocol | neighbors(), edges(), out_degree() |
| `CQERefinerProtocol` | CQE refinement protocol | refine(result, entry_token) -> CQERefinedResult |

## Registry Types (`adapters/registry/types.py`)

| Class | Kind | Description | Key Fields |
|-------|------|-------------|------------|
| `SymbolMetadata` | Frozen dataclass | Semantic type metadata | node_type, is_container, is_executor |
| `FileRecord` | Frozen dataclass | File record | id, file_path, language, fingerprint, fidelity, contract_status |
| `SymbolRecord` | Frozen dataclass | Symbol record | id, canonical_uid, file_id, file_path, symbol_name, symbol_type, content_hash, canonical_hash, role, intent, tags, confidence |
| `MorphismRecord` | Frozen dataclass | Morphism edge record | id, from_symbol_id, to_symbol_id, morphism_type, weight, metadata |
| `SymbolInsertRequest` | Frozen dataclass | Symbol insert request | file_path, symbol_name, symbol_type, role, intent, tags |
| `MorphismInsertRequest` | Frozen dataclass | Morphism insert request | from_symbol_name, to_symbol_name, morphism_type, weight, metadata |

## Shadow Types (`adapters/shadows/types.py`)

| Class | Kind | Description | Key Fields |
|-------|------|-------------|------------|
| `DSLAtom` | Frozen dataclass | DSL operation | op, resource, line_hint, in_finally |
| `ShadowFile` | Frozen dataclass | Shadow file record | symbol, deps, checksum, atoms, risks, truncated, extra_symbols, behavioral_tags, risk_anchors, schema_refs |
| `ShadowReadRequest` | Frozen dataclass | Shadow read request | file_path |
| `ShadowWriteRequest` | Frozen dataclass | Shadow write request | file_path, shadow |

## Trajectory Types (`tda/phase4/trajectory_planner.py`)

| Class | Description | Key Fields |
|-------|-------------|------------|
| `TrajectoryConstraints` | Trajectory constraints | max_energy=10.0, max_friction=0.8, max_hops=20, avoid_symbols |
| `TrajectoryRequest` | Trajectory planning request | start, goal, intent, constraints |
| `CandidateDecision` | Beam search candidate | node, score, energy_hint, is_attractor, friction |
| `RejectedNode` | Rejected candidate | node, reasons |
| `StepDecision` | Single beam search step | step, current, candidates, rejected |

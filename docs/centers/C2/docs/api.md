# C2 API Surface

## Entry Points

### `select_traversal_mode` (function)
- **File**: `core/cqe/traversal_modes.py:70`
- **Signature**: `(node_state: NodeState, current_mode: TraversalMode = FORWARD) -> tuple[TraversalMode, Optional[str]]`
- **Role**: TRANSIENT (forward_magnitude=0.0, backward_tension=0.59, in_degree=8)
- **Description**: Decision tree for mode selection based on node state.
  Returns (mode, trigger_reason).

### `FlowObserver` (class)
- **File**: `tda/flow_observer.py:53`
- **Role**: TRANSIENT (forward_magnitude=2.87, in_degree=4, out_degree=30)
- **Description**: TDA pipeline flow observer. Tracks data shapes through
  pipeline phases 1-4.

### `to_dict` (method)
- **File**: `tda/flow_observer.py:37`
- **Role**: Method of `FlowTrace` in `tda/flow_observer.py`
- **Signature**: `to_dict(self) -> Dict[str, Any]`
- **Description**: Serializes flow trace to dictionary.

---

## Core Classes

### Traversal Orchestrator

#### `TraversalOrchestrator` (class)
- **File**: `core/cqe/traversal_orchestrator.py:66`
- **Role**: CONVERTER (forward_magnitude=12.49, in_degree=8, out_degree=19)
- **Constructor**: `(graph: GraphAdapter, tda_bridge: TDABridge, mi_scores: Dict[str, float], upstream_navigator: Optional[UpstreamNavigator])`
- **Methods**:
  - `get_node_state(node_id: str) -> NodeState`
  - `traverse(start_node, max_depth=3, top_k=5, force_mode=None) -> TraversalResult`
  - `_execute_forward(start_node, max_depth, top_k, telemetry) -> TraversalResult`
  - `_execute_reverse(start_node, max_depth, top_k, telemetry) -> TraversalResult`
  - `_execute_field_guided(start_node, max_depth, top_k, telemetry) -> TraversalResult`
  - `_execute_saddle_escape(start_node, max_depth, top_k, telemetry) -> TraversalResult`
  - `_reconstruct_path(predecessors, start_node, end_node) -> List[str]`

#### `TraversalResult` (dataclass, frozen)
- **File**: `core/cqe/traversal_orchestrator.py:47`
- **Fields**: `start_node: str`, `mode: TraversalMode`, `visited_nodes: Set[str]`, `results: List[tuple]`, `mode_switches: List[ModeSwitchEvent]`, `telemetry: Dict`

### Node State

#### `NodeState` (dataclass, frozen)
- **File**: `core/cqe/node_state.py:34`
- **Role**: CONVERTER (forward_magnitude=0.59, in_degree=12, out_degree=34)
- **Fields**: `node_id, out_degree, in_degree, node_role, field_role, gravity_score, energy_total, field_magnitude`
- **Properties**: `is_sink`, `is_isolated`, `is_critical_point`, `is_high_gravity`, `is_volatile`

#### `NodeRole` (Enum)
- **Values**: `SOURCE`, `SINK`, `HUB`, `BRIDGE`, `LEAF`, `ISOLATED`

#### `FieldRole` (Enum)
- **Values**: `ATTRACTOR`, `REPELLER`, `SADDLE_POINT`, `NOT_CRITICAL_POINT`

#### `classify_node_role(out_degree, in_degree) -> NodeRole`
- Pure function, degree-based classification.

### Traversal Modes

#### `TraversalMode` (Enum)
- **File**: `core/cqe/traversal_modes.py:21`
- **Values**: `FORWARD`, `REVERSE`, `FIELD_GUIDED`, `SADDLE_ESCAPE`

#### `ModeSwitchEvent` (dataclass, frozen)
- **Fields**: `from_mode, to_mode, trigger, node_id, node_state, escape_probability`

#### `should_switch_mode(node_state, current_mode) -> tuple[bool, Optional[TraversalMode], Optional[str]]`

#### `compute_escape_probability(gravity_score, mi_weight, noise_ratio) -> float`

### TDA Bridge

#### `TDABridge` (class)
- **File**: `core/cqe/tda_bridge.py`
- **Role**: CONVERTER (forward_magnitude=7.56, in_degree=20, out_degree=49)
- **Description**: Interfaces with TDA subsystem for node state enrichment.
  Provides `get_node_state`, `get_energy_total`, `get_field_magnitude`,
  `get_field_role`.

### Traversers

#### `CQEKernel` (class)
- **File**: `core/cqe/kernel.py:27`
- **Role**: CORE_ATTRACTOR (forward_magnitude=4.97, in_degree=4, out_degree=5)
- **Static Method**: `query(graph, start, tau=0.05, mi_weight=0.1, mi_scorer=None, top_k=100, use_soft_tau=True) -> CQEResult`
- **Description**: Pure deterministic graph traversal with additive MI scoring.

#### `ReverseTraverser` (class)
- **File**: `core/cqe/reverse_traverser.py:48`
- **Role**: CORE_ATTRACTOR (forward_magnitude=12.71, in_degree=4, out_degree=15)
- **Constructor**: `(graph, tda_bridge, mi_scores)`
- **Method**: `traverse(start_node, max_depth=3, top_k=5) -> ReverseTraversalResult`

#### `ReverseTraversalResult` (dataclass, frozen)
- **Fields**: `start_node, visited_nodes, paths, top_escapes`

#### `FieldGuidedTraverser` (class)
- **File**: `core/cqe/field_guided_traverser.py:37`
- **Role**: CONVERTER (forward_magnitude=9.53, in_degree=8, out_degree=20)
- **Constructor**: `(graph, tda_bridge)`
- **Methods**: `traverse(start_node, mode=DESCENT, max_steps=10) -> FieldGuidedResult`, `find_nearest_attractor(start_node, max_steps)`, `escape_repeller(start_node, max_steps)`

#### `FieldGuidedResult` (dataclass, frozen)
- **Fields**: `start_node, mode, visited_nodes, trajectory, endpoint, endpoint_role, total_energy_change`

#### `FieldNavigationMode` (Enum)
- **Values**: `DESCENT`, `ASCENT`

#### `SaddleEscapeTraverser` (class)
- **File**: `core/cqe/saddle_escape_traverser.py`
- **Role**: CORE_ATTRACTOR (forward_magnitude=10.57, in_degree=4, out_degree=10)
- **Method**: `escape(saddle_node, max_steps) -> SaddleEscapeResult`

### Upstream Navigator

#### `UpstreamNavigator` (class)
- **File**: `core/cqe/upstream_navigator.py:60`
- **Constructor**: `(anisotropic_fields_path, registry_db_path)`
- **Method**: `escape_sink(node_id) -> EscapeResult`

#### `EscapeResult` (dataclass, frozen)
- **Fields**: `escape_to, confidence, reason, upstream_sources`

#### `UpstreamSource` (dataclass, frozen)
- **Fields**: `symbol, tension, distance, source_type, forward_magnitude, score`

### Policy System

#### `CQEPolicy` (dataclass, frozen)
- **File**: `core/cqe/policy.py:177`
- **Role**: EMITTER (forward_magnitude=19.69, in_degree=4, out_degree=19)
- **Fields**: `version, prune: PrunePolicy, boost: BoostPolicy, normalize: NormalizePolicy, grammar: PathGrammarPolicy`
- **Factory Methods**: `default()`, `conservative()`, `aggressive()`

#### `PrunePolicy` (dataclass, frozen)
- **Fields**: `min_weight, max_hops, max_nodes_visited, max_category_fanout`

#### `BoostPolicy` (dataclass, frozen)
- **Fields**: `enabled, jaccard_floor, jaccard_ceiling, boost_factor`

#### `NormalizePolicy` (dataclass, frozen)
- **Fields**: `method, preserve_ordering`

#### `PathGrammarPolicy` (dataclass, frozen)
- **Fields**: `layer_map, allowed_transitions, hub_normalization_enabled`

### Transforms

#### `GraphTransform` (base class)
- **File**: `core/cqe/transforms.py:12`
- **Method**: `transform(graph) -> GraphProtocol`

#### `HubNormalizer(GraphTransform)`
- **Transform**: Applies entropy suppression to hub nodes with high fanout.

#### `TopKPruner(GraphTransform)`
- **Transform**: Limits edges per node to `max_edges` (default 200).

### Canonical Layer

#### `CanonicalLayer` (class)
- **File**: `core/cqe/canonical.py:23`
- **Role**: CORE_ATTRACTOR (forward_magnitude=15.24, in_degree=4, out_degree=10)
- **Constructor**: `(symbol_table, aliases=None, max_edit_distance=1)`
- **Method**: `resolve(query) -> CanonicalResult`

#### `CanonicalResult` (dataclass)
- **File**: `core/cqe/types.py:16`
- **Fields**: `status, token, candidates`

### Refiner

#### `DefaultCQERefiner` (class, implements `CQERefinerProtocol`)
- **File**: `core/cqe/refiner.py:13`
- **Role**: CONVERTER (forward_magnitude=8.55, in_degree=12, out_degree=10)
- **Constructor**: `(node_metadata_fetcher, max_tokens=4000, bytes_per_token_est=4.0)`
- **Method**: `refine(result: CQEResult, entry_token) -> CQERefinedResult`

#### `CQERefinerProtocol` (Protocol)
- **File**: `core/cqe/types.py:92`
- **Method**: `refine(result, entry_token) -> CQERefinedResult`

#### `CQERefinedResult` (dataclass)
- **Fields**: `primary_structural, secondary_structural, related_concepts, metadata, strict_token_budget_est, truncated, advisory`

### Types

#### `CQEResult` (dataclass)
- **File**: `core/cqe/types.py:28`
- **Fields**: `max_weights: Dict[str, float]`, `predecessors: Dict[str, Optional[str]]`

#### `CQETier` (dataclass)
- **Fields**: `tau, node_count, refined, advisory`

#### `CQEMultiTierResult` (dataclass)
- **Fields**: `core, extended, exploratory, recommendation, entry_token`

#### `GraphProtocol` (Protocol)
- **Methods**: `neighbors(node)`, `edges(node)`, `out_degree(node)`

### Flow Observers

#### `FlowObserver` (class, core/cqe)
- **File**: `core/cqe/flow_observer.py:91`
- **Constructor**: `(enabled=False)`
- **Methods**: `start_trace(query_id, query_params)`, `observe(query_id, stage, data, metadata)`, `get_trace(query_id)`, `clear_trace(query_id)`, `get_all_traces()`, `clear_all()`

#### `FlowTrace` (dataclass, core/cqe)
- **Fields**: `query_id, start_time, snapshots: List[FlowSnapshot]`
- **Methods**: `add_snapshot(stage, data, metadata)`, `to_dict()`

#### `FlowSnapshot` (dataclass, core/cqe)
- **Fields**: `stage, timestamp, data_shape, metadata`

#### `FlowObserver` (class, tda/)
- **File**: `tda/flow_observer.py:53`
- **Methods**: `observe_phase2_output`, `observe_pass1_output`, `observe_pass2_output`, `observe_pass3_output`, `observe_pass4_output`, `write_trace`, `write_all_traces`, `get_trace`, `print_trace_summary`

#### `DataSnapshot` (dataclass, frozen, tda/)
- **Fields**: `stage, timestamp, symbol, shape, sample_data`

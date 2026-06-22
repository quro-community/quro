# C1 Data Flow — Leaf-Dominated Fanout Utility Layer

## Data Flow Through Graph Adapters

### Primary Data Path: TDA Pipeline → GraphInterface

```
TDA Pipeline (C0)
    │
    ▼
GraphAdapter.create(field_data_path)
    │
    ├── 1. adjacency_cache.pkl ──► FileGraphAdapter ◄── FASTEST
    ├── 2. field_data_cache.pkl ──► FieldDataGraphAdapter
    ├── 3. manifold_states.jsonl ──► ManifoldStatesGraphAdapter
    ├── 4. registry.db ──► SQLiteGraphAdapter (IO-level)
    └── 5. graph_events.jsonl ──► StreamingGraphAdapter ◄── SLOWEST
    │
    ▼
GraphInterface
    │
    ├── get_out_neighbors(node) → List[str]
    ├── get_in_neighbors(node) → List[str]
    ├── get_all_nodes() → List[str]
    ├── has_node(node) → bool
    ├── num_nodes() → int
    ├── num_edges() → int
    ├── get_edge_weight(src, dst) → Optional[float]
    ├── bfs(start, max_depth, direction) → List[(node, depth)]
    ├── find_path(src, dst) → Optional[List[str]]
    └── subgraph(nodes) → SubgraphView
```

### CQE Traversal Data Path

```
CQE Orchestrator (C0)
    │
    ▼
RegistryAdapter ──► CQEGraphAdapter (bridge)
    │                     │
    │                     ├── neighbors(node) → (neighbor, weight)
    │                     │    └── MI adjustment ✓
    │                     │    └── Top-K fanout pruning (K=10, fanout>12)
    │                     ├── edges(node) → GraphEdge[]
    │                     └── out_degree(node) → int
    │
    ▼
CQE Kernel
```

### CQE GraphAdapter MI Adjustment Flow

```
neighbors(node)
    │
    ▼
get_edges_from(node) ──► edges list
    │
    ▼
MI Adjuster available?
    ├── No → Use raw weights
    └── Yes → For each edge:
         │
         ├── kind == "contains" → Skip MI adjustment
         └── else → adjusted = weight * mi_adjuster.compute_adjustment_factor(src, dst)
    │
    ▼
Fanout > 12?
    ├── No → Return all edges
    └── Yes → Sort by weight DESC, keep top 10
    │
    ▼
Yield (dst, adjusted_weight)
```

### Visualization Data Flow

```
TDA Data Files (C0/.quro_context/tda/)
    │
    ▼
VisualizationService.initialize(workspace)
    │
    ├── Checks .quro_context/tda/ exists
    └── Creates .quro_context/tda/visualizations/
    │
    ▼
load_tda_data(workspace_root)
    │
    ├── positions: Dict[str, (x, y)]
    ├── energies: Dict[str, float]
    ├── roles: Dict[str, str]
    ├── field_directions: Dict[str, (dx, dy)]
    └── field_magnitudes: Dict[str, float]
    │
    ▼
FieldPlotter
    │
    ├── plot_energy_heatmap() → energy_heatmap.png
    ├── plot_gradient_field() → gradient_field.png
    ├── plot_attractor_basins() → attractor_basins.png
    ├── plot_trajectory() → trajectory.png
    ├── plot_coherence_analysis() → coherence_analysis.png
    └── create_summary_dashboard() → field_dashboard.png
```

### SQLite Persistence Flow (Index Builder)

```
Index Builder
    │
    ▼
SQLiteRegistryAdapter(registry.db)
    │
    ├── save_node(GraphNode) ──► nodes table + aliases table
    ├── save_edge(GraphEdge) ──► edges table
    ├── get_node(id) → GraphNode | None
    ├── get_edges_from(id) → GraphEdge[]
    ├── node_exists(id) → bool
    ├── get_all_nodes() → GraphNode[]
    ├── get_all_edges() → GraphEdge[]
    └── find_symbol_aliases(name) → alias metadata[]
    │
    ▼
Registry Data Store
```

### DuckDB Storage Layer (TDA Pipeline Unified Storage)

```
CLI: quro tda-pipeline 1 --backend duckdb [--incremental]
    │
    ▼
StorageCoordinator(db_path)             — Connection lifecycle manager
    │                                      (single-writer, WAL disabled)
    ▼
MigrationRunner                          — Schema version detection + migration
    │                                      Creates tables via TdaSchema.all_tables()
    │                                      Imports legacy JSONL/PKL data if tables empty
    ▼
TdaSchema                                — Declarative DDL (2 versions)
    ├── v1: events, nodes, edges_weighted, manifold_states
    └── v2: energy_states, anisotropic_fields, adjacency,
    │        phase_completion (UNUSED), semantic_centers, _meta
    │
    ▼
DuckDBPhase1Processor                    — Phase 1: SQL-based BFS traversal
    │                                      50-100x faster than Python BFS
    │
    ├── Step 1: _load_graph_data()        ──► SQLite registry.db → DuckDB temp tables
    ├── Step 2: _compute_bfs_paths()      ──► Frontier-based BFS (max_depth=3, pure SQL)
    └── Step 3: _build_and_insert_events() ──► SQL INSERT ... SELECT (bulk, 1 transaction)
    │
    ▼
DuckDBEventWriter                        — Streaming buffered writer (batch=1000)
    │                                     INSERT OR IGNORE for idempotency
    ▼
DuckDBGraphAdapter                       — Read-only CQE query adapter
    │                                     Queries nodes + edges_weighted tables
    ▼
Phase 2 / 2.5 / 3.5 / 3.6 writes        — Write energy_states, anisotropic_fields,
                                           semantic_centers etc. via StorageCoordinator
```

#### Incremental Processing — Current Status

| Backend | Incremental Support | Mechanism | Status |
|---------|-------------------|-----------|--------|
| **JSONL** | ✅ Working | `_load_processed_symbols()` filters already-processed symbol IDs | `Phase1BatchProcessor` |
| **DuckDB** | ❌ `NotImplementedError` | Planned: filter symbols already in `events` table by `query_id` | `DuckDBPhase1Processor.run()` |
| `phase_completion` table | ❌ Unused | Declared in schema v2, never written | Future checkpoint/resume |

### Cross-Center Data Flows

| Flow | Source Center | Sink Center | Bridge Symbols | Mechanism |
|------|--------------|-------------|----------------|-----------|
| Graph adapter consumption | C1 → C0 | Hub | `MemoryRegistryAdapter`, `DynamicsState` | TDA pipeline reads graph data for center detection |
| CQE traversal | C0 → C1 | CQE uses adapters | `CQEGraphAdapter`, `RegistryAdapter` | CQE Orchestrator uses graph adapters for traversal |
| TDA enrichment | C1 → C7 | Chain layer | `upsert_node`, `_process_event` | TDA operations on graph data |
| Index building | C4 → C1 | Registry | `SQLiteRegistryAdapter` | Index builder persists to SQLite |
| DuckDB Phase 1 | C0 → C1 | TDA pipeline | `DuckDBPhase1Processor` | SQL-based BFS, bulk-insert events |
| DuckDB Storage | C1 internal | Storage layer | `StorageCoordinator`, `MigrationRunner` | Schema management, legacy import |
| Shared sinks | All centers → C3, C8 | Sink layer | `MemoryRegistryAdapter`, `verify_symbol_integrity` | Common persistence and verification |

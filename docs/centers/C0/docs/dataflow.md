# C0: Data Flow

> **Center:** C0 | **Archetype:** Hub | **Symbols:** 919
> **Status:** Populated — first exploration session complete

## Overview

C0 orchestrates data flow through a multi-stage pipeline: scanning → indexing → CQE query execution → TDA analysis. Data enters through the service layer, flows through orchestrators and pipeline stages, and exits to downstream centers for persistence and further processing.

## Main Data Flows

### Flow 1: Workspace Scanning (ScannerService)

```
CLI/MCP → QuroV3Service.scan_workspace()
  → ScannerService.scan_workspace()
    → ScannerOrchestrator.scan_workspace()
      ├── ScannerGateChain.validate_file()      — Gate 1: file filter
      ├── PythonASTParser.parse()               — Parse source
      ├── FeatureExtractor.extract()            — Extract features
      ├── ScannerGateChain.validate_symbol()    — Gate 2: symbol filter
      ├── ScannerGateChain.validate_features()  — Gate 3: feature gate
      └── ScannerMemoryAdapter.save_scan_result() → persistence
    → IndexBuilder.build_index()
      ├── DefaultHeuristicEnricher              — Base enrichment
      ├── HubPressureEnricher                   — High-fanout hub detection
      ├── PathEntropyEnricher                   — Ambiguous symbol detection
      ├── RoleEnricher                          — Architectural role classification
      ├── IntentEnricher                        — Semantic intent classification
      └── SQLiteRegistryAdapter                 → C1 storage (registry.db)
```

### Flow 2: CQE Query Execution (CQEService)

```
CLI/MCP → QuroV3Service.cqe_query()
  → CQEService.query()
    → CQEOrchestrator.query()
      ├── GraphAdapter (I/O — loads from SQLite/DuckDB)    ← C1
      ├── HubNormalizer.transform()                         — Graph enrichment
      ├── TopKPruner.transform()                            — Pruning
      ├── CQEKernel.query()                                 — Max-Product Dijkstra
      └── DefaultCQERefiner.refine()                        — Result refinement

QuroV3Service.cqe_query_with_mode()
  → Adds traversal mode selection (depth_first/breadth_first/balanced)
  → Resolves symbol IDs via _resolve_symbol_id()
  → Returns enriched result metadata

QuroV3Service.cqe_query_multi_tier()
  → Runs multiple CQE queries at different tau thresholds
  → Merges results into unified response
```

### Flow 3: TDA Pipeline Analysis (TDAService)

```
CLI/MCP → quro tda-pipeline 1 [--backend duckdb] [--incremental]
  │
  ├── [Backend: jsonl] → Phase1BatchProcessor (Python BFS)
  │     Reads SQLite registry.db → BFS per symbol (max_depth=3, tau=0.05)
  │     Writes events to graph_events.jsonl via GraphEventLogger
  │     Incremental: --incremental flag skips symbols with existing QUERY_METADATA events
  │
  └── [Backend: duckdb] → DuckDBPhase1Processor (SQL BFS, ~50-100x faster)
        Phase 1 DuckDB Flow:
         1. StorageCoordinator.ensure_initialized() → MigrationRunner
            → Creates quro_tda.duckdb with v1/v2 schema
         2. DuckDBPhase1Processor.run()
            ├── Step 1: _load_graph_data() — Load ALL nodes + edges from SQLite
            │     registry.db into DuckDB temp tables _nodes and _edges
            │     (single round-trip, not per-symbol)
            ├── Step 2: _compute_bfs_paths() — Frontier-expansion BFS in SQL
            │     └── For each depth level (0..max_depth):
            │          1. Find ALL outgoing edges from current frontier → _edge_events
            │          2. Find NEW unvisited targets → next frontier
            │     ⚠ Incremental mode raises NotImplementedError in DuckDB backend
            └── Step 3: _build_and_insert_events() — Pure SQL INSERT...SELECT
                  ├── QUERY_METADATA (Python loop, ~3000 rows)
                  ├── NODE_VISIT (streaming SQL json_object(), ~867k rows)
                  └── EDGE_TRAVERSE (streaming SQL json_object(), ~9.2M rows)

  → Phase2Orchestrator.run()
      ├── Phase-2 Pass 1: AtomicFeatureDistiller
      │     Input:  graph_events.jsonl (event stream)
      │     Output: SparseAdjacencyMatrix, SymbolFrequencyMap,
      │             TauSurvivalTable, EdgeTypeDistribution
      │
      ├── Phase-2 Pass 2: TopologyInferenceEngine.infer()
      │     Input:  adjacency, frequency, tau_survival, edge_types
      │     Output: centrality, betweenness, clustering_coeff
      │
      ├── Phase-2 Pass 3: SemanticProjector.project()
      │     Input:  topology + signal data
      │     Output: SymbolManifoldState (manifold_states.jsonl)
      │
      ├── Phase-2 Pass 4: enrich_with_field_metrics()
      │     Input:  SymbolManifoldState[]
      │     Kernel: EnergyFunctional + FieldKernel
      │     Output: enriched manifold states (energy, field_role, mass, friction)
      │
      ├── Phase-2 Pass 4.5: Offline Physics Integration
      │     Input:  offline_energy.json (from Phase-2.5)
      │     Merge:  replaces energy/field_role/field_magnitude/mass/friction
      │
      └── Phase-2 Output: adjacency_cache.pkl → C2/C4/SC70

    → Phase3Orchestrator.run()
      ├── Pass 1: RoleInterpreter.interpret()
      ├── Pass 2: RiskStabilityMapper.map_stability()
      ├── Pass 3: CognitiveAffordanceEngine.detect_affordances()
      └── Pass 4: ContextInjectionFormatter.format_context()
      Output: cognitive_contexts.jsonl

    → Phase35Orchestrator.run()
      └── CenterDetector.detect_centers()
            ├── GraphAdapter.create() — Load adjacency
            ├── Seed communities (top centrality + energy diversity)
            ├── Label propagation (weighted by energy similarity)
            ├── Prune small communities
            ├── Derive SemanticCenter with archetypes + entry points
            └── Build Structural Coupling Graph (SCG)
            Output: semantic centers → partitioning

    → TDA Service Endpoints
      ├── tda_find_upstream()     — Controlled backward navigation
      ├── tda_escape_sink()        — Escape from sink nodes
      ├── tda_classify_role()     — TDA role classification
      └── tda_get_field_vector()  — Field vector retrieval
```

### Flow 4: Orchestrator Sub-flows

#### LSH Fingerprint Pipeline (LSHOrchestrator)
```
LSHOrchestrator.compute_and_store()
  ├── _tokenize(content) → set of tokens
  ├── MinHashLSH.compute_signature(tokens) → LSHSignature
  └── ManifoldAdapter.insert_node() → C8 persistence

LSHOrchestrator.compute_similarity(symbol_a, symbol_b)
  ├── ManifoldAdapter.get_node(symbol_a) → C8
  ├── ManifoldAdapter.get_node(symbol_b) → C8
  └── MinHashLSH.compute_similarity(sig_a, sig_b) → float
```

#### Morph Drift Detection (MorphOrchestrator)
```
MorphOrchestrator.detect_drift(symbol, old_fp, new_fp)
  ├── ManifoldEngine.compute_drift(old_bands, new_bands) → DriftResult
  └── ManifoldAdapter.record_drift() → C8 persistence

MorphOrchestrator.compute_topology(symbol, fingerprint)
  ├── ManifoldEngine.compute_betti_numbers(fingerprint) → BettiResult
  └── ManifoldAdapter.get_node() (metadata update)
```

#### Skeleton Graph (SkeletonOrchestrator)
```
SkeletonOrchestrator.build_and_store_graph(nodes, edges)
  ├── Build adjacency lists (in/out)
  ├── SkeletonEngine.detect_cycles(kernel_graph) → CycleResult
  └── SkeletonAdapter.save_graph(graph) → C7 persistence
```

#### Phantom Simulation (PhantomOrchestrator)
```
PhantomOrchestrator.simulate_from_shadow(file_path)
  ├── ShadowAdapter.read_shadow(request) → C7
  ├── _parse_threads(shadow) → ThreadSequence[]
  └── PhantomKernel.simulate(threads, config) → PhantomResult[]
```

## Cross-Center Data Flow

```
C0 (Hub)                             Downstream Centers
───                                  ─────────────────
ScannerOrchestrator + IndexBuilder → C1 (Storage: SQLiteRegistryAdapter)
CQEOrchestrator                     → C1 (Adapter: SQLiteGraphAdapter / DuckDBGraphAdapter)
                                → C3 (Shared sinks: MemoryRegistryAdapter, verify_symbol_integrity)
Phase35Orchestrator (Center Detection) → C4 (CQE quality reporting)
CQEService/TDAService              → C5 (Policy: CQEPolicy, TrustWeights)
                                → C6 (Type system: SymbolInfo, StructuralTags)
ShadowDraftManager                 → C7 (Shadow: ShadowAdapter)
SkeletonOrchestrator               → C7 (Skeleton: SkeletonAdapter)
LSHOrchestrator/MorphOrchestrator  → C8 (LSH index: ManifoldAdapter)
```

## Data Persistence Locations

| Data | Location | Format |
|------|----------|--------|
| Graph events (JSONL path) | `.quro_context/tda/phase1/graph_events.jsonl` | JSONL (20GB) |
| Graph events (DuckDB path) | `.quro_context/quro_tda.duckdb` → `events` table | DuckDB |
| Node + edge imports | `.quro_context/quro_tda.duckdb` → `nodes`, `edges_weighted` | DuckDB |
| Adjacency cache (file) | `.quro_context/tda/adjacency_cache.pkl` | Pickle |
| Adjacency (DuckDB) | `.quro_context/quro_tda.duckdb` → `adjacency` | DuckDB |
| Manifold states (file) | `.quro_context/tda/phase2/manifold_states.jsonl` | JSONL |
| Manifold states (DuckDB) | `.quro_context/quro_tda.duckdb` → `manifold_states` | DuckDB |
| Energy states | `.quro_context/quro_tda.duckdb` → `energy_states` | DuckDB |
| Anisotropic fields | `.quro_context/quro_tda.duckdb` → `anisotropic_fields` | DuckDB |
| Semantic centers | `.quro_context/quro_tda.duckdb` → `semantic_centers` | DuckDB |
| Phase completion | `.quro_context/quro_tda.duckdb` → `phase_completion` | DuckDB |
| Schema version | `.quro_context/quro_tda.duckdb` → `_meta` | DuckDB |
| Registry DB | `.quro_context/registry.db` | SQLite |
| TDA DB (legacy) | `.quro_context/tda_index.db` | SQLite |

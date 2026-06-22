# C0: Architecture

> **Center:** C0 | **Archetype:** Hub | **Symbols:** 919
> **Status:** Populated — first exploration session complete
> **Agent:** quro-center-explorer v2.0.0

## Overview

C0 is the **Core Orchestration Layer** — a hub center that coordinates the full Quro semantic analysis pipeline. It follows a **layered orchestration architecture**: requests enter through a service layer, route through a central registry, and are dispatched to specialized orchestrators that coordinate pipeline stages.

## Architecture Layers

### 1. Service Layer (entry points)

The service layer provides the public API surface for C0. All services extend `BaseService` and register with `ServiceRegistry`.

| Service | Role | Registration |
|---------|------|-------------|
| **QuroV3Service** | Main MCP entry point — wraps scan, CQE, TDA, and management operations | Registered on import |
| **CQEService** | CQE query execution — wraps CQE orchestrator and kernel | Registered on import |
| **TDAService** | TDA topological analysis — wraps phase pipeline and field analysis | Registered on import |
| **ScannerService** | Workspace scanning and index building — wraps scanner orchestrator | Registered on import |
| **VisualizationService** | Visualization and reporting | Registered on import |

Key pattern: `ServiceRegistry` is a singleton class with class-level `_services` dict. Services auto-register on import. Access via `ServiceRegistry.get("cqe")`, `ServiceRegistry.get("tda")`, etc.

### 2. Orchestrator Layer (core logic)

Each orchestrator follows a consistent pattern:
- **Adapter injection**: Adapter (I/O) is injected via constructor
- **Kernel composition**: Pure computation is delegated to kernel classes
- **Pipeline orchestration**: Methods follow: Load (adapter) → Transform → Compute (kernel) → Persist (adapter)

| Orchestrator | Forward Mag | Role | Domain |
|-------------|-------------|------|--------|
| **CQEOrchestrator** | 43.9 | CONVERTER | CQE query — Graph Adapter → HubNormalizer → TopKPruner → Max-Product Dijkstra |
| **PhantomOrchestrator** | 29.6 | EMITTER | Monte Carlo simulation of shadow files |
| **ServiceRegistry** | 27.7 | EMITTER | Central service registry (singleton, class-level) |
| **BaseService** | 20.0 | EMITTER | Abstract base service (ABC) |
| **MorphOrchestrator** | 19.1 | EMITTER | Morphism drift detection between LSH fingerprints |
| **LSHOrchestrator** | 17.1 | EMITTER | LSH fingerprint computation and similarity |
| **SkeletonOrchestrator** | 16.6 | EMITTER | Dependency graph skeleton and cycle detection |
| **Phase35Orchestrator** | 13.6 | CONVERTER | Phase-3.5 center detection pipeline |
| **Phase3Orchestrator** | 13.6 | CONVERTER | Phase-3 cognitive compilation (4 passes) |
| **Phase2Orchestrator** | 12.8 | CONVERTER | Phase-2 manifold inference (3+1 passes) |
| **TraversalOrchestrator** | 12.5 | CONVERTER | Graph traversal orchestration |
| **ScannerOrchestrator** | 5.9 | CONVERTER | File scanning with gate chain |

### 3. TDA Pipeline (deep analysis)

The TDA pipeline is a multi-phase analysis pipeline:

```
Phase-1 (Graph Event Collection) — OFFLINE BATCH
  ├── Backend A: Phase1BatchProcessor (Python BFS)
  │     Reads SQLite registry → BFS traversal per symbol → writes graph_events.jsonl
  │     Supports --incremental (skips already-processed symbols via QUERY_METADATA scan)
  └── Backend B: DuckDBPhase1Processor (SQL BFS, ~50-100x faster)
        Loads registry into DuckDB temp tables ONCE
        → Frontier-expansion BFS in pure SQL (avoids combinatorial explosion)
        → Generates events via streaming INSERT ... SELECT with json_object()
        → Writes directly to events table in quro_tda.duckdb
        ⚠ Incremental mode NOT yet supported for DuckDB backend

Phase-2 (Manifold Inference)
  ├── Pass 1: AtomicFeatureDistiller — Event stream → adjacency matrix + frequency map + tau survival
  ├── Pass 2: TopologyInferenceEngine — Centrality, betweenness, clustering coefficient
  ├── Pass 3: SemanticProjector — Manifold position embedding
  ├── Pass 4: FieldEnrichment — Energy potential, field role, mass, friction
  └── Pass 4.5: Offline Physics Integration — Phase 2.5 offline energy merge

Phase-3 (Cognitive Compilation)
  ├── Pass 1: RoleInterpreter — Cognitive role classification
  ├── Pass 2: RiskStabilityMapper — Stability class + mutation risk
  ├── Pass 3: CognitiveAffordanceEngine — Affordance detection + attention weight
  └── Pass 4: ContextInjectionFormatter — Context formatting

Phase-3.5 (Center Detection)
  └── CenterDetector — Community detection → label propagation → center derivation + SCG
```

### 4. I/O Adapters (boundary contracts)

C0 uses several adapter interfaces that couple to downstream centers:
- **SQLiteGraphAdapter** / **SQLiteTDAGraphAdapter** → C1 storage
- **ManifoldAdapter** → C1/C8 storage (LSH fingerprints, drift history)
- **DuckDBGraphAdapter** → C1 storage (preferred over SQLite, read-only for CQE)
- **ShadowAdapter** → C7 shadow draft persistence
- **SkeletonAdapter** → C7 skeleton graph persistence
- **GraphAdapter** → C2/SC70 adjacency cache loading

### 5. DuckDB Storage Layer (unified TDA storage)

All TDA pipeline phases converge on a single DuckDB database at `.quro_context/quro_tda.duckdb`:

**Schema versioning** (`storage/schema.py` — `TdaSchema`):
- v1: `events`, `nodes`, `edges_weighted`, `manifold_states` tables
- v2: `energy_states`, `anisotropic_fields`, `adjacency`, `phase_completion`, `semantic_centers`
- Version tracked in `_meta` table; migrations run via `MigrationRunner`

**Connection lifecycle** (`storage/coordinator.py` — `StorageCoordinator`):
- Single writer at a time; WAL disabled (batch pipeline)
- Creates DB + runs migration on first open
- Connection pool semantics: one connection per instance

**Legacy data import** (`storage/migration.py` — `MigrationRunner._import_legacy_data_if_empty`):
- Automatically imports from `registry.db`, `graph_events.jsonl`, `manifold_states.jsonl`, `offline_energy.json`, `adjacency_cache.pkl` if DuckDB tables are empty

## Key Design Patterns

### Orchestration-only Invariant
All orchestrators follow the invariant: **Orchestration only, no business logic**. Business logic lives in kernel classes (e.g., `CQEKernel`, `SkeletonEngine`, `ManifoldEngine`, `MinHashLSH`, `PhantomKernel`).

### Pipeline State Management
Pipeline state flows through two parallel paths depending on the backend choice:

**JSONL path** (legacy):
```
graph_events.jsonl (20GB, Phase-1) → adjacency_cache.pkl → manifold_states.jsonl → cognitive_contexts.jsonl
```

**DuckDB path** (preferred, unified storage):
```
quro_tda.duckdb
  ├── events table          — Phase-1 graph events (direct SQL generation, ~50-100x faster)
  ├── nodes + edges_weighted — Imported from registry.db via MigrationRunner
  ├── manifold_states       — Phase-2 manifold inference results
  ├── energy_states         — Phase-2.5 physics enrichment
  ├── anisotropic_fields    — Phase-2.5 field tensors
  ├── adjacency             — Phase-2 adjacency cache (from adjacency_cache.pkl)
  ├── semantic_centers      — Phase-3.5 center detection
  └── phase_completion      — Run tracking
```

### Energy Profile
- **Highest energy** (forward magnitude): CQEOrchestrator (43.9)
- **Emitter cluster**: Morph, Skeleton, Phantom, LSH share identical backward_tension (0.075) and in_degree (4) — same adapter pattern
- **Stable attractor candidates**: TopologyInferenceEngine, Phase2Orchestrator, Phase3Orchestrator

# C0: Dependencies

> **Center:** C0 | **Archetype:** Hub | **Symbols:** 919
> **Status:** Populated — first exploration session complete

## Overview

C0 has deep internal dependencies between its service layer, orchestrators, and pipeline stages, plus strong cross-center couplings to 7 downstream centers. The center belongs to the **SC70** tight-coupling cluster (must-change-together with C1, C3, C7, C8).

## Internal Dependency Graph

```
QuroV3Service
  ├── CQEService (wraps → CQEOrchestrator → CQEKernel)
  ├── TDAService (wraps → QuroV3Service.tda_* methods)
  ├── ScannerService (wraps → ScannerOrchestrator → ScannerGateChain → PythonASTParser → FeatureExtractor)
  ├── ServiceRegistry (managed by)
  ├── IndexBuilder (from scan_workspace)
  └── CQEPipelineBuilder (builds → ScannerOrchestrator + IndexBuilder + QuroV3Service)

CQEOrchestrator
  ├── GraphProtocol / SQLiteGraphAdapter / SQLiteTDAGraphAdapter / DuckDBGraphAdapter
  ├── CQEPolicy
  ├── CQEKernel (pure computation)
  ├── HubNormalizer (graph transform)
  └── TopKPruner (graph transform)

Phase2Orchestrator
  ├── AtomicFeatureDistiller (Pass 1)
  ├── TopologyInferenceEngine (Pass 2)
  ├── SemanticProjector (Pass 3)
  ├── enrich_with_field_metrics (Pass 4 — FieldKernel + EnergyFunctional)
  └── Offline Physics Integration (Pass 4.5 — Phase 2.5 data)

Phase3Orchestrator
  ├── RoleInterpreter (Pass 1)
  ├── RiskStabilityMapper (Pass 2)
  ├── CognitiveAffordanceEngine (Pass 3)
  └── ContextInjectionFormatter (Pass 4)

Phase35Orchestrator
  └── CenterDetector
        ├── GraphAdapter (C2)
        ├── build_coupling_graph (SCG)
        ├── detect_structural_clusters
        └── compute_inter_center_coupling

MorphOrchestrator
  ├── ManifoldAdapter (I/O)
  └── ManifoldEngine (pure — Betti numbers, drift detection)

LSHOrchestrator
  ├── ManifoldAdapter (I/O)
  └── MinHashLSH (pure — signature computation, similarity)

SkeletonOrchestrator
  ├── SkeletonAdapter (I/O)
  └── SkeletonEngine (pure — cycle detection, dependency traversal)

PhantomOrchestrator
  ├── ShadowAdapter (I/O)
  └── PhantomKernel (pure — Monte Carlo simulation)
```

## Cross-Center Dependencies

### Structural Coupling Scores (from TDA Landscape)

| Coupled Center | Coupling Score | Mechanism | Role |
|---------------|---------------|-----------|------|
| **C1** (Fanout) | **674.4** | 10 bridge symbols → 10 shared sinks | Storage adapter contract |
| **C8** (Sink) | **672.3** | 10 bridge symbols → 10 shared sinks | LSH index persistence |
| **C3** (Sink) | **635.9** | 10 bridge symbols → 10 shared sinks | File I/O boundary |
| **C7** (Chain) | **632.9** | 10 bridge symbols → 10 shared sinks | Shadow/draft + skeleton |
| **C5** (Hub) | **407.9** | 10 bridge symbols → 10 shared sinks | Policy configuration |
| **C4** (Hub) | **199.8** | 10 bridge symbols → 10 shared sinks | CQE quality reporting |
| **C6** (Chain) | **159.0** | 10 bridge symbols → 10 shared sinks | Type system |

### Shared Sink Symbols (Bridge Points)
The most significant shared sink symbols across the SC70 cluster:
- `sym::MemoryRegistryAdapter`
- `sym::verify_symbol_integrity::tools::504`
- `sym::DynamicsState`
- `sym::upsert_node`
- `sym::_process_event`
- `sym::argument`

### Tight-Coupling Cluster SC70
C0 belongs to **SC70** (832 symbols across C0, C1, C3, C7, C8). This cluster **must change together** — any significant refactor of the orchestration layer will likely require coordinated changes in storage (C1), file I/O (C3), shadow/draft tools (C7), and LSH indexing (C8).

## Adapter Boundaries (I/O Layer)

C0 interacts with downstream centers through these adapter interfaces:

| Adapter | Used By | Downstream Center | Persistence Format |
|---------|---------|------------------|-------------------|
| `SQLiteGraphAdapter` | CQEOrchestrator | C1 | `.quro_context/cqe_index.db` |
| `SQLiteTDAGraphAdapter` | CQEOrchestrator | C1 | `.quro_context/cqe_index.db` + `tda_index.db` |
| `DuckDBGraphAdapter` | CQEOrchestrator | C1 | `.quro_context/quro_tda.duckdb` |
| `SQLiteRegistryAdapter` | ScannerService, IndexBuilder | C1 | `.quro_context/registry.db` |
| `MemoryAdapter` (Scanner) | ScannerOrchestrator | C1 | In-memory (transient) |
| `ManifoldAdapter` | LSHOrchestrator, MorphOrchestrator | C8 | Manifold store |
| `ShadowAdapter` | PhantomOrchestrator | C7 | Shadow file store |
| `SkeletonAdapter` | SkeletonOrchestrator | C7 | Skeleton graph store |
| `GraphAdapter` | CenterDetector | C2/SC70 | `.quro_context/tda/adjacency_cache.pkl` |

## Pipeline Data Dependencies

```
Phase-1 (C2 traversal) → graph_events.jsonl (20GB)
  → Phase-2 Pass 1 → SparseAdjacencyMatrix + SymbolFrequencyMap + TauSurvivalTable
    → Phase-2 Pass 2 → topology metrics
      → Phase-2 Pass 3 → manifold_states.jsonl
        → Phase-2 Pass 4 → enriched manifold states
          → Phase-3 → cognitive_contexts.jsonl
            → Phase-3.5 → semantic centers + SCG
              → MCP Server / CLI

Phase-2.5 (C1/C8 offline physics) → offline_energy.json
  → Phase-2 Pass 4.5 (merge into manifold states)

Phase-2 cache → adjacency_cache.pkl
  → Phase-3.6 (CenterDetector)
  → Phase-4 (Trajectory planning)
  → MCP Server
```

## External (Non-Center) Dependencies

| Dependency | Used By | Purpose |
|-----------|---------|---------|
| `SQLite` | CQEOrchestrator, ScannerService, IndexBuilder | Graph + registry persistence |
| `DuckDB` | CQEOrchestrator, Phase2Orchestrator | OLAP query engine (preferred) |
| `Path` / `Pathlib` | All | File system operations |
| `asyncio` | Phantom, LSH, Morph, Skeleton orchestrators | Async adapter interactions |
| `dataclasses` | CQEOrchestrator, Schema types | Data containers |
| `abc.ABC` | BaseService | Abstract base class |
| `tqdm` | Pipeline stages | Progress bars |
| `json` / `pickle` | Pipeline stages | Serialization |

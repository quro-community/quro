# C1 Architecture — Leaf-Dominated Fanout Utility Layer

## Overview

C1 is a **leaf-dominated fanout** center (archetype: `fanout`) comprising **~666 symbols** across graph data adapters, I/O persistence adapters, TDA graph interfaces, DuckDB storage layer, manifold protocols, and visualization services. It serves as the **utility layer** providing data access abstractions and visualization output for the Quro semantic analysis pipeline.

## Module Structure

```
C1 (Leaf-Dominated Fanout Utility Layer)
├── graph/                    # Graph Data Adapters (CQE traversal)
│   ├── protocol.py          # GraphAdapter Protocol — interface contract
│   ├── types.py             # GraphNode, GraphEdge data types
│   ├── sqlite.py            # SQLiteGraphAdapter — SQLite-backed graph
│   └── duckdb.py            # DuckDBGraphAdapter — DuckDB-backed graph
│
├── io/adapters/             # I/O Persistence Adapters
│   ├── sqlite.py            # SQLiteGraphAdapter (IO-level), SQLiteIndexLoader
│   └── sqlite_tda.py        # SQLiteTDAGraphAdapter — TDA-specific SQLite
│
├── storage/                 # 🆕 DuckDB Storage Layer (TDA Unified Storage)
│   ├── coordinator.py      # StorageCoordinator — connection lifecycle manager
│   ├── schema.py           # TdaSchema — declarative DDL (v1+v2, 11 tables)
│   └── migration.py        # MigrationRunner — schema migration + legacy import
│
├── tda/
│   ├── interfaces/
│   │   └── graph.py         # GraphInterface (ABC), GraphMetadata, SubgraphView
│   ├── adapters/
│   │   ├── graph_adapter.py # GraphAdapter Factory — auto-selects best source
│   │   └── file_graph.py    # FileGraphAdapter, FieldDataGraphAdapter,
│   │                        # MemoryGraphAdapter, StreamingGraphAdapter
│   ├── phase1/
│   │   └── duckdb_processor.py  # 🆕 DuckDBPhase1Processor — SQL-based BFS (50-100x)
│   └── visualization/
│       ├── __init__.py      # FieldPlotter — plotting class
│       └── generate_plots.py # Plot generation entry points
│
├── pipeline/writers/
│   └── duckdb_event_writer.py  # 🆕 DuckDBEventWriter — streaming batch writer
│
├── adapters/manifold/       # Manifold Adapters Protocol
│   ├── protocol.py          # ManifoldAdapter Protocol
│   ├── types.py             # ManifoldNode, NodeInsertRequest
│   └── postgres.py          # PostgreSQL implementation
│
├── service/
│   └── visualization_service.py  # VisualizationService
│
├── cli/commands/
│   ├── visualize.py         # VisualizeCommand — CLI entry point
│   └── tda_pipeline.py     # 🆕 TDAPipelineCommand — orchestrates all phases
│
└── quro_mcp/
    └── service.py           # CQEGraphAdapter (within QuroV3Service)
```

## Layer Organization

| Layer | Module | Role | Description |
|-------|--------|------|-------------|
| **Protocol** | `adapters/graph/protocol.py` | EMITTER | Defines GraphAdapter protocol interface |
| **Protocol** | `adapters/manifold/protocol.py` | EMITTER | Defines ManifoldAdapter protocol interface |
| **Protocol** | `tda/interfaces/graph.py` | EMITTER | Defines GraphInterface ABC |
| **Types** | `adapters/graph/types.py` | CONVERTER | GraphNode, GraphEdge dataclasses |
| **Types** | `adapters/manifold/types.py` | CONVERTER | ManifoldNode, NodeInsertRequest |
| **Implementation** | `adapters/graph/sqlite.py` | CONVERTER | SQLiteGraphAdapter |
| **Implementation** | `adapters/graph/duckdb.py` | EMITTER | DuckDBGraphAdapter |
| **Implementation** | `io/adapters/sqlite.py` | CONVERTER | IO-level SQLiteGraphAdapter |
| **Implementation** | `io/adapters/sqlite_tda.py` | CONVERTER | SQLiteTDAGraphAdapter |
| **Implementation** | `tda/adapters/file_graph.py` | CONVERTER | 4 adapter classes for various cache formats |
| **Factory** | `tda/adapters/graph_adapter.py` | CONVERTER | GraphAdapter factory with auto-detection |
| **Storage (Coordinator)** | `storage/coordinator.py` | EMITTER (NEW) | 🆕 StorageCoordinator — DuckDB connection lifecycle |
| **Storage (Schema)** | `storage/schema.py` | POLICY | 🆕 TdaSchema — 11 tables, 2 versions, DDL definitions |
| **Storage (Migration)** | `storage/migration.py` | ORCHESTRATOR | 🆕 MigrationRunner — schema migration + legacy data import |
| **Phase 1 Processor** | `tda/phase1/duckdb_processor.py` | EMITTER (NEW) | 🆕 DuckDBPhase1Processor — SQL BFS (50-100x faster) |
| **Event Writer** | `pipeline/writers/duckdb_event_writer.py` | CONVERTER (NEW) | 🆕 DuckDBEventWriter — streaming batch writer |
| **Pipeline CLI** | `cli/commands/tda_pipeline.py` | ORCHESTRATOR | 🆕 TDAPipelineCommand — orchestrates phases 1-3.6 |
| **Bridge** | `quro_mcp/service.py` | CONVERTER | CQEGraphAdapter bridges Registry ↔ CQE |
| **Visualization** | `tda/visualization/__init__.py` | CONVERTER | FieldPlotter for TDA visualizations |
| **Service** | `service/visualization_service.py` | CONVERTER | Higher-level visualization service |
| **CLI** | `cli/commands/visualize.py` | TRANSIENT | CLI command wrapping service |

## Component Relationships

1. **GraphInterface** (ABC) ← implemented by → **FileGraphAdapter**, **FieldDataGraphAdapter**, **MemoryGraphAdapter**, **StreamingGraphAdapter**
2. **GraphAdapter** (Protocol) ← implemented by → **SQLiteGraphAdapter**, **DuckDBGraphAdapter**
3. **GraphAdapter** (Factory) creates instances of GraphInterface based on available data sources
4. **CQEGraphAdapter** wraps RegistryAdapter to conform to GraphProtocol for CQE traversal
5. **ManifoldAdapter** (Protocol) ← implemented by → PostgresManifoldAdapter
6. **VisualizationService** uses **FieldPlotter** to generate plots from TDA data

## Cross-Center Boundaries

C1 has high coupling with all 7 other centers (C0, C3, C4, C5, C6, C7, C8), with the strongest couplings to:
- **C0** (Hub, 674.4): Bridge via `sym::MemoryRegistryAdapter`, `sym::verify_symbol_integrity::tools::504`, `sym::DynamicsState`
- **C8** (Sink, 171.4): Bridge via shared sinks
- **C4** (Hub, 162.8): Bridge via shared sinks
- **C7** (Chain, 150.6): Bridge via shared sinks
- **C6** (Chain, 147.5): Bridge via `sym::upsert_node`, `sym::MemoryRegistryAdapter`, `sym::_process_event`

C1 is part of the **SC70 tight-coupling cluster** (with C0, C3, C7, C8) — changes in C1 may require co-changes in those centers.

## Key Design Invariants

1. **Read-only data access**: All graph adapters are read-only after initialization
2. **Lazy loading**: File-based adapters (FileGraphAdapter, StreamingGraphAdapter) use lazy initialization via `_ensure_loaded()`
3. **Source priority**: GraphAdapter factory uses a strict priority order: cache → field_cache → manifold → sqlite → jsonl
4. **Context manager pattern**: DuckDBGraphAdapter requires `with` statement for connection lifecycle
5. **Immutable cache**: SQLite adapters load data during `__init__` and never mutate
6. **DuckDB single-writer**: StorageCoordinator assumes one writer at a time; WAL disabled (batch pipeline)
7. **DuckDB schema migrations**: MigrationRunner applies append-only migrations in a single transaction, rollback on failure
8. **INSERT-only event log**: DuckDBEventWriter never UPDATE/DELETE; uses `INSERT OR IGNORE` for idempotency (dedup by event_id)
9. **Frontier-expansion BFS**: DuckDBPhase1Processor uses strict frontier-based expansion (NOT self-joins) to avoid O(N^d) combinatorial explosion
10. **SQL-native JSON construction**: Edge traversals (millions of rows) built via DuckDB `json_object()` — no Python serialization overhead
11. **⚠️ Incremental NOT implemented in DuckDB**: `--incremental` flag with DuckDB backend raises `NotImplementedError`; only JSONL backend supports incremental

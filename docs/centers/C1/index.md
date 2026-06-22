# C1 Knowledge Base Index — Leaf-Dominated Fanout Utility Layer

> **Last updated**: 2026-06-20
> **Mode**: INCREMENTAL (DuckDB storage layer findings)

## Coverage Summary

| Metric | Value |
|--------|-------|
| Total symbols | ~666 |
| Documented | 25+ key symbols (4% by count, 85% by energy weight) |
| Entry points cataloged | 3 |
| Modules identified | 15 major modules across 9 directories |
| Core attractors | 1 (SQLiteIndexLoader) |
| High-energy emitters | 6 (GraphInterface, GraphAdapter protocol, ManifoldAdapter, DuckDBGraphAdapter, DuckDBPhase1Processor, StorageCoordinator) |
| Coupling score (C0) | 674.4 (highest) |
| ⚠️ Incremental (DuckDB) | NOT implemented — `NotImplementedError` |

## Coverage Map

| Document | Status | Key Contents |
|----------|--------|-------------|
| `docs/architecture.md` | ✅ | Module structure, layer organization, 15+ components, design invariants (+DuckDB storage layer) |
| `docs/dataflow.md` | ✅ | 7 data flow paths: graph adapters, CQE traversal, MI adjustment, visualization, SQLite persistence, DuckDB storage, cross-center |
| `docs/api.md` | ✅ | 13 API surfaces with signatures, 6 data types documented |
| `docs/dependencies.md` | ✅ | Internal dependency graph, 7 cross-center bridges, external deps |
| `docs/entry-points.md` | ✅ | 3 entry points analyzed, energy ranking of 20 symbols, TDA roles |

## Core Modules

| Module | Path | Role | Purpose |
|--------|------|------|---------|
| GraphInterface | `tda/interfaces/graph.py` | EMITTER (68.31 fm) | Core abstract interface for graph data access |
| GraphAdapter (Factory) | `tda/adapters/graph_adapter.py` | CONVERTER (46.24 fm) | Auto-detects best graph data source |
| FileGraphAdapter | `tda/adapters/file_graph.py` | CONVERTER | Reads adjacency_cache.pkl (fastest) |
| FieldDataGraphAdapter | `tda/adapters/file_graph.py` | CONVERTER | Reads field_data_cache.pkl |
| MemoryGraphAdapter | `tda/adapters/file_graph.py` | CONVERTER | In-memory graph for testing |
| StreamingGraphAdapter | `tda/adapters/file_graph.py` | CONVERTER | Parses graph_events.jsonl (slow) |
| SQLiteGraphAdapter | `adapters/graph/sqlite.py` | CONVERTER | SQLite-based graph data |
| DuckDBGraphAdapter | `adapters/graph/duckdb.py` | EMITTER | DuckDB-based graph data |
| **DuckDBPhase1Processor** 🆕 | `tda/phase1/duckdb_processor.py` | **EMITTER (11.21 fm)** | SQL-based BFS traversal (50-100x) |
| **StorageCoordinator** 🆕 | `storage/coordinator.py` | ORCHESTRATOR | DuckDB connection lifecycle manager |
| **TdaSchema** 🆕 | `storage/schema.py` | POLICY | Declarative DDL (11 tables, v1+v2) |
| **MigrationRunner** 🆕 | `storage/migration.py` | ORCHESTRATOR | Schema migration + legacy data import |
| **DuckDBEventWriter** 🆕 | `pipeline/writers/duckdb_event_writer.py` | CONVERTER | Streaming batch writer (batch=1000) |
| SQLiteRegistryAdapter | `index_builder/adapters/sqlite.py` | CONVERTER | Persistent registry storage |
| SQLiteIndexLoader | `io/adapters/sqlite.py` | CORE_ATTRACTOR | Index loading from SQLite |
| CQEGraphAdapter | `quro_mcp/service.py` | CONVERTER | Registry → CQE bridge |
| ManifoldAdapter | `adapters/manifold/protocol.py` | EMITTER | Manifold storage protocol |
| VisualizationService | `service/visualization_service.py` | CONVERTER | TDA visualization generation |
| FieldPlotter | `tda/visualization/__init__.py` | CONVERTER | Plotting engine (6 plot types) |

## Energy Snapshot

| Rank | Symbol | Role | Forward Mag | Tension |
|------|--------|------|-------------|---------|
| 1 | `GraphInterface` | **EMITTER** | 68.31 | 0.08 |
| 2 | `GraphAdapter` (tda) | CONVERTER | 46.24 | 0.08 |
| 3 | `SubgraphView` | TRANSIENT | 29.02 | 0.57 |
| 4 | `FileGraphAdapter` | CONVERTER | 24.13 | 0.38 |
| 5 | `FieldDataGraphAdapter` | CONVERTER | 24.13 | 0.38 |
| 6 | `ManifoldAdapter` | **EMITTER** | 23.92 | 0.08 |
| 7 | `MemoryGraphAdapter` | CONVERTER | 23.12 | 0.38 |
| 8 | `BaseService` | **EMITTER** | 20.00 | 0.08 |
| 9 | `SQLiteGraphAdapter` | CONVERTER | 18.04 | 0.45 |
| 10 | `GraphAdapter` (proto) | **EMITTER** | 18.04 | 0.08 |

**Core Attractor**: `SQLiteIndexLoader` (12.40 fm, 0.80 bt) — backward-tension dominant, stable attractor in index persistence

## Coupling Summary

| Center | Score | Type |
|--------|-------|------|
| C0 (Hub) | 674.4 | Tight (SC70 cluster) |
| C8 (Sink) | 171.4 | Strong shared sinks |
| C4 (Hub) | 162.8 | Strong shared sinks |
| C7 (Chain) | 150.6 | Strong shared sinks |
| C6 (Chain) | 147.5 | Strong shared sinks |
| C3 (Sink) | 132.5 | Moderate shared sinks |
| C5 (Hub) | 100.1 | Moderate shared sinks |

---

> **Legend:** ✅ documented | ⚠️ partial | ❌ undocumented

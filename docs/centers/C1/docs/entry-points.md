# C1 Entry Points — Leaf-Dominated Fanout Utility Layer

## Entry Point Overview

C1 has **3 declared entry points** (per landscape partition). All three are lazy-imported modules used by the **GraphAdapter factory** in the TDA pipeline. They represent leaf-level data access points from which the fanout expands outward.

### Entry Point Symbols

| Entry Point | Module | Type | Role | Energy |
|-------------|--------|------|------|--------|
| `sym::ManifoldStatesGraphAdapter` | `manifold_graph` | Class (lazy import) | CONVERTER (est.) | Medium (fanout utility) |
| `sym::sqlite_graph` | `sqlite_graph` | Module (lazy import) | CONVERTER (est.) | Medium (data access) |
| `sym::figure` | `tda/visualization` | Module | CONVERTER (est.) | Medium (visualization) |

> **Note**: The `quro_get_center_reachability("C1")` call returned 0 reachable symbols, consistent with C1's **leaf-dominated** archetype — entry points are leaves that expand outward to callers, not inward. All three entry points are lazy imports within `tda/adapters/graph_adapter.py` and `tda/visualization/`.

---

## 1. `sym::ManifoldStatesGraphAdapter`

**Location**: Lazy import in `tda/adapters/graph_adapter.py:92` (module `manifold_graph`)

**Role**: CONVERTER (estimated — not directly classified as sym not found in TDA index)

**Purpose**: Reads `manifold_states.jsonl` (Phase 2 output) to provide graph data with embedded neighbor information.

**Usage**:
```python
from manifold_graph import ManifoldStatesGraphAdapter
adapter = ManifoldStatesGraphAdapter(manifold_path)  # manifold_states.jsonl
```

**TDA Profile** (estimated from f(MI)-like adapters):
- Forward magnitude: ~18-24 (similar to SQLiteGraphAdapter/FileGraphAdapter)
- Source diversity: ~0.88-1.0 (single-file source)
- In-degree: ~4-8 (imported by GraphAdapter factory)
- Out-degree: ~29-49 (provides GraphInterface methods)

**Callers**:
| Caller | File | Context |
|--------|------|---------|
| `GraphAdapter.create()` | `tda/adapters/graph_adapter.py:92` | Factory auto-detection path |

**Entry strategy**: Bottom-up — this is a leaf adapter, callers (C0) access it through the factory.

---

## 2. `sym::sqlite_graph`

**Location**: Lazy import in `tda/adapters/graph_adapter.py:103` (module `sqlite_graph`)

**Role**: CONVERTER (estimated)

**Purpose**: Provides `SQLiteGraphAdapter` class that reads `registry.db` for graph data when faster caches are unavailable.

**Usage**:
```python
from sqlite_graph import SQLiteGraphAdapter
adapter = SQLiteGraphAdapter(registry_path)  # registry.db
```

**TDA Profile** (estimated):
- Forward magnitude: ~13-18 (similar to SQLiteTDAGraphAdapter)
- Source diversity: ~0.88
- In-degree: ~4-8 (imported by GraphAdapter factory)
- Out-degree: ~20-30

**Callers**:
| Caller | File | Context |
|--------|------|---------|
| `GraphAdapter.create()` | `tda/adapters/graph_adapter.py:103` | Fallback SQLite path |

**Entry strategy**: Bottom-up — leaf-level data access, used only when higher-priority caches are unavailable.

---

## 3. `sym::figure`

**Location**: `tda/visualization/` (all plotting functions)

**Role**: CONVERTER (per `FieldPlotter` classification — forward magnitude: 8.88)

**Purpose**: Visualization generation — produces PNG plots of TDA energy landscapes, gradient fields, attractor basins, trajectories, coherence analyses, and summary dashboards.

**TDA Profile** (via `FieldPlotter`):
- Role: **CONVERTER**
- Forward magnitude: 8.88
- Backward tension: 0.55
- Source diversity: 1.0
- In-degree: 20
- Out-degree: 35

**Entry points within figure**:
| Symbol | Role | Description |
|--------|------|-------------|
| `FieldPlotter` | CONVERTER | Main plotting class (6 plot types) |
| `VisualizationService` | CONVERTER | Higher-level service wrapping FieldPlotter |
| `VisualizeCommand` | TRANSIENT | CLI command binding |

**Entry strategy**: Bottom-up — CLI commands call VisualizationService → FieldPlotter.

---

## Energy Priority Ranking

Based on TDA role classification of related symbols:

| Rank | Symbol | Role | Forward Mag | Priority | Reason |
|------|--------|------|-------------|----------|--------|
| 1 | `GraphInterface` | **EMITTER** | 68.31 | HIGH | Core ABC — all adapters implement it |
| 2 | `GraphAdapter` (Factory) | **CONVERTER** | 46.24 | HIGH | Central factory — orchestrates all sources |
| 3 | `SubgraphView` | TRANSIENT | 29.02 | MEDIUM | View wrapper — high transient traffic |
| 4 | `FileGraphAdapter` | CONVERTER | 24.13 | MEDIUM | Primary adapter (cache path) |
| 5 | `FieldDataGraphAdapter` | CONVERTER | 24.13 | MEDIUM | Secondary adapter (field cache) |
| 6 | `ManifoldAdapter` | **EMITTER** | 23.92 | MEDIUM | Protocol interface |
| 7 | `MemoryGraphAdapter` | CONVERTER | 23.12 | MEDIUM | Test adapter |
| 8 | `GraphAdapter` (Proto) | **EMITTER** | 18.04 | MEDIUM | Protocol definition |
| 9 | `SQLiteGraphAdapter` | CONVERTER | 18.04 | MEDIUM | SQLite implementation |
| 10 | `StreamingGraphAdapter` | CONVERTER | 17.63 | MEDIUM | Slow fallback |
| 11 | `CQEGraphAdapter` | CONVERTER | 17.79 | MEDIUM | Bridge adapter |
| 12 | `DuckDBGraphAdapter` | **EMITTER** | 16.24 | LOW | DuckDB implementation |
| 13 | `SQLiteTDAGraphAdapter` | CONVERTER | 13.19 | LOW | TDA-specific SQLite |
| 14 | `VisualizationService` | CONVERTER | 12.91 | LOW | Visualization service |
| 15 | `SQLiteIndexLoader` | **CORE_ATTRACTOR** | 12.40 | MEDIUM | Core index loader |
| 16 | `VisualizeCommand` | TRANSIENT | 12.33 | LOW | CLI wrapper |
| 17 | `FieldPlotter` | CONVERTER | 8.88 | LOW | Plotting engine |
| 18 | `GraphNode` | CONVERTER | 7.87 | LOW | Data type |
| 19 | `GraphEdge` | CONVERTER | 7.86 | LOW | Data type |
| 20 | `ManifoldNode` | CONVERTER | 5.57 | LOW | Data type |

## Attractor/Energy Summary

- **Core attractors**: `SQLiteIndexLoader` (12.40 fm, 0.8 backward tension) — principal index persistence node
- **Emitters**: `GraphInterface` (68.31 fm), `GraphAdapter` Protocol (18.04 fm), `ManifoldAdapter` (23.92 fm), `DuckDBGraphAdapter` (16.24 fm), `BaseService` (20.0 fm)
- **Converters**: Most implementation classes (factory, adapters, services)
- **Transients**: `SubgraphView` (29.02 fm), `GraphMetadata` (2.42 fm), `VisualizeCommand` (12.33 fm)
- **Stable nodes**: `GraphNode` (0.55 backward tension), `GraphEdge` (0.54 backward tension), `SQLiteRegistryAdapter` (0.53 backward tension)

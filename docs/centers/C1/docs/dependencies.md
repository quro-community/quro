# C1 Dependencies — Leaf-Dominated Fanout Utility Layer

## Internal Dependency Graph

```
GraphInterface (ABC)                     ← tda/interfaces/graph.py
    │
    ├──◄── FileGraphAdapter              ← tda/adapters/file_graph.py
    ├──◄── FieldDataGraphAdapter          ← tda/adapters/file_graph.py
    ├──◄── MemoryGraphAdapter             ← tda/adapters/file_graph.py
    ├──◄── StreamingGraphAdapter          ← tda/adapters/file_graph.py
    └──◄── SubgraphView                   ← tda/interfaces/graph.py
            [wraps any GraphInterface]

GraphAdapter (Protocol)                  ← adapters/graph/protocol.py
    │
    ├──◄── SQLiteGraphAdapter            ← adapters/graph/sqlite.py
    └──◄── DuckDBGraphAdapter            ← adapters/graph/duckdb.py
            [Both use GraphNode, GraphEdge from types.py]

GraphAdapter (Factory)                    ← tda/adapters/graph_adapter.py
    │
    ├── creates ──► FileGraphAdapter
    ├── creates ──► FieldDataGraphAdapter
    ├── creates ──► ManifoldStatesGraphAdapter  [lazy import]
    ├── creates ──► SQLiteGraphAdapter           [lazy import]
    └── creates ──► StreamingGraphAdapter

CQEGraphAdapter                           ← quro_mcp/service.py
    │
    ├── uses ──► RegistryAdapter
    └── uses ──► MorphismMIAdjuster

ManifoldAdapter (Protocol)                ← adapters/manifold/protocol.py
    │
    └──◄── PostgresManifoldAdapter        ← adapters/manifold/postgres.py

SQLiteRegistryAdapter                     ← index_builder/adapters/sqlite.py
    │
    └── uses ──► GraphNode, GraphEdge     ← adapters/graph/types.py

VisualizationService                       ← service/visualization_service.py
    │
    ├── extends ──► BaseService           ← service/base.py
    └── uses ──► FieldPlotter              ← tda/visualization/__init__.py
         └── uses ──► generate_plots      ← tda/visualization/generate_plots.py
```

## Cross-Center Dependency Graph

### C1 → C0 (Hub, score: 674.4)
```
C1 adapters ──► C0 RegistryAdapter
    │                │
    └── SQLiteRegistryAdapter.save_node() ──► C0 GraphNode
    └── CQEGraphAdapter.neighbors() ──► C0 RegistryAdapter.get_edges_from()
    └── GraphAdapter.create() ──► C0 field_data_path
    └── ManifoldStatesGraphAdapter ──► C0 manifold_states.jsonl
```

Shared sinks: `sym::MemoryRegistryAdapter`, `sym::verify_symbol_integrity::tools::504`, `sym::DynamicsState`

### C1 → C3 (Sink, score: 132.5)
```
C1 ──► C3
    └── FileGraphAdapter ──► C3 Path I/O
    └── SQLiteGraphAdapter ──► C3 file system .db paths
    └── StreamingGraphAdapter ──► C3 JSONL file parsing
```

Shared sinks: `sym::MemoryRegistryAdapter`, `sym::verify_symbol_integrity::tools::504`, `sym::DynamicsState`

### C1 → C4 (Hub, score: 162.8)
```
C1 ──► C4
    └── SQLiteRegistryAdapter ──► C4 index building
    └── VisualizeCommand ──► C4 CLI infrastructure
```

Shared sinks: `sym::MemoryRegistryAdapter`, `sym::verify_symbol_integrity::tools::504`, `sym::DynamicsState`

### C1 → C5 (Hub, score: 100.1)
```
C1 ──► C5
    └── GraphAdapter factory ──► C5 type system
    └── ManifoldAdapter protocol ──► C5 policy types
```

Shared sinks: `sym::MemoryRegistryAdapter`, `sym::verify_symbol_integrity::tools::504`, `sym::DynamicsState`

### C1 → C6 (Chain, score: 147.5)
```
C1 ──► C6
    └── SQLiteRegistryAdapter.save_node/edge ──► C6 persistence
    └── CQEGraphAdapter ──► C6 event processing
```

Shared sinks: `sym::upsert_node`, `sym::MemoryRegistryAdapter`, `sym::_process_event`

### C1 → C7 (Chain, score: 150.6)
```
C1 ──► C7
    └── TDA adapters ──► C7 graph operations
    └── SubgraphView ──► C7 partitioning
```

Shared sinks: `sym::MemoryRegistryAdapter`, `sym::verify_symbol_integrity::tools::504`, `sym::DynamicsState`

### C1 → C8 (Sink, score: 171.4)
```
C1 ──► C8
    └── FieldPlotter ──► C8 visual output
    └── VisualizationService ──► C8 HTML/file generation
    └── FileGraphAdapter ──► C8 file caching
```

Shared sinks: `sym::MemoryRegistryAdapter`, `sym::verify_symbol_integrity::tools::504`, `sym::DynamicsState`

## External Dependencies

| Dependency | Used By | Purpose |
|-----------|---------|---------|
| `pathlib.Path` | All adapters | File path handling |
| `pickle` | FileGraphAdapter, FieldDataGraphAdapter | Cache deserialization |
| `sqlite3` | SQLiteGraphAdapter, SQLiteRegistryAdapter | Database access |
| `duckdb` | DuckDBGraphAdapter | DuckDB database access |
| `json` | StreamingGraphAdapter | JSONL parsing |
| `matplotlib` | FieldPlotter | Plot generation |
| `scipy.spatial.Voronoi` | FieldPlotter | Voronoi attractor basins |
| `numpy` | FieldPlotter | Numerical operations |
| `logging` | All modules | Logging |
| `argparse` | VisualizeCommand | CLI argument parsing |

## Tight Coupling Cluster SC70

C1 is part of the **SC70** tight-coupling cluster (size: 832, archetype: `tight_coupling`) with:

- **C0** — Core orchestration hub
- **C1** — Utility layer (this center)
- **C3** — File/IO sink
- **C7** — Chain layer
- **C8** — Storage sink

**Implication**: Changes to C1's adapter interfaces or data types may require co-changes in C0, C3, C7, and C8. The 10 bridge symbols flowing to 10 shared sinks create a tightly coupled change surface.

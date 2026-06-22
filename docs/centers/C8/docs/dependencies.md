# C8 Dependencies — MinHash LSH Sink

## Internal Dependency Graph

```
core/lsh/__init__.py
  ├── imports: types → LSHConfig, LSHSignature
  ├── imports: kernel → LSHKernel
  └── imports: minhash → MinHashLSH

core/lsh/types.py
  └── (standalone — no internal deps)

core/lsh/kernel.py
  ├── imports: types → LSHSignature
  └── imports: typing → Protocol, Set

core/lsh/minhash.py
  ├── imports: types → LSHConfig, LSHSignature
  ├── imports: hashlib, struct, numpy, typing
  └── (implements LSHKernel protocol)

orchestrators/lsh.py
  ├── imports: core.lsh → LSHConfig, LSHSignature, MinHashLSH
  └── imports: adapters.manifold → ManifoldAdapter, ManifoldNode, NodeInsertRequest

deprecated/.../lsh_engine.py
  └── imports: numpy, hashlib, struct, logging, typing, asyncpg, argparse
       (standalone — no quro internal deps beyond self)
```

## Cross-Center Dependencies

### Upstream Callers (call C8)

| Caller | Center | Uses |
|--------|--------|------|
| `deprecated/.../mcp/tools.py` | C0 | MinHashLSH (lsh_engine.py) — instantiation, _find_neighbors, query_semantic_inventory, scan_workspace, index_symbols |
| `deprecated/.../mcp/tools/scan_tools.py` | C0 | MinHashLSH (lsh_engine.py) — scan method |
| `deprecated/.../mcp/tools/symbol_tools.py` | C1 | MinHashLSH (lsh_engine.py) — _find_neighbors, query_semantic_inventory |
| `deprecated/.../scanner.py` | C1 | MinHashLSH (lsh_engine.py) — instantiation in WorkspaceScanner |
| `core/cqe/flow_observer.py` | C3 | to_dict — FlowTrace serialization |
| `tda/flow_observer.py` | C3 | to_dict — FlowTrace serialization |

### Downstream Dependencies (C8 calls)

| Dependency | Center | Context |
|------------|--------|---------|
| `ManifoldAdapter` | C0 | Used by LSHOrchestrator for persistence |
| `LSHConfig` (deprecated) | C8 self | Used by MCP tools, scan_tools, symbol_tools |

### Coupling Scores (from landscape)

| Center Pair | Score | Mechanism |
|-------------|-------|-----------|
| C0 ↔ C8 | 672.288 | Bridge symbols → shared sinks (MemoryRegistryAdapter, DynamicsState) |
| C1 ↔ C8 | 171.358 | Bridge symbols → shared sinks |
| C3 ↔ C8 | 163.367 | Bridge symbols → shared sinks |

### Coupling Cluster

C8 is part of **SC70** (tight coupling cluster, size=832 symbols):
- Centers: C0, C1, C3, C7, C8
- Hint: "Must change together"

## External Dependencies

| Dependency | Version/Usage |
|------------|--------------|
| Python 3.11+ | Core runtime |
| numpy | MinHash vectorized computation |
| hashlib | Token/band hashing (SHA256) |
| struct | Binary serialization |
| asyncpg | PostgreSQL async driver (deprecated CLI) |

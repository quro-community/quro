# C3 Dependencies — Semantic Analysis and CQE Refinement Hub

## Cross-Center Coupling

### Coupling Cluster SC38

| Center | Relationship |
|--------|-------------|
| **C0** | Core orchestration ↔ TDA classification |
| **C1** | Utility layer ↔ classification refinement |
| **C2** | Utility layer ↔ analysis support |
| **C4** | Quality reporting ↔ CQE refinement output |
| **C5** | Hub ↔ hub — tool dispatch coordination |
| **C6** | Transitional layer ↔ refinement pipeline |
| **C7** | Chain layer ↔ tool execution |
| **C8** | MinHash LSH ↔ workspace scanning |
| **C9** | Fanout utility ↔ dispatch support |

## Internal Dependency Graph

```
┌─────────────────────────────────────────────────────────┐
│                    C3 Symbols                             │
│                                                           │
│  classify_node_role ───→ TDA analysis modules            │
│  SemanticCQERefiner ───→ CQE refinement engine           │
│  GateResult::types ────→ Gate type definitions           │
│  call_tool ─────────────→ MCP tool registry              │
│  scan_workspace ────────→ Workspace scanner modules      │
│                                                           │
│  All entry points ──────→ Cross-center calls (C0–C9)     │
└─────────────────────────────────────────────────────────┘
```

## External Dependencies

| Dependency | Used By | Purpose |
|------------|---------|---------|
| TDA engine (C0) | classify_node_role | Node role classification |
| CQE engine (C4) | SemanticCQERefiner | Quality evaluation refinement |
| MCP framework | call_tool | Tool dispatch and execution |
| Filesystem (stdlib) | scan_workspace | Workspace traversal |
| Type system (stdlib) | GateResult::types | Result type validation |

## Caller Map

| C3 Entry Point | Called By (Upstream) | Calls (Downstream) |
|----------------|---------------------|-------------------|
| `classify_node_role` | CLI, MCP tools | C0, C1, C2 |
| `SemanticCQERefiner` | C4 quality reporter | C4, C5, C6 |
| `GateResult::types` | C5 gate engine | C5, C6, C7 |
| `call_tool` | CLI, MCP tools | C5, C7, C9 |
| `scan_workspace` | CLI, MCP tools | C8, C9 |

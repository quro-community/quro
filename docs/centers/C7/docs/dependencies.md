# C7 Dependencies — Shadow Draft & Tools Chain

## Internal Dependency Graph

```
entry points (L1)
    │
    ├── get_in_neighbors ──→ _ensure_loaded (file_graph.py)
    │                           └── get (registry.py)
    │
    ├── get_draft_status ──→ ShadowDraftManager
    │                           ├── DSLAtomParser
    │                           │     ├── parse_sequence
    │                           │     ├── validate_sequence
    │                           │     ├── build_execution_graph
    │                           │     ├── detect_potential_deadlocks
    │                           │     ├── generate_python_skeleton
    │                           │     └── generate_typescript_skeleton
    │                           └── MonteCarloSimulator
    │                                 └── simulate
    │
    └── shutdown ──→ TypeScriptAnalyzer
                        ├── TypeScriptProbe
                        │     ├── start
                        │     ├── stop
                        │     ├── ping
                        │     └── get_type_at_position
                        └── (TreeSitter fallback - not yet implemented)
```

## Module-Level Dependencies

| Source Module | Depends On | Type |
|---------------|------------|------|
| MCPTools (tools.py) | ShadowDraftManager, TypeScriptAnalyzer, asyncpg | Composition |
| ShadowDraftManager | DSLAtomParser, MonteCarloSimulator, hashlib | Composition |
| TypeScriptAnalyzer | TypeScriptProbe, tree-sitter (planned) | Composition |
| TypeScriptProbe | ts-node subprocess, asyncio | Subprocess |
| ShadowTools | ShadowDraftManager | Delegation |
| SymbolTools | Registry, TypeScriptAnalyzer | Delegation |

## Cross-Center Coupling

### C7 ↔ C0 (Hub, score: 632.92 — HIGH)
10 bridge symbols flowing to shared sinks:
- `MemoryRegistryAdapter`
- `verify_symbol_integrity::tools::504`
- `DynamicsState`

C7 delegates orchestration tasks to C0 for:
- Trust registry queries
- Symbol verification
- State management

### C7 ↔ C1 (Fanout, score: 150.60)
10 bridge symbols flowing to shared sinks:
- `MemoryRegistryAdapter`
- `verify_symbol_integrity::tools::504`
- `DynamicsState`

C7 delegates utility operations to C1 for:
- Symbol identification
- Path tracing

### C7 ↔ C3 (Sink, score: 140.53)
10 bridge symbols flowing to shared sinks:
- `MemoryRegistryAdapter`
- `verify_symbol_integrity::tools::504`
- `DynamicsState`

C7 routes I/O operations through C3 for:
- Database persistence
- File system operations

### Coupling Cluster SC70
C7 is part of **tight-coupling cluster SC70** (size: 832) with C0, C1, C3, C8. Centers in this cluster must change together.

## External Dependencies

| Dependency | Used By | Purpose |
|------------|---------|---------|
| asyncpg | MCPTools, Database | PostgreSQL async driver |
| hashlib | ShadowDraftManager | Checksum computation |
| asyncio | All | Async runtime |
| json | Logger, serialization | JSON serialization |
| Path (pathlib) | All | Path manipulation |
| ts-node | TypeScriptProbe | TypeScript runtime |
| tree-sitter | TypeScriptAnalyzer | Language parsing (planned) |

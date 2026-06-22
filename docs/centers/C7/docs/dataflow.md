# C7 Data Flow — Shadow Draft & Tools Chain

## Primary Data Flows

### Flow 1: Shadow Draft Pipeline (core C7 chain)

```
[MCP Client] → create_shadow_draft(symbol, atoms, language, target_path)
    │
    ├─ DSLAtomParser.parse_sequence(atoms) → parsed_atoms
    ├─ DSLAtomParser.validate_sequence(parsed_atoms) → is_valid, errors
    ├─ DSLAtomParser.build_execution_graph(parsed_atoms) → graph
    ├─ DSLAtomParser.detect_potential_deadlocks(graph) → warnings
    ├─ store draft in self.drafts[symbol] (status: PENDING)
    │
    └─ (optional auto_eject=True) → eject_shadow_draft(symbol)
         │
         ├─ MonteCarloSimulator.simulate([graph]) → risk_score, witness_traces
         │
         ├─ if risk_score >= risk_gate:
         │     status = REJECTED, return rejection_report
         │
         └─ if risk_score < risk_gate or force:
               DSLAtomParser.generate_python/typescript_skeleton(graph, symbol)
               → write skeleton to target_path
               status = MATERIALIZED
```

### Flow 2: Draft Status Polling

```
[MCP Client] → get_draft_status(symbol)
    │
    └─ ShadowDraftManager.get_draft_status(symbol)
         └─ lookup self.drafts[symbol] → status, risk_score, warnings
```

### Flow 3: TypeScript Analysis

```
[MCP Client] → TypeScriptAnalyzer.initialize()
    │
    ├─ TypeScriptProbe.start()  (starts ts-node subprocess)
    │
    ├─ get_symbol_at_position(file, line, char)
    │    ├─ probe.get_type_at_position() → SymbolInfo
    │    └─ fallback: _get_symbol_tree_sitter() (not yet implemented)
    │
    ├─ find_definition(file, line, char)
    │    ├─ probe.find_definition() → SymbolInfo
    │    └─ fallback: _find_definition_tree_sitter() (not yet implemented)
    │
    ├─ resolve_import(file, import_path)
    │    ├─ probe.resolve_import_path() → resolved path
    │    └─ fallback: _resolve_import_heuristic()
    │
    ├─ get_diagnostics(file_path)
    │    └─ probe.get_diagnostics() → List[Diagnostic]
    │
    └─ shutdown()
         └─ probe.stop()  (kills subprocess)
```

### Flow 4: CQE Query Pipeline

```
[MCP Client] → cqe_query(query)
    │
    ├─ CQETools.cqe_query(query)
    │    ├─ load CQE index
    │    ├─ compute MI scores
    │    └─ return refined results
    │
    └─ CQECommands.run_update/build/rebuild()
         └─ manage CQE index lifecycle
```

### Flow 5: Registry Operations

```
[MCP Tool] → insert_symbol(symbol, metadata)
    │
    ├─ protocol::insert_symbol (validation)
    └─ registry_v2::insert_symbol (persistence)

[MCP Tool] → get_symbol_by_name(name)
    │
    ├─ protocol::get_symbol_by_name (query)
    └─ registry_v2::get_symbol_by_name (persistence)
```

## Cross-Center Data Flow

### C7 → C0 (Hub, score: 632.92)

C7 channels tool requests from MCP interface to C0 orchestration layer:
- `verify_symbol_integrity` → C0 trust/registry queries
- `read_source_symbol` → C0 file/symbol resolution
- `quro_explore` → C0 exploration engine
- `project_panorama` → C0 project overview

### C7 → C1 (Fanout, score: 150.60)

C7 delegates utility operations to C1:
- `identify_symbol` → C1 symbol identification
- `trace_logic_path` → C1 path tracing
- `compact_context` → C1 context compaction

### C7 → C3 (Sink, score: 140.53)

C7 persists data through C3 I/O layer:
- Database operations (connect, disconnect, health_check)
- File-based shadow storage (read/write/delete shadow files)

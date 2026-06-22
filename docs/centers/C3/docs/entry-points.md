# C3 Entry Points — Semantic Analysis and CQE Refinement Hub

## Entry Points

| Entry Point | Symbol | Description |
|-------------|--------|-------------|
| `classify_node_role::upstream_navigator::325` | `sym::classify_node_role::upstream_navigator::325` | TDA node role classification and upstream navigation |
| `SemanticCQERefiner::refiner::128` | `sym::SemanticCQERefiner::refiner::128` | CQE quality evaluation refinement engine |
| `GateResult::types::13` | `sym::GateResult::types::13` | Gate result type definitions and validation |
| `call_tool` | `sym::call_tool` | MCP tool invocation dispatch |
| `scan_workspace` | `sym::scan_workspace` | Workspace scanning entry point |

## Top-Down Navigation Strategy

Since C3 is a **hub archetype**, the recommended navigation strategy is **top-down**:
1. Start at entry points (listed above)
2. Trace downstream calls to coupled centers (C0–C9 via SC38)
3. Follow the data flow from hub entry to downstream processing

## Key Hub Dispatch Points

### TDA Classification (→ C0, C1, C2)
```
Entry: classify_node_role::upstream_navigator::325
  → classify_node_role(symbol)        → EMITTER/CONVERTER/SINK/CORE_ATTRACTOR
  → upstream_navigator(symbol, depth) → upstream source chain
```

### CQE Refinement (→ C4, C5, C6)
```
Entry: SemanticCQERefiner::refiner::128
  → refine(evaluation_data)           → RefinedReport
  → compute_confidence(metrics)       → float
  → generate_report(refined)          → human-readable text
```

### Gate Result Types (→ C5, C6, C7)
```
Entry: GateResult::types::13
  → GateResult(status, code, message, data)    → standard result
  → GateError(code, message, details)           → typed error
  → GateWarning(code, message, severity)        → typed warning
  → GateSummary(total, passed, failed, warnings)→ aggregation
```

### MCP Tool Dispatch (→ C5, C7, C9)
```
Entry: call_tool
  → call_tool(tool_name, arguments)   → tool execution result
```

### Workspace Scanning (→ C8, C9)
```
Entry: scan_workspace
  → scan_workspace(path, includes, excludes) → ScanResult
```

## Dispatch Pattern Summary

| Entry Point | Dispatch Mechanism | Handler Pattern |
|-------------|-------------------|-----------------|
| `classify_node_role` | TDA classifier function | Analysis → role mapping |
| `SemanticCQERefiner` | Class method | Refinement pipeline |
| `GateResult::types` | Data types | Type definitions + validators |
| `call_tool` | Registry lookup | Registration → resolution → execution |
| `scan_workspace` | Function | Traversal → extraction → summary |

# C3 Data Flow — Semantic Analysis and CQE Refinement Hub

## Data Flow Overview

C3 acts as a **hub** — data flows through C3 entry points and fans out to downstream centers for processing, analysis, and storage.

```
         ┌──────────────────────────────────────────────┐
         │  External / CLI / MCP Client                  │
         │  (call_tool, scan_workspace)                   │
         └──────────┬───────────────────────┬────────────┘
                    │                       │
                    ▼                       ▼
         ┌──────────────────────────────────────────────┐
         │              C3 (Hub)                         │
         │                                                │
         │  classify_node_role ───→ TDA Analysis (C0)    │
         │  SemanticCQERefiner ───→ CQE Refinement (C4)  │
         │  GateResult::types ───→ Type Validation (C5)  │
         │  call_tool ───────────→ Tool Execution (C5/C7)│
         │  scan_workspace ──────→ Symbol Indexing (C8)  │
         └──────────────────────────────────────────────┘
```

## Specific Data Flows

### Flow 1: TDA Node Role Classification
```
CLI/MCP → C3 classify_node_role::upstream_navigator::325
  → TDA classification engine
  → Analyzes node energy (forward/backward magnitude)
  → Returns role: EMITTER, CONVERTER, SINK, CORE_ATTRACTOR
  → Optionally navigates upstream for tracing
```

### Flow 2: CQE Refinement
```
C4 Quality Reporter → C3 SemanticCQERefiner::refiner::128
  → Loads raw CQE evaluation results
  → Applies semantic refinement rules
  → Computes quality metrics and confidence scores
  → Returns refined evaluation report
```

### Flow 3: Gate Result Validation
```
C5 Gate Engine → C3 GateResult::types::13
  → Loads gate result types
  → Validates result against type definitions
  → Routes validated results to downstream processors
```

### Flow 4: MCP Tool Dispatch
```
CLI → C3 call_tool
  → Resolves tool name from registry
  → Validates arguments against tool schema
  → Invokes tool implementation
  → Returns tool execution result
```

### Flow 5: Workspace Scanning
```
CLI → C3 scan_workspace
  → Traverses workspace filesystem
  → Extracts symbol definitions and references
  → Feeds symbols into C8 (MinHash LSH) for similarity indexing
  → Returns scan summary with symbol count
```

## Entry Point Flow Summary

| Entry Point | Input | Output | Downstream Centers |
|-------------|-------|--------|-------------------|
| `classify_node_role` | Node ID / symbol name | Role classification | C0, C1, C2 |
| `SemanticCQERefiner` | Raw evaluation data | Refined quality metrics | C4, C5, C6 |
| `GateResult::types` | Gate result data | Validated/transformed result | C5, C6, C7 |
| `call_tool` | Tool name + args | Tool execution result | C5, C7, C9 |
| `scan_workspace` | Workspace path | Symbol scan summary | C8, C9 |

# C6: Type System & Validation Chain — Internal Architecture

> **Center Profile:** Chain archetype | 176 symbols | Entry: sequential

## Overview

C6 is the **Type System & Validation Chain** center. It provides the immutable data structures (DTOs/type definitions) that flow through the Quro scanner and CQE pipeline, plus the stateless gate operators that validate and filter symbols, files, and features before indexing. It acts as the **transitional layer** between raw code parsing (C1/C3) and the CQE graph (C0/C4).

## Subsystems

### 1. Scanner Types (`scanner/types.py`)
Core immutable dataclasses for the scanner pipeline:

| Type | Role | Description |
|------|------|-------------|
| `ParsedSymbol` | DTO (TRANSIENT) | Raw AST symbol data: name, kind, file_path, line, char, signature, calls, imports, decorators, docstring |
| `SymbolFeatures` | DTO (TRANSIENT) | Behavioral/structural tags + LSH signature + risk anchors |
| `SymbolInfo` | **Entry Point** (CONVERTER) | Enriched symbol: `ParsedSymbol` + `SymbolFeatures` + fingerprint + metadata |
| `FileInfo` | DTO (TRANSIENT) | File metadata: path, language, fingerprint, size, symbol count, scan time |
| `ScanResult` | DTO (TRANSIENT) | Complete scan result: FileInfo + symbols + edges + errors |

### 2. Scanner Gate Chain (`scanner/gates/`)
Stateless validation pipeline with sequential gate execution:

| Component | Type | Responsibility |
|-----------|------|---------------|
| `GateResult` | CONVERTER | Validation result (passed, reason, modified_data) — high traffic (in=32, out=13) |
| `SymbolFilterGate` | Stateless | Filters symbols: blacklist → name length → private → test → lambda |
| `FileFilterGate` | Stateless | Filters files: exists → is_file → extension whitelist → quroignore → size → binary |
| `FeatureGate` | Transform | Caps features (MAX=100), priority: risk > behavioral > structural |
| `ScannerGateChain` | Orchestrator | Coordinates all 3 gates, tracks rejection statistics |

### 3. Pipeline Input Gates (`pipeline/cqe/input_gates.py`)
Parallel validation chain for the CQE extraction pipeline:

| Component | Type | Responsibility |
|-----------|------|---------------|
| `SymbolBlacklistGate` | Stateless | Rejects generic symbol names (task_id, path, error, data, etc.) |
| `FilePathIntegrityGate` | Stateless | Validates path exists, not ignored, has directory structure |
| `FeatureCapGate` | Transform | Caps features at 1000 to prevent SQLite BLOB overflow |
| `InputGateChain` | Orchestrator | Sequential validate_atom: symbol → file → feature |

### 4. Structural Tag Extraction (`deprecated/quro_cli/analysis/structural_tag_extractor.py`)
Deterministic tag extraction from AST structural signals:

| Component | Type | Responsibility |
|-----------|------|---------------|
| `StructuralTags` | **Entry Point** (CONVERTER) | Immutable result: tags tuple, role, source ('structural'/'llm'/'merged') |
| `extract_tags()` | Function | Kind-level → source-level pattern matching → memory → decorator → entry point → role inference |
| `_infer_role()` | Function | Priority-ordered role inference (ResourceManager > IOHandler > Coordinator > Transformer > Configuration > Container > CoreInfrastructure) |
| `merge_with_llm_tags()` | Function | Additive merge: LLM tags appended without overriding structural tags |

### 5. Graph Adapter Protocol (`adapters/graph/`)
Protocol + implementations for graph data access used by CQE traversal:

- `GraphAdapter` (Protocol) — Read-only interface: get_node, neighbors, edges, out_degree, tags, reverse_neighbors, in_degree
- `SQLiteGraphAdapter` — SQLite implementation with LRU cache
- `DuckDBGraphAdapter` — DuckDB implementation (TDA-enriched, no caching)

## Architecture Diagram (Data Flow)

```
Raw Source Code
      │
      ▼
┌──────────────────────────────┐
│  ParsedSymbol (AST extract)  │ ← C1 (Utility)
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  SymbolFilterGate.validate() │
│  (blacklist → length →      │
│   private → test → lambda)  │
└──────────┬───────────────────┘
           │ GateResult(passed/rejected)
           ▼
┌──────────────────────────────┐
│  SymbolFeatures (extractor)  │ ← C1
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  FeatureGate.validate()      │
│  (cap at 100, priority sort) │
└──────────┬───────────────────┘
           │ GateResult(modified_data)
           ▼
┌──────────────────────────────┐
│  SymbolInfo (enriched)       │
│  = ParsedSymbol + Features   │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  StructuralTags.extract_tags │
│  (kind → pattern → role)    │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  CQE InputGateChain          │
│  (re-validation at pipeline) │
└──────────┬───────────────────┘
           │
           ▼
      CQE Graph (C0/C4)
```

## Design Principles

1. **Immutability**: All types are frozen dataclasses — no mutations, pure data flow
2. **Stateless Gates**: Gate operators are stateless (or static); only orchestrators track statistics
3. **Sequential Chain**: Each gate acts as a pure function: `(input) → GateResult(output | rejection)`
4. **Transform Gates**: Feature gates may modify data (cap features) but never reject — passing with `modified_data`
5. **Tag Merge Policy**: Structural tags are authoritative; LLM tags are additive only

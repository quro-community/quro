# C6: Type System & Validation Chain — Data Flow

## Flow Overview

C6 is a **chain archetype** center where data enters through three entry points and flows sequentially through validation gates and type enrichment. The center processes raw symbol data into validated, enriched symbol info for the CQE pipeline.

## Data Flow Diagram

```
                    ┌─────────────┐
  Entry Point 1 ──► │ SymbolInfo  │ ◄── Entry Point 3
  (ParsedSymbol)    │ (CONVERTER) │     (StructuralTags)
                    └──────┬──────┘
                           │ enrich
                           ▼
               ┌─────────────────────┐
               │  SymbolFeatures     │
               │  (behavioral tags,  │
               │   structural tags,  │
               │   risk anchors,     │
               │   LSH signature)    │
               └──────────┬──────────┘
                          │
                          ▼
┌─────────────────────────────────────────────┐
│         Scanner Gate Chain                  │
│                                             │
│  ParsedSymbol                               │
│      │                                      │
│      ▼                                      │
│  ┌──────────────────┐                       │
│  │ SymbolFilterGate │── GateResult ──► reject│
│  │ (blacklist,      │                       │
│  │  name length,    │                       │
│  │  private, test,  │                       │
│  │  lambda)         │                       │
│  └────────┬─────────┘                       │
│           │ passed                          │
│           ▼                                 │
│  ┌──────────────────┐                       │
│  │ FeatureGate      │── GateResult ──► cap  │
│  │ (cap at 100)     │    (modified_data)    │
│  └────────┬─────────┘                       │
│           │ passed                          │
│           ▼                                 │
│  ┌──────────────────┐                       │
│  │ FileFilterGate   │── GateResult ──► reject│
│  │ (exists, ext,    │                       │
│  │  quroignore,     │                       │
│  │  size, binary)   │                       │
│  └────────┬─────────┘                       │
│           │ passed                          │
└───────────┼─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────┐
│         CQE Input Gate Chain                │
│                                             │
│  Entry Point 2: validate_atom()             │
│      │                                      │
│      ▼                                      │
│  SymbolBlacklistGate ──► GateResult         │
│      │                                      │
│      ▼                                      │
│  FilePathIntegrityGate ──► GateResult       │
│      │                                      │
│      ▼                                      │
│  FeatureCapGate ──► GateResult              │
│      │            (modified_data)           │
└──────┼──────────────────────────────────────┘
       │
       ▼
  ┌─────────┐
  │ CQE     │
  │ Graph   │  (Centers C0, C4)
  └─────────┘
```

## Key Flows

### Flow 1: Symbol Validation (Scanner → Filter → Enrich)
1. `ParsedSymbol` enters from C1 (AST parser)
2. `SymbolFilterGate.validate()` checks: blacklist → name length → private → test → lambda
3. If passed: `SymbolFeatures` are extracted and `FeatureGate.validate()` caps them
4. `SymbolInfo` is created as `ParsedSymbol + SymbolFeatures + fingerprint`
5. Structural tags from `StructuralTags.extract_tags()` are merged

### Flow 2: File Validation (File Filter Chain)
1. File path enters from scanner
2. `FileFilterGate.validate()` checks: exists → is_file → extension whitelist → quroignore → file size → binary detection
3. If rejected, tracked in `rejection_stats`
4. Only passed files proceed to symbol extraction

### Flow 3: CQE Input Validation (Pipeline Re-validation)
1. Entry Point 2: `InputGateChain.validate_atom(symbol_name, file_path, features)`
2. Sequential gates: symbol blacklist → file path integrity → feature cap
3. Returns final `GateResult` for CQE pipeline insertion
4. Rejection stats tracked per reason

### Flow 4: Structural Tag Extraction
1. `extract_tags(kind, source_code, symbol_name, file_path, decorators, call_count)`
2. Applies deterministic rules:
   - Kind-level (async_function → "async")
   - Source-level pattern matching (21 category regex rules)
   - Memory pattern detection
   - Decorator detection
   - Entry point detection
3. `_infer_role()` assigns a role via priority-ordered rules
4. Returns `StructuralTags` (immutable, sorted tuple)

## Data Transformations

| Input | Gate | Output | Side Effects |
|-------|------|--------|--------------|
| `ParsedSymbol` | `SymbolFilterGate` | `GateResult(passed/rejected)` | Rejection stats |
| `SymbolFeatures` | `FeatureGate` | `GateResult(modified_data)` | Cap stats |
| `File path` | `FileFilterGate` | `GateResult(passed/rejected)` | Rejection stats |
| `Atom inputs` | `InputGateChain` | `GateResult(final)` | Rejection stats |
| AST metadata | `extract_tags()` | `StructuralTags` | None (pure) |

## Cross-Center Data Flow

| Direction | Partner | Data | Mechanism |
|-----------|---------|------|-----------|
| Input from | C1 (fanout) | `ParsedSymbol`, raw symbol data | Bridge symbols |
| Input from | C3 (sink) | File I/O, path resolution | Bridge symbols |
| Output to | C0 (hub) | `SymbolInfo`, validated atoms | Bridge symbols |
| Output to | C4 (hub) | Scan results, enriched data | Bridge symbols |

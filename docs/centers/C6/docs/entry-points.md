# C6: Type System & Validation Chain — Entry Points

## Entry Point Summary

| # | Entry Point | Symbol | Role | fwd_mag | in_deg | out_deg | Source File |
|---|-------------|--------|------|---------|--------|---------|-------------|
| 1 | `sym::SymbolInfo` | `SymbolInfo` | CONVERTER | 9.88 | 20 | 17 | `scanner/types.py:75` |
| 2 | `sym::validate::input_gates::49` | `InputGateChain.validate_atom` | CONVERTER | 2.70 | 11 | 8 | `pipeline/cqe/input_gates.py:155` |
| 3 | `sym::StructuralTags` | `StructuralTags` | CONVERTER | 5.36 | 12 | 9 | `deprecated/quro_cli/analysis/structural_tag_extractor.py:131` |

---

## Entry Point 1: `SymbolInfo` (CONVERTER, fwd=9.88)

**Location:** `scanner/types.py:75`
**Role:** CONVERTER — highest forward magnitude in C6 (9.88), high fan-in (20) and fan-out (17).

### Purpose
`SymbolInfo` is the **core enriched symbol type** in the scanner pipeline. It combines:
- `ParsedSymbol` (raw AST data extracted by C1)
- `SymbolFeatures` (behavioral/structural tags + LSH signature)
- Content-based fingerprint (SHA256)
- Optional metadata

### Call Flow
```
ParsedSymbol ──► ScannerGateChain.validate_symbol() ──► SymbolFilterGate.validate()
                                                              │
                                                              ▼
                                                     GateResult(passed?)
                                                              │
                                                    (if passed) ▼
                                              SymbolFeatures extractor
                                                              │
                                                              ▼
                                              FeatureGate.validate() ──► cap
                                                              │
                                                              ▼
                                              SymbolInfo(symbol, features, fingerprint)
                                                              │
                                                              ▼
                                              CQE Pipeline / Graph Insert
```

### Consumers
- `scanner/__init__.py` — scanner entry point
- `scanner/adapters/memory.py` — in-memory storage
- `scanner/adapters/protocol.py` — adapter protocol
- `scanner/orchestrator.py` — scan orchestration

### Entry Strategy
Sequential: Start from `ParsedSymbol` input, follow through `ScannerGateChain` to `SymbolInfo` output.

---

## Entry Point 2: `validate::input_gates::49` (CONVERTER, fwd=2.70)

**Location:** `pipeline/cqe/input_gates.py:155` (method `InputGateChain.validate_atom`)
**Role:** CONVERTER — moderate forward magnitude (2.70), moderate fan-in (11) and fan-out (8).

### Purpose
`InputGateChain.validate_atom()` is the **CQE pipeline re-validation gate**. It runs an atomic symbol through three sequential stateless gates before insertion into the CQE graph:

1. **`SymbolBlacklistGate.validate(symbol_name)`** — Gate 1: Rejects generic names (task_id, path, error, data, value, __init__, etc.)
2. **`FilePathIntegrityGate.validate(file_path)`** — Gate 2: Validates file exists, not quroignored, has directory structure
3. **`FeatureCapGate.validate(features)`** — Gate 3 (Transform): Caps feature list at 1000 to prevent SQLite BLOB overflow

### Call Flow
```
validate_atom(symbol_name, file_path, features)
    │
    ├──► SymbolBlacklistGate.validate(symbol_name)
    │       └── Gate1: blacklisted? → reject
    │
    ├──► FilePathIntegrityGate.validate(file_path)
    │       └── Gate2: exists? not ignored? has dir? → reject
    │
    └──► FeatureCapGate.validate(features)
            └── Gate3: >1000? → cap (pass with modified_data)

    └──► Return GateResult(final)
```

### Rejection Tracking
Rejection reasons are tracked per gate in `rejection_stats` dict:
- `blacklisted_symbol`
- `empty_file_path`, `file_not_found`, `quroignore_match`, `flat_path_no_directory`
- `features_capped`

### Entry Strategy
Sequential: Follow the chain from Gate 1 → Gate 2 → Gate 3. Each gate returns early on rejection.

---

## Entry Point 3: `StructuralTags` (CONVERTER, fwd=5.36)

**Location:** `deprecated/quro_cli/analysis/structural_tag_extractor.py:131`
**Role:** CONVERTER — high forward magnitude (5.36), fan-in (12) and fan-out (9).

### Purpose
`StructuralTags` is the **immutable result container** for deterministic tag extraction. It captures:
- `tags`: Sorted tuple of closed-vocabulary structural tokens
- `role`: Inferred semantic role (ResourceManager, IOHandler, Coordinator, etc.)
- `source`: Tag source provenance (`structural`, `llm`, or `merged`)

### Extraction Flow
```
extract_tags(kind, source_code, symbol_name, file_path, decorators, call_count)
    │
    ├── Kind-level: async_function → "async"
    ├── Source patterns: 21 category regex rules
    ├── Memory pattern: _MEMORY_PATTERN
    ├── Decorator detection
    ├── Entry point detection: known names + decorators
    │
    └── _infer_role(kind, tags, name, path, call_count, decorators)
            └── Priority: ResourceManager > IOHandler > Coordinator >
                          Transformer > Configuration > Container >
                          CoreInfrastructure > Unknown

    └──► StructuralTags(tags=sorted tuple, role, source="structural")
```

### Merge with LLM
```python
merge_with_llm_tags(structural: StructuralTags, llm_tags: Optional[List[str]])
    → StructuralTags(source="merged")
```
LLM tags are appended only if they add new vocabulary. Structural tags are never overridden.

### Entry Strategy
Sequential: Start from `extract_tags()` function call parameters, follow through category rules → role inference → `StructuralTags` output.

---

## Key TDA Metrics

| Entry Point | Role | Forward Mag | Backward Tension | Source Diversity | In | Out |
|-------------|------|-------------|------------------|-----------------|----|-----|
| `SymbolInfo` | CONVERTER | 9.88 | 0.27 | 0.90 | 20 | 17 |
| `validate::input_gates::49` | CONVERTER | 2.70 | 0.21 | 0.85 | 11 | 8 |
| `StructuralTags` | CONVERTER | 5.36 | 0.29 | 0.93 | 12 | 9 |

All three entry points are **CONVERTER** role — they transform input data into typed output, consistent with the chain archetype.

## Navigation Tips

1. **Start at `SymbolInfo`** for the main scanner type pipeline (most connected)
2. **Follow `validate::input_gates::49`** for the CQE re-validation path
3. **Explore `StructuralTags`** for the tag extraction and role inference system
4. **Topology**: The chain flows `ParsedSymbol → [gates] → SymbolInfo → [gates] → CQE graph`

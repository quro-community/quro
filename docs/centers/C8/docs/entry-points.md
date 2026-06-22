# C8 Entry Points — MinHash LSH Sink

## Entry Point Summary

| # | Symbol | File | Line | Kind | TDA Role | Fwd Mag | Bwd Tension |
|---|--------|------|------|------|----------|---------|-------------|
| 1 | `sym::MinHashLSH::lsh_engine::28` | deprecated/.../lsh_engine.py | 28 | class | CONVERTER | 8.7604 | 0.4903 |
| 2 | `sym::MinHashLSH` | core/lsh/minhash.py | 16 | class | CONVERTER | 2.4058 | 0.7147 |
| 3 | `sym::to_dict` | pipeline/cqe/stability.py | 35 | method | TRANSIENT | 0.0 | 0.2692 |

## Entry Point 1: `MinHashLSH` — deprecated lsh_engine.py

**Symbol:** `sym::MinHashLSH::lsh_engine::28`
**File:** `deprecated/quro_cli/analysis/lsh_engine.py`
**Line:** 28
**Kind:** class
**TDA Role:** CONVERTER
**Forward Magnitude:** 8.7604 (high — major transformation node)
**Backward Tension:** 0.4903
**In-degree:** 40 (high fan-in)
**Out-degree:** 30

**Usage context:** This is the **legacy** MinHashLSH used by the CLI/MCP toolchain.
It has 17 callers across C0 and C1:
- `MCPTools.__init__` — initialization
- `MCPTools._find_neighbors` — similarity search
- `MCPTools.query_semantic_inventory` — semantic inventory queries
- `MCPTools.scan_workspace` — workspace scanning
- `MCPTools.index_symbols` — symbol indexing
- `ScanTools.scan` — scan operations
- `SymbolTools._find_neighbors` — symbol neighbor finding
- `SymbolTools.query_semantic_inventory` — semantic queries
- `WorkspaceScanner.__init__` — scanner setup
- Tests: `test_lsh_engine.py`

**API surface:** 10 public methods, 3 private, plus `LSHIndex` class and
`generate_minhash_for_all_symbols` async function.

### Call Flow (C0/C1 → Deprecated MinHashLSH)

```
C0 MCPTools.__init__ ──► MinHashLSH.__init__(config)
C0 MCPTools._find_neighbors ──► MinHashLSH.compute_minhash → compute_bands
C0 MCPTools.query_semantic_inventory ──► LSHIndex.query
C0 MCPTools.scan_workspace ──► MinHashLSH.compute_signature [text→bytes]
C0 MCPTools.index_symbols ──► MinHashLSH.compute_signature
C0 ScanTools.scan ──► MinHashLSH (init + compute)
C1 SymbolTools._find_neighbors ──► MinHashLSH
C1 SymbolTools.query_semantic_inventory ──► LSHIndex.query
C1 WorkspaceScanner ──► MinHashLSH (init)
```

---

## Entry Point 2: `MinHashLSH` — core/lsh/minhash.py

**Symbol:** `sym::MinHashLSH`
**File:** `core/lsh/minhash.py`
**Line:** 16
**Kind:** class
**TDA Role:** CONVERTER
**Forward Magnitude:** 2.4058
**Backward Tension:** 0.7147
**In-degree:** 40
**Out-degree:** 65

**Usage context:** This is the **production** pure MinHash kernel, implementing
the `LSHKernel` protocol. Used by `LSHOrchestrator`.

**API surface:** 2 public methods (`compute_signature`, `compute_similarity`),
5 private methods. Clean protocol-based interface.

### Call Flow (C0 Orchestrator → Production MinHashLSH)

```
C0 LSHOrchestrator.__init__ ──► MinHashLSH.__init__(config)
C0 LSHOrchestrator.compute_and_store ──► MinHashLSH.compute_signature(tokens)
C0 LSHOrchestrator.compute_similarity ──► MinHashLSH.compute_similarity(sig1, sig2)
C0 LSHOrchestrator.find_similar ──► MinHashLSH.compute_similarity (N times)
```

### Internal Call Chain

```
compute_signature(tokens)
  ├── _hash_token(token)              [per token: SHA256 → uint32]
  ├── _compute_minhash(token_hashes)  [vectorized: numpy broadcasting]
  │   └── h(x) = (a*x + b) mod prime  [k=128 hash functions]
  └── _compute_bands_from_signature   [b=16 bands]
      └── _hash_band(band_rows)       [per band: SHA256 → uint64]
```

---

## Entry Point 3: `to_dict` — pipeline/cqe/stability.py

**Symbol:** `sym::to_dict`
**File:** `pipeline/cqe/stability.py`
**Line:** 35
**Kind:** method
**TDA Role:** TRANSIENT
**Forward Magnitude:** 0.0 (leaf node — no outgoing calls)
**Backward Tension:** 0.2692
**In-degree:** 36

**Usage context:** Serialization helper on `StabilityState` dataclass.
Called by `FixPlanStabilityLayer` during index builds.

### Call Flow

```
C3 FixPlanStabilityLayer.commit_plan
  └── StabilityState.save(state_path)
      └── StabilityState.to_dict()
          └── Returns: {
                applied_hashes: sorted(str),
                node_modified_counts: Dict[str,int],
                last_entropy_score: float,
                entropy_history: List[float]
              }
```

---

## Navigation Strategy

As a **sink** archetype with **upstream-first** entry strategy:

1. **Start from upstream**: Trace callers in C0/C1 to understand how MinHashLSH is invoked
2. **Converge on C8 internals**: Then drill into the pure kernel implementation
3. **Two parallel codebases**: Note the deprecated vs. production split — the deprecated
   version has higher forward magnitude (8.76 vs 2.41) because it includes more functionality
   (tokenization, serialization, behavioral tag extraction)

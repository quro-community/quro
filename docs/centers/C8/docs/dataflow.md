# C8 Data Flow — MinHash LSH Sink

## Upstream → C8 Flow

### Primary Data Path: C0/C1 → C8 (MinHashLSH)

```
C0/C1 (callers)
  │
  │  tokens: Set[str]  (code tokens, behavioral tags)
  │  config: LSHConfig (num_hashes=128, num_bands=16, threshold=0.3)
  ▼
C8: MinHashLSH.compute_signature(tokens)
  │
  ├─ _hash_token(token) → int    [SHA256 → uint32]
  ├─ _compute_minhash(token_hashes) → np.ndarray  [vectorized numpy]
  │   └─ h(x) = (a*x + b) mod prime  (k hash functions)
  └─ _compute_bands_from_signature(signature) → List[int]
      └─ _hash_band(band_rows) → int  [SHA256 → uint64]
  │
  ▼
  LSHSignature { hash_values, bands, config }
```

### Secondary Data Path: C0/C1 → C8 (LSHIndex)

```
C0/C1 (callers)
  │
  │  signature: np.ndarray or bytes
  ▼
C8: LSHIndex (deprecated lsh_engine.py)
  │
  ├─ insert(item_id, signature) → None
  │   └─ compute_bands → index into band buckets
  ├─ query(signature, threshold) → [(item_id, similarity)]
  │   └─ band lookup → jaccard_similarity filter → sorted results
  └─ remove(item_id) → None
```

### Orchestrator Path

```
C0: ManifoldAdapter
  │
  │  content: str (source code), metadata: dict
  ▼
C8: LSHOrchestrator.compute_and_store(symbol, content, metadata)
  │
  ├─ _tokenize(content) → Set[str]
  ├─ kernel.compute_signature(tokens) → LSHSignature
  └─ manifold.insert_node(request) → ManifoldNode
```

### Stability Layer Path (to_dict)

```
C3/pipeline: FixPlanStabilityLayer
  │
  │  StabilityState → needs serialization
  ▼
C8: StabilityState.to_dict() → dict
  │
  └─ Serializes: applied_hashes, node_modified_counts,
     last_entropy_score, entropy_history
```

## Data Flow Diagram

```
┌─────────┐   scan()/enrich()    ┌──────────────────┐
│  C0/C1  │ ──────────────────►  │ MinHashLSH        │
│  Callers │                     │ lsh_engine.py:28  │
│  (MCP,   │                     │ (deprecated)      │
│  Scanner)│                     │                   │
└─────────┘                     └────────┬──────────┘
       │                                 │
       │ compute_and_store()             │ query()/insert()
       ▼                                 ▼
┌──────────────────┐           ┌──────────────────┐
│ LSHOrchestrator  │           │ LSHIndex          │
│ orchestrator/    │           │ lsh_engine.py:334 │
│ lsh.py           │           │ (deprecated)      │
└────────┬─────────┘           └──────────────────┘
         │
         ▼
┌──────────────────┐
│ core/lsh/minhash │
│ Pure kernel      │
│ (no I/O)         │
└──────────────────┘
```

## Cross-Center Coupling

| From | To | Mechanism | Score |
|------|----|-----------|-------|
| C0 | C8 | Bridge symbols flowing to shared sinks | 672.288 |
| C1 | C8 | Bridge symbols flowing to shared sinks | 171.358 |
| C3 | C8 | Bridge symbols flowing to shared sinks | 163.367 |

All three coupled centers call C8 via `MinHashLSH` for semantic similarity computation
during indexing, scanning, and enrichment operations. The shared sinks include
`MemoryRegistryAdapter` and `DynamicsState`.

# C5 Data Flow

## 1. Trust Computation Flow

```
TrustSignals (observables)     TrustWeights (config)
        │                            │
        ▼                            ▼
  TrustComputeRequest ──────────▶ TrustEngine.compute_trust()
                                      │
                                      │ 1. Clamp signals
                                      │ 2. base_trust = linear sum
                                      │ 3. stability = drift^4
                                      │ 4. verification factor
                                      │ 5. min(trust, gravity)
                                      ▼
                                 TrustRecord ◀── stored/consumed
```

### Propagation Flow

```
UpstreamDependency[] ───┐
                        ├──▶ TrustPropagationRequest ──▶ TrustEngine.propagate_upstream_trust()
TrustRecord[]      ─────┘                                      │
                                                                │
                          For each symbol:                      │
                            1. Find upstream deps (non-HERITAGE)│
                            2. Compute min upstream trust       │
                            3. Recompute trust with new signal  │
                                                                ▼
                                                      Tuple[TrustRecord]
```

## 2. Self-Heal Flow

```
HealProposal[] ───┐
                  ├──▶ HealRequest ──▶ SelfHealEngine ──▶ HealDecision ──▶ HealResult
TrustScores  ─────┘                                         │
NRTBreaches  ─────┘                                    approved/rejected
                                                          + reason
```

## 3. Shadow I/O Flow

```
ShadowReadRequest ──▶ ShadowAdapter.read() ──▶ ShadowFile
                        │
                        └── Contains DSLAtom[] (DSL operation sequence)

ShadowFile ───┐
              ├──▶ ShadowWriteRequest ──▶ ShadowAdapter.write()
              │
         Symbol, deps, checksum,
         atoms, risks
```

## 4. CQE Policy Composition Flow

```
PrunePolicy ───┐
BoostPolicy ───┤
NormalizePolicy├──▶ CQEPolicy(default|conservative|aggressive)
PathGrammarPolicy┘
                    │
    CQEPolicy is consumed by CQE Kernel (C0) for:
    - Traversal pruning (min_weight, max_hops)
    - Weight boosting (Jaccard similarity)
    - Normalization (minmax/softmax/none)
    - Path grammar constraints (layer transitions)
```

## 5. NRT Breach Detection Flow

```
ShadowRule[] (compiled predicates)
        │
        ▼
BreachCheckRequest ──▶ NRTEngine.check() ──▶ NRTResult
        │                                        │
   symbol, qss_path, qra_path              breach_type, severity
```

## 6. Registry Insert Flow

```
SymbolInsertRequest ──▶ RegistryAdapter.insert_symbol()
                            │
MorphismInsertRequest ──▶ RegistryAdapter.insert_morphism()
                            │
                       MorphismRecord / SymbolRecord
```

## Cross-Center Data Flow

```
C5 (Policy & Trust Hub) ───▶ C0 (Orchestration)
  │                              Consumes: CQEPolicy, CQEMultiTierResult,
  │                              TrustRecord, MorphismRecord
  │
  ├──▶ C1 (Manifold/Graph)
  │       Consumes: ShadowFile, DSLAtom
  │
  ├──▶ C4 (Memory/Symbols)
  │       Consumes: SymbolInsertRequest, MorphismInsertRequest,
  │       FileRecord, SymbolRecord
  │       [SC480 tight coupling cluster]
  │
  └──▶ C3 (Persistence/I/O)
          Consumes: ShadowWriteRequest, FileRecord
```

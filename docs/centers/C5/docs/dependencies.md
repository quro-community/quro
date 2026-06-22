# C5 Dependency Map

## Internal Dependencies

### Module: `policy/trust/`

```
types.py ←── engine.py (consumes TrustSignals, TrustWeights, TrustComputeRequest, etc.)
types.py ←── protocol.py (references types for Protocol signatures)
engine.py ←── protocol.py (implements TrustPolicy Protocol)
```

### Module: `policy/self_heal/`

```
types.py ←── engine.py (consumes HealRequest, HealProposal, etc.)
types.py ←── protocol.py (references types for Protocol signatures)
```

### Module: `policy/nrt/`

```
types.py ←── engine.py (consumes ShadowRule, BreachCheckRequest, NRTResult)
```

### Module: `core/cqe/`

```
types.py (independent, no internal deps)
policy.py (independent, no internal deps)
```

### Module: `adapters/registry/`

```
types.py (independent, no internal deps)
```

### Module: `adapters/shadows/`

```
types.py (independent, no internal deps)
```

### Module: `tda/phase4/`

```
trajectory_planner.py (defines TrajectoryRequest, StepDecision, etc. — types used locally)
```

## Cross-Center Dependencies

### C0 (Orchestration) — Coupling Score: 407.9 (HIGH)

C5 provides types consumed by C0's orchestration layer:
- `CQEPolicy` (prune, boost, normalize, grammar)
- `CQEMultiTierResult` / `CQETier` / `CQERefinedResult`
- `TrustRecord` / `TrustSignals` / `TrustWeights`
- `MorphismRecord` / `SymbolRecord`
- `HealResult` / `HealDecision`
- `ShadowFile` / `DSLAtom`

Shared sinks: `MemoryRegistryAdapter`, `verify_symbol_integrity`, `DynamicsState`

### C4 (Memory/Symbols) — Coupling Score: 96.0 [SC480 Cluster]

Tight coupling cluster SC480 binds C4 and C5:
- `MorphismInsertRequest` (C5 entry point) → C4 symbol operations
- `SymbolInsertRequest` → C4 registry operations  
- `FileRecord` / `SymbolRecord` → shared across both centers
- `ShadowFile` / `ShadowWriteRequest` → shadow file operations

**⚠️ SC480 cluster: Changes to C5 registry types may require C4 changes.**

### C1 (Manifold/Graph) — Coupling Score: 100.1

- `ShadowFile` consumed by C1 graph adapters
- `DSLAtom` operations used for graph traversal trace analysis

### C3 (Persistence/I/O) — Coupling Score: 73.2

- `ShadowWriteRequest` → C3 file I/O
- `FileRecord` → persistence layer

## Coupling Summary Table

| Center | Score | Mechanism | Cluster |
|--------|-------|-----------|---------|
| C0 | 407.9 | Shared sinks + type consumption | — |
| C1 | 100.1 | Shadow type consumption | — |
| C3 | 73.2 | Shadow I/O requests | — |
| C4 | 96.0 | Registry types (bidirectional) | **SC480** |

## Shared Sink Symbols

These symbols are shared across multiple centers, forming the bridges:
- `sym::MemoryRegistryAdapter` — shared by C0, C1, C3, C4, C5, C7, C8
- `sym::verify_symbol_integrity::tools::504` — shared by C0, C1, C3, C4, C5, C7, C8
- `sym::DynamicsState` — shared by C0, C1, C3, C4, C5, C7, C8

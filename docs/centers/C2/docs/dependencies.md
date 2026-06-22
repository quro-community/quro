# C2 Dependencies

## Internal Dependency Graph (within C2)

```
traversal_modes.py ────────────► traversal_orchestrator.py
       │                                │
       │                                ├──► reverse_traverser.py
       │                                ├──► field_guided_traverser.py
       ▼                                ├──► saddle_escape_traverser.py
node_state.py                           └──► upstream_navigator.py
       │                                     │
       ▼                                     │
   tda_bridge.py ◄────────────────────────────┘
       │
       ├──► kernel.py ──► types.py
       │
       └──► transforms.py ──► types.py
       
types.py ◄──── canonial.py
              refiner.py ───► scoring.py
              policy.py

flow_observer.py (core/cqe)
tda/flow_observer.py
tda/mi_warmup.py
```

### Module Dependency Table

| Module | Depends On | Depended By |
|--------|-----------|-------------|
| `traversal_modes.py` | `node_state` | `traversal_orchestrator`, `reverse_traverser`, `saddle_escape_traverser` |
| `traversal_orchestrator.py` | `traversal_modes`, `node_state`, `tda_bridge`, `reverse_traverser`, `field_guided_traverser`, `saddle_escape_traverser`, `upstream_navigator`, `kernel` | C0 |
| `node_state.py` | none (stdlib only) | `traversal_modes`, `tda_bridge`, `traversal_orchestrator` |
| `tda_bridge.py` | `node_state`, TDA subsystem | `traversal_orchestrator`, `field_guided_traverser`, `reverse_traverser`, `saddle_escape_traverser` |
| `kernel.py` | `types` | `traversal_orchestrator` |
| `types.py` | none (stdlib only) | `kernel`, `canonical`, `refiner` |
| `transforms.py` | `types` | C0 (via orchestrator) |
| `policy.py` | none (stdlib only) | C0 |
| `canonical.py` | `types` | C0 |
| `refiner.py` | `types`, `scoring` | C0 |
| `scoring.py` | `types` | `refiner` |
| `reverse_traverser.py` | `tda_bridge` | `traversal_orchestrator` |
| `field_guided_traverser.py` | `tda_bridge` | `traversal_orchestrator`, `saddle_escape_traverser` |
| `saddle_escape_traverser.py` | `traversal_modes`, `field_guided_traverser`, `tda_bridge` | `traversal_orchestrator` |
| `upstream_navigator.py` | TDA data files | `traversal_orchestrator` |
| `flow_observer.py` (core) | none | C0 |
| `flow_observer.py` (tda) | none | TDA pipeline |

## Cross-Center Dependencies

### C0 (Hub) ← C2
C0 is the primary consumer of all C2 functionality:

| C0 Consumer | C2 Provider | Mechanism |
|------------|-------------|-----------|
| `QuroV3Service` | `FlowObserver` (core) | `QuroV3Service.__init__` instantiates `FlowObserver(enabled=...)` |
| `QuroV3Service` | `UpstreamNavigator` | `_init_upstream_navigator()` creates `UpstreamNavigator` from file paths |
| `QuroV3Service` | `TraversalOrchestrator` | via `cqe_query_with_mode()` |
| `QuroV3Service` | `CanonicalLayer` | via `resolve()` calls |
| `QuroV3Service` | `CQEPolicy` | via `IndexBuilder` configuration |
| `QuroV3Service` | `DefaultCQERefiner` | via `cqe_query_with_mode()` |
| `QuroV3Service` | `CQEKernel` | via `_execute_forward` |
| `QuroV3Service` | `transforms.HubNormalizer` | via graph adapter pipeline |

### TDA Pipeline → C2
| TDA Provider | C2 Consumer | Mechanism |
|-------------|------------|-----------|
| Anisotropic field data | `TDABridge` | Node state enrichment |
| Field vectors/scores | `FieldGuidedTraverser` | Energy gradient navigation |
| Backward tension | `UpstreamNavigator` | Sink escape |
| Field roles | `NodeState` | Field role classification |

## External (stdlib) Dependencies

- `dataclasses` — All core types
- `enum` — `NodeRole`, `FieldRole`, `TraversalMode`, etc.
- `heapq` — Kernel priority queue
- `math` — Log computation in HubNormalizer
- `json`, `datetime`, `pathlib`, `typing` — Utilities
- `logging` — Traversal logging

## Boundary Contracts (do NOT explore these internals)

- **TDA pipeline** (tda/): C2 only reads field data through `TDABridge`.
  No direct dependency on TDA internals.
- **Graph adapter** (adapters/graph/): Provided as `GraphProtocol` interface.
  C2 treats it as a pure function.
- **C0 Hub**: Orchestrator consumes `TraversalResult`. Do not explore C0
  internals from C2 docs.

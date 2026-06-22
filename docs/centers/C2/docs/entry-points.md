# C2 Entry Points

## Overview

C2 has 3 declared entry points, all leaf-level functions/methods in the
fanout utility layer. The bottom-up strategy starts from these leaves
and expands outward.

---

## Entry Point 1: `select_traversal_mode`

- **Symbol**: `sym::select_traversal_mode`
- **File**: `core/cqe/traversal_modes.py:70`
- **Kind**: function
- **Role**: TRANSIENT (forward_magnitude=0.0, backward_tension=0.59)
- **In-degree**: 8
- **Out-degree**: 0
- **Intent**: util

### Signature
```python
def select_traversal_mode(
    node_state: NodeState,
    current_mode: TraversalMode = TraversalMode.FORWARD,
) -> tuple[TraversalMode, Optional[str]]:
```

### Decision Tree
1. Isolated node → FORWARD ("isolated_node")
2. Sink node (out=0, in>0) → REVERSE ("sink_detected")
3. Saddle point → SADDLE_ESCAPE ("saddle_point")
4. High-gravity attractor → FIELD_GUIDED ("high_gravity_attractor")
5. Repeller → FIELD_GUIDED ("repeller_escape")
6. Default → FORWARD (None)

### Callers
- `TraversalOrchestrator.traverse()` — primary consumer
- `should_switch_mode()` — mode switch monitor

### Related Symbols
- `TraversalMode` (enum, defined in same file)
- `ModeSwitchEvent` (dataclass, defined in same file)
- `NodeState`, `NodeRole`, `FieldRole` (from `node_state.py`)

---

## Entry Point 2: `FlowObserver` (tda/flow_observer.py:53)

- **Symbol**: `sym::FlowObserver::flow_observer::53`
- **File**: `tda/flow_observer.py:53`
- **Kind**: class
- **Role**: TRANSIENT (forward_magnitude=2.87, in_degree=4, out_degree=30)
- **Intent**: Unknown (TDA pipeline observability)

### Constructor
```python
def __init__(self, output_dir: str = ".quro_context/flow_traces"):
```

### Methods
| Method | Line | Purpose |
|--------|------|---------|
| `observe_phase2_output(symbol, sms)` | 66 | Phase 2 SymbolManifoldState |
| `observe_pass1_output(symbol, cognitive_role)` | 105 | Pass 1 CognitiveRole |
| `observe_pass2_output(symbol, stability)` | 141 | Pass 2 StabilityAssessment |
| `observe_pass3_output(symbol, affordances, attention_weight)` | 179 | Pass 3 Affordances |
| `observe_pass4_output(symbol, context)` | 215 | Pass 4 CognitiveSymbolContext |
| `_add_snapshot(symbol, snapshot)` | 258 | Internal snapshot storage |
| `write_trace(symbol)` | 264 | Write trace to file |
| `write_all_traces()` | 285 | Write all traces |
| `get_trace(symbol)` | 293 | Retrieve trace |
| `print_trace_summary(symbol)` | 304 | Console summary |

### Related Symbols
- `DataSnapshot` (frozen dataclass, line 16)
- `FlowTrace` (dataclass, line 27)
- `to_dict` method on `FlowTrace` (line 37)

---

## Entry Point 3: `to_dict` (tda/flow_observer.py:37)

- **Symbol**: `sym::to_dict::flow_observer::37`
- **File**: `tda/flow_observer.py:37`
- **Kind**: method
- **Role**: Method of `FlowTrace` in `tda/flow_observer.py`
- **Intent**: util

### Signature
```python
def to_dict(self) -> Dict[str, Any]:
```

### Return Structure
```python
{
    "symbol": str,
    "snapshots": [
        {
            "stage": str,
            "timestamp": str,
            "shape": Dict,
            "sample_data": Optional[Dict],
        }
    ]
}
```

### Related Symbols
- `FlowTrace` (containing class)
- `DataSnapshot` (snapshot type)
- `FlowObserver` (creates and consumes FlowTrace)

---

## Derived High-Energy Symbols

### Core Attractors (stable hubs)

| Symbol | Forward Mag | In | Out | File |
|--------|------------|----|-----|------|
| `CanonicalLayer` | 15.24 | 4 | 10 | `core/cqe/canonical.py` |
| `ReverseTraverser` | 12.71 | 4 | 15 | `core/cqe/reverse_traverser.py` |
| `SaddleEscapeTraverser` | 10.57 | 4 | 10 | `core/cqe/saddle_escape_traverser.py` |
| `CQEKernel` | 4.97 | 4 | 5 | `core/cqe/kernel.py` |

### Converters (energy transit)

| Symbol | Forward Mag | In | Out | File |
|--------|------------|----|-----|------|
| `CQEPolicy` | 19.69 | 4 | 19 | `core/cqe/policy.py` |
| `FieldGuidedTraverser` | 9.53 | 8 | 20 | `core/cqe/field_guided_traverser.py` |
| `DefaultCQERefiner` | 8.55 | 12 | 10 | `core/cqe/refiner.py` |
| `TDABridge` | 7.56 | 20 | 49 | `core/cqe/tda_bridge.py` |
| `TraversalOrchestrator` | 12.49 | 8 | 19 | `core/cqe/traversal_orchestrator.py` |

### Transients (leaves)

| Symbol | Forward Mag | In | Out | File |
|--------|------------|----|-----|------|
| `select_traversal_mode` | 0.0 | 8 | 0 | `core/cqe/traversal_modes.py` |
| `FlowObserver` (tda) | 2.87 | 4 | 30 | `tda/flow_observer.py` |

## Coupling to C0 (Hub)

C0 consumes C2 outputs through multiple paths:
- `TraversalOrchestrator.traverse()` for CQE query execution
- `FlowObserver` for pipeline tracing
- `UpstreamNavigator` for sink escape
- `CanonicalLayer` for token resolution
- `CQEPolicy` for index builder configuration

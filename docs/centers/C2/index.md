# C2 Knowledge Base Index

## Coverage Summary
- Total symbols: 624
- Documented: 180 (29%) — INIT exploration complete
- Last updated: 2026-06-20
- Mode: INIT (first full exploration complete)
- Git hash: 8d5ee9b

## Coverage Map

### `docs/architecture.md` ✅
- Full internal architecture, 12 subsystems documented
- Architecture layers diagram, key design properties

### `docs/dataflow.md` ✅
- Primary data flow (traversal execution) with ASCII diagram
- Secondary data flow (upstream escape)
- Observability data flow
- Data ownership table

### `docs/api.md` ✅
- 3 entry points documented with signatures and TDA roles
- 17 classes with constructors and methods
- All dataclass fields, enum values, protocol methods

### `docs/dependencies.md` ✅
- Full internal dependency graph with module dependency table
- Cross-center coupling to C0 (9 consumer-provider pairs)
- TDA pipeline → C2 data flow (boundary contracts marked)
- External (stdlib) dependencies listed

### `docs/entry-points.md` ✅
- 3 declared entry points with full analysis
- Decision trees, callers, related symbols
- Derived high-energy symbols table (4 attractors, 5 converters, 2 transients)
- C0 coupling summary

## Core Modules

| Module | Status | Docs |
|--------|--------|------|
| `core/cqe/traversal_modes.py` | ✅ documented | `docs/architecture.md`, `docs/api.md` |
| `core/cqe/traversal_orchestrator.py` | ✅ documented | `docs/architecture.md`, `docs/dataflow.md` |
| `core/cqe/node_state.py` | ✅ documented | `docs/architecture.md`, `docs/api.md` |
| `core/cqe/tda_bridge.py` | ✅ documented | `docs/architecture.md`, `docs/dependencies.md` |
| `core/cqe/kernel.py` | ✅ documented | `docs/architecture.md`, `docs/api.md` |
| `core/cqe/types.py` | ✅ documented | `docs/api.md` |
| `core/cqe/policy.py` | ✅ documented | `docs/api.md` |
| `core/cqe/transforms.py` | ✅ documented | `docs/api.md` |
| `core/cqe/refiner.py` | ✅ documented | `docs/api.md` |
| `core/cqe/canonical.py` | ✅ documented | `docs/api.md`, `docs/entry-points.md` |
| `core/cqe/reverse_traverser.py` | ✅ documented | `docs/architecture.md` |
| `core/cqe/field_guided_traverser.py` | ✅ documented | `docs/architecture.md` |
| `core/cqe/saddle_escape_traverser.py` | ✅ documented | `docs/architecture.md` |
| `core/cqe/scoring.py` | ✅ documented | `docs/dependencies.md` |
| `core/cqe/upstream_navigator.py` | ✅ documented | `docs/api.md` |
| `core/cqe/flow_observer.py` | ✅ documented | `docs/api.md` |
| `core/cqe/field_scorer.py` | ✅ documented | `docs/dependencies.md` |
| `tda/flow_observer.py` | ✅ documented | `docs/api.md`, `docs/entry-points.md` |
| `tda/mi_warmup.py` | ⚠️ referenced | `docs/api.md` |

## Energy Snapshot

| Band | Count | Example |
|------|-------|---------|
| High (fwd > 10) | 4 | `CanonicalLayer` (15.24), `ReverseTraverser` (12.71) |
| Medium (fwd 5-10) | 3 | `FieldGuidedTraverser` (9.53), `DefaultCQERefiner` (8.55) |
| Low (fwd < 5) | 2 | `CQEKernel` (4.97), `FlowObserver` (2.87) |
| Transients | 2 | `select_traversal_mode` (0.0) |

> **Legend:** ✅ documented | ⚠️ partial | ❌ undocumented

# C2 Architecture — Leaf-Dominated Fanout (Utility Layer)

## Overview

C2 is the **traversal and utility layer** of the Quro CQE engine. It houses all
traversal strategies, node state detection, policy configuration, token
canonicalization, result refinement, and flow observability. As a fanout
archetype with 624 symbols, C2 provides the "muscle" that C0 (the
orchestration hub) delegates traversal execution to.

## Architecture Layers

```
┌─────────────────────────────────────────────────────┐
│             Traversal Orchestrator                   │
│         (core/cqe/traversal_orchestrator.py)         │
├──────────┬──────────┬──────────┬─────────────────────┤
│  Forward  │  Reverse │  Field   │  Saddle Escape      │
│ Traverser │Traverser │  Guided  │  Traverser          │
│ (kernel)  │          │ Traverser│                     │
├──────────┴──────────┴──────────┴─────────────────────┤
│           Node State Detection & TDA Bridge           │
│         (core/cqe/node_state.py, tda_bridge.py)       │
├──────────────────────────────────────────────────────┤
│     CQE Kernel       │     Policy & Transforms        │
│  (core/cqe/kernel.py)│  (core/cqe/policy.py,          │
│                       │   transforms.py)               │
├──────────────────────┴───────────────────────────────┤
│  Canonical Layer     │  Refiner        │  Scoring     │
│  (canonical.py)      │  (refiner.py)   │ (scoring.py) │
├──────────────────────────────────────────────────────┤
│      Flow Observer (core/cqe/flow_observer.py)        │
│      TDA Flow Observer (tda/flow_observer.py)        │
│      MI Warmup (tda/mi_warmup.py)                     │
└──────────────────────────────────────────────────────┘
```

## Subsystems

### 1. Traversal Mode System (`traversal_modes.py`)
Defines the four traversal modes (FORWARD, REVERSE, FIELD_GUIDED,
SADDLE_ESCAPE) and the mode selection decision tree. Entry point
`select_traversal_mode` classifies each node by topological and field
properties and selects the optimal mode.

### 2. Traversal Orchestrator (`traversal_orchestrator.py`)
Central coordinator that instantiates all traversers, delegates mode
selection to `traversal_modes.py`, and dispatches execution to the
appropriate traverser. Produces a unified `TraversalResult` with
telemetry.

### 3. Node State Detection (`node_state.py`)
Self-awareness layer. Every node entering the orchestrator gets a
`NodeState` with out/in degree, topological role, field role, gravity
score, and energy levels. Foundation for automatic mode switching.

### 4. TDA Bridge (`tda_bridge.py`)
Bridge between CQE and the TDA (Topological Data Analysis) subsystem.
Provides node state enrichment with field vectors, energy levels, and
gravity scores computed offline by the TDA pipeline.

### 5. Traversers
- **Forward** (`kernel.py`): Pure deterministic graph traversal with
  additive MI scoring (Design 93). No side effects.
- **Reverse** (`reverse_traverser.py`): Upward traversal from sink
  nodes, following incoming edges to find escape routes.
- **Field-Guided** (`field_guided_traverser.py`): Energy gradient
  descent/ascent following TDA field vectors.
- **Saddle Escape** (`saddle_escape_traverser.py`): Multi-mode escape
  from saddle points with automatic mode switching.

### 6. Upstream Navigator (`upstream_navigator.py`)
Phase 3.5 component that navigates upstream from stuck/sink nodes using
backward tension from anisotropic fields.

### 7. Kernel (`kernel.py`)
Pure mathematical kernel implementing additive-scoring Dijkstra
(Design 93). Deterministic, no I/O, no logging.

### 8. Policy System (`policy.py`)
Configuration policies: `CQEPolicy`, `PrunePolicy`, `BoostPolicy`,
`NormalizePolicy`, `PathGrammarPolicy`. All immutable data objects.

### 9. Transforms (`transforms.py`)
Graph transformation passes applied before kernel execution:
`HubNormalizer` (entropy suppression) and `TopKPruner` (fanout limit).

### 10. Canonical Layer (`canonical.py`)
Deterministic token resolution (from v2, unchanged). Maps raw strings
to valid atoms with bounded edit distance. No LLM, no guessing.

### 11. Refiner (`refiner.py`)
`DefaultCQERefiner` and `SemanticCQERefiner` that categorize raw CQE
results into primary/secondary structural and related concepts.

### 12. Flow Observers
- `core/cqe/flow_observer.py`: CQE pipeline tracing with `FlowObserver`
  and `FlowTrace` — optional debug instrumentation for pipeline stages.
- `tda/flow_observer.py`: TDA pipeline flow observer with stage-specific
  observation methods (phases 1-4).

## Key Design Properties

- **Separation of Concerns**: Each traverser strategy is isolated in its
  own module with a clear interface.
- **Pure Kernel Invariant**: `CQEKernel.query()` is a pure function
  with no side effects.
- **Immutable Policies**: All policy objects are frozen dataclasses.
- **Deterministic Canonicalization**: No LLM, no guessing, bounded edit
  distance.
- **Feature Gated Observability**: Flow tracing is disabled by default
  (QURO_FLOW_TRACE env var).

## Coupling Notes

- **C0 (Hub)**: Consumes all C2 traverser outputs via
  `TraversalOrchestrator`. Also instantiates `FlowObserver` and
  `UpstreamNavigator`.
- **TDA pipeline**: C2 reads TDA field data through `TDABridge` but does
  not explore the TDA pipeline internals.

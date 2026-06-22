# C2 Data Flow

## Primary Data Flow: Traversal Execution

```
                          ┌──────────────┐
                          │   C0 (Hub)   │
                          │ (Orchestrates)│
                          └──────┬───────┘
                                 │ start_node, max_depth, top_k
                                 ▼
                    ┌────────────────────────┐
                    │  TraversalOrchestrator │
                    └────────┬───────────────┘
                             │
               ┌─────────────┼─────────────┐
               │             │             │
               ▼             ▼             ▼
        ┌──────────┐ ┌────────────┐ ┌──────────────┐
        │get_node_ │ │traversal_  │ │select_traver-│
        │state()   │ │modes.py    │ │sal_mode()    │
        └────┬─────┘ └────────────┘ └──────┬───────┘
             │                             │
             ▼                             ▼
      ┌──────────────┐          ┌──────────────────┐
      │ TDABridge    │          │ NodeState +      │
      │ (TDA field)  │          │ TraversalMode    │
      └──────────────┘          └────────┬─────────┘
                                         │ mode selected
                                         ▼
                          ┌──────────────────────────┐
                          │  Dispatch to Traverser   │
                          └──────┬───────┬──────┬────┘
                                 │       │      │
              ┌──────────────────┘       │      └──────────────┐
              ▼                          ▼                     ▼
    ┌─────────────────┐     ┌───────────────────┐  ┌──────────────────┐
    │ Forward         │     │ Reverse           │  │ SaddleEscape     │
    │ (CQEKernel)     │     │ (ReverseTraverser)│  │ (SaddleEscape    │
    └────────┬────────┘     └────────┬──────────┘  │  Traverser)      │
             │                       │             └────────┬─────────┘
             ▼                       ▼                      ▼
    ┌─────────────────┐     ┌───────────────────┐  ┌──────────────────┐
    │ CQEResult       │     │ ReverseTraversal  │  │ SaddleEscape     │
    │ (max_weights,   │     │ Result            │  │ Result           │
    │  predecessors)  │     └───────────────────┘  └──────────────────┘
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ DefaultCQERefine│ ◄── CanonicalLayer (token resolution)
    │ r.refine()      │
    └────────┬────────┘
             │ CQERefinedResult
             ▼
    ┌─────────────────┐
    │ TraversalResult │ ──► C0 (Hub)
    └─────────────────┘
```

## Secondary Data Flow: Upstream Escape

```
                    ┌──────────────┐
                    │ Forward stuck │
                    │ (is_stuck)   │
                    └──────┬───────┘
                           │ escape_sink(start_node)
                           ▼
                  ┌────────────────────┐
                  │ UpstreamNavigator  │
                  │ (Phase 3.5)        │
                  └────────┬───────────┘
                           │ finds best upstream source
                           ▼
                  ┌────────────────────┐
                  │ EscapeResult       │
                  │ (escape_to, conf)  │
                  └────────┬───────────┘
                           │ resume forward traversal from escape_to
                           ▼
                  ┌────────────────────┐
                  │ _execute_forward() │
                  └────────────────────┘
```

## Observability Data Flow

```
CQE Pipeline Stage
       │
       │ data + stage name
       ▼
┌────────────────┐     ┌────────────────┐
│ FlowObserver   │     │ TDA FlowObserv │
│ (core/cqe/)    │     │ er (tda/)      │
└───────┬────────┘     └───────┬────────┘
        │                      │
        ▼                      ▼
┌────────────────┐     ┌────────────────┐
│ FlowTrace      │     │ FlowTrace      │
│ (query_id,     │     │ (symbol,       │
│  snapshots[])  │     │  snapshots[])  │
└────────────────┘     └────────────────┘
        │                      │
        ▼                      ▼
┌────────────────┐     ┌────────────────┐
│ to_dict()      │     │ to_dict()      │
│ (serialize)    │     │ (serialize)    │
└────────────────┘     └────────────────┘
```

## Data Ownership

| Data Type | Producer | Consumer | Storage |
|-----------|----------|----------|---------|
| `NodeState` | `TDABridge` | `TraversalOrchestrator`, `select_traversal_mode` | Transient |
| `TraversalMode` | `select_traversal_mode` | `TraversalOrchestrator` dispatchers | Transient |
| `CQEResult` | `CQEKernel` | `DefaultCQERefiner` | Transient |
| `CQERefinedResult` | `DefaultCQERefiner` | Caller (C0) | Transient |
| `TraversalResult` | `TraversalOrchestrator` | Caller (C0) | Transient |
| `FlowTrace` | `FlowObserver` | Debug consumer | Memory/File |
| `EscapeResult` | `UpstreamNavigator` | `TraversalOrchestrator` | Transient |

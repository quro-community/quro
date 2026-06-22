# TDA Phase-1: Pure Graph Observation Layer

**Status**: Implementation Complete  
**Design Doc**: `docs/designs/74-TDA-PHASE1-DESIGN-v2.md`

---

## Overview

Phase-1 is an **offline batch processor** that records atomic graph traversal events without interpretation. It produces a pure observation log that Phase-2 can analyze to compute manifold insights.

**Key Principle**: Phase-1 is a "graph film recorder" — it captures raw footage, not analysis.

---

## Architecture

```
Phase-1: Observation Layer   (raw graph event log)
Phase-2: Inference Layer     (manifold analysis) [TODO]
Phase-3: LLM Enrichment      (runtime context)   [TODO]
```

---

## Prerequisites

**Before running Phase-1, you must build the symbol index:**

```bash
# Build symbol index (required first step)
./.venv/bin/python -m quro_v3.build_index
```

This scans your workspace and creates the symbol registry that Phase-1 needs.

---

## Usage

### Basic Usage

```bash
# Run full offline traversal
./.venv/bin/python -m quro_v3.tda.phase1
```

**Output**:
```
[Phase-1] Starting offline manifold observation...
[Phase-1] Loaded 1,247 symbols from registry
Processing symbols: 100%|████████████| 1247/1247 [03:42<00:00, 5.61it/s]
[Phase-1] Complete: 1,247 symbols processed
[Phase-1] Events written: 45,832
[Phase-1] Duration: 3m 42s
[Phase-1] Output: .quro_context/tda/phase1/graph_events.jsonl
[Phase-1] ✓ Complete
```

### Incremental Updates

After code changes, run incremental mode to only process new/changed symbols:

```bash
./.venv/bin/python -m quro_v3.tda.phase1 --incremental
```

### Custom Parameters

```bash
# Higher tau (more selective), deeper traversal
./.venv/bin/python -m quro_v3.tda.phase1 \
  --tau 0.1 \
  --max-depth 5 \
  --output /tmp/phase1_deep.jsonl
```

### All Options

```bash
python -m quro_v3.tda.phase1 --help

Options:
  --output PATH         Output JSONL file path
  --registry-db PATH    Symbol registry database path
  --graph-db PATH       Graph database path
  --tau FLOAT           MI-gate threshold (default: 0.05)
  --max-depth INT       Maximum BFS depth (default: 3)
  --incremental         Skip already-processed symbols
```

---

## Output Format

Phase-1 produces a JSONL event log with three event types:

### 1. NODE_VISIT

Records that a node was visited during traversal.

```json
{
  "event_type": "NODE_VISIT",
  "event_id": "uuid",
  "timestamp": 1710000000,
  "query_id": "uuid",
  "node": {
    "id": "sym::get_node",
    "kind": "method",
    "file_path": "quro_v3/core/graph/engine.py",
    "line_number": 142,
    "signature": "async def get_node(self, node_id: str) -> Node"
  },
  "visit_context": {
    "depth": 2,
    "predecessor": "sym::cqe_query",
    "via_edge_type": "CALL"
  }
}
```

### 2. EDGE_TRAVERSE

Records that an edge was traversed during BFS.

```json
{
  "event_type": "EDGE_TRAVERSE",
  "event_id": "uuid",
  "timestamp": 1710000000,
  "query_id": "uuid",
  "edge": {
    "src": "sym::get_node",
    "dst": "sym::append",
    "edge_type": "CALL",
    "weight": 0.71,
    "direction": "outbound"
  },
  "traverse_context": {
    "depth": 2,
    "tau_threshold": 0.05,
    "passed_gate": true
  }
}
```

### 3. PATH_COMPLETE

Records a complete path from entry to target.

```json
{
  "event_type": "PATH_COMPLETE",
  "event_id": "uuid",
  "timestamp": 1710000000,
  "query_id": "uuid",
  "path": {
    "nodes": ["sym::cqe_query", "sym::get_node", "sym::append"],
    "edges": [
      {"type": "CALL", "weight": 0.89},
      {"type": "CALL", "weight": 0.71}
    ],
    "total_length": 2
  },
  "path_context": {
    "entry_point": "sym::cqe_query",
    "target": "sym::append",
    "is_shortest": true
  }
}
```

---

## What Phase-1 Does NOT Do

Phase-1 is a **pure observation layer**. It does NOT:

- ❌ Aggregate (count, sum, mean, variance)
- ❌ Normalize (percentiles, softmax, z-score)
- ❌ Interpret (role, importance, anomaly)
- ❌ Simulate (tau sweep, what-if analysis)
- ❌ Compare (cross-node, cross-category)

**All of these are Phase-2 operations.**

---

## Validation

Run tests to verify Phase-1 purity:

```bash
./.venv/bin/pytest tests/test_tda_phase1.py -v
```

**Key tests**:
- `test_no_aggregation`: Ensures no count/mean/variance in output
- `test_no_interpretation`: Ensures no role/hub/bridge labels
- `test_start_query`: Validates query metadata logging
- `test_log_node_visit`: Validates node visit events
- `test_log_edge_traverse`: Validates edge traverse events
- `test_log_path_complete`: Validates path complete events

---

## Integration with Git Hooks

Add to `.git/hooks/post-commit` for automatic incremental updates:

```bash
#!/bin/bash
echo "Running Phase-1 TDA analysis..."
./.venv/bin/python -m quro_v3.tda.phase1 --incremental
```

---

## Performance

**No real-time constraints** — Phase-1 is offline batch processing.

**Estimated runtime**:
- Small codebase (100-500 symbols): ~30 seconds - 2 minutes
- Medium codebase (500-2000 symbols): ~2-10 minutes
- Large codebase (2000-10000 symbols): ~10-60 minutes

**Storage**:
- ~200-500 bytes per event
- ~30-100 events per symbol
- For 1K symbols: ~6-50 MB JSONL
- gzip compression: 10-20x reduction

---

## Next Steps

1. **Phase-2 Implementation**: Manifold inference layer (compute percentiles, entropy, role emergence)
2. **Phase-3 Implementation**: LLM enrichment layer (runtime context injection)
3. **Optimization**: Parallel processing, distributed execution, caching

---

## References

- **Design 74**: TDA Phase-1 Design (v2)
- **Design 73**: TDA Specification
- **Design 49**: CQE Protocol

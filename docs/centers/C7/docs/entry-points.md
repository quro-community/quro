# C7 Entry Point Analysis — Shadow Draft & Tools Chain

## Entry Points Summary

| Entry Point | Role | Forward Mag | In Degree | Out Degree | Category |
|-------------|------|-------------|-----------|------------|----------|
| `get_in_neighbors` | CONVERTER | 2.54 | 51 | 36 | TDA Graph |
| `get_draft_status::shadow_draft_tools::252` | CONVERTER | 1.42 | 15 | 8 | Shadow Draft |
| `shutdown::typescript_analyzer::79` | CONVERTER | 2.31 | 15 | 8 | TS Analyzer |

## Detailed Analysis

### EP1: `get_in_neighbors(node: str) → List[str]`

- **Files:** tda/adapters/file_graph.py (7 implementations), tda/interfaces/graph.py (abstract)
- **Role:** CONVERTER — transforms graph structure queries into neighbor lists
- **Forward Magnitude:** 2.54 (moderate forward flow)
- **Source Diversity:** 0.74 (diverse calling contexts)
- **In/Out Degree:** 51 in / 36 out (high-traffic graph node)
- **Callers:** TDA phase 3-5 components (center detection, inter-center graph)
- **Strategy:** Sequential — look up reverse adjacency matrix

**Flow:**
```
get_in_neighbors(node)
  → _ensure_loaded()
    → load graph from filesystem
  → _in_matrix.get(node, [])
    → return cached adjacency
```

**Entry strategy for this entry point:** Start from `tda/adapters/file_graph.py` (concrete implementations), trace upward to callers in TDA phases 3-5.

---

### EP2: `get_draft_status(symbol: str) → Dict`

- **Files:**
  - `shadow/shadow_draft_tools.py:252` (core implementation)
  - `mcp/tools/shadow_tools.py:148` (MCP wrapper)
  - `mcp/tools_modular.py:367` (modular MCP wrapper)
  - `mcp/tools.py:1854` (monolithic MCP wrapper)
- **Role:** CONVERTER — transforms symbol name into draft status
- **Forward Magnitude:** 1.42 (low forward flow — query-only)
- **Source Diversity:** 0.87 (many calling contexts)
- **In/Out Degree:** 15 in / 8 out

**Flow:**
```
get_draft_status(symbol)
  → ShadowDraftManager.get_draft_status(symbol)
    → lookup self.drafts[symbol]
      → return {ok, status, draft_id, risk_score, warnings, ...}
```

**Entry strategy for this entry point:** Start at `shadow/shadow_draft_tools.py` (core), then expand to:
1. `mcp/tools/shadow_tools.py` — MCP wrapper layer
2. `mcp/tools.py` — monolithic MCPTools class
3. `mcp/tools_modular.py` — modular MCPTools class

---

### EP3: `shutdown()` (TypeScriptAnalyzer)

- **File:** `analysis/typescript_analyzer.py:79`
- **Role:** CONVERTER — terminates analyzer + probe subprocess
- **Forward Magnitude:** 2.31 (moderate — triggers subprocess termination chain)
- **Source Diversity:** 0.86
- **In/Out Degree:** 15 in / 8 out
- **Callers:** MCPTools.shutdown() (tools.py:97), tools_modular.py:239

**Flow:**
```
shutdown()
  → if self.probe:
    → await self.probe.stop()
      → kill ts-node subprocess
    → self.probe = None
    → self._probe_available = False
```

**Entry strategy for this entry point:** Start at `analysis/typescript_analyzer.py`, then:
1. `analysis/typescript_probe.py` — probe subprocess management
2. `mcp/tools.py` — parent context
3. `mcp/tools_modular.py` — parent context

## Sequential Chain Traversal Strategy

Since C7 is a **chain archetype**, traverse in this order:

1. **L1 — Entry Points** (get_in_neighbors → get_draft_status → shutdown)
2. **L2 — MCP Tool Facade** (MCPTools → ShadowTools → SymbolTools)
3. **L3 — Core Logic** (ShadowDraftManager → TypeScriptAnalyzer → CQETools)
4. **L4 — I/O Layer** (shadow filesystem → database → registry operations)
5. **L5 — Downstream** (C0 Hub → C1 Fanout → C3 Sink — boundary only)

## High-Energy Symbols (priority exploration candidates)

| Symbol | Forward Mag | Role | Priority |
|--------|-------------|------|----------|
| `stop::typescript_probe::118` | 29.62 | CONVERTER | HIGH |
| `get::registry::40` | 16.38 | CONVERTER | HIGH |
| `commit_reasoning::qra_tools::68` | 10.49 | CONVERTER | HIGH |
| `call_graph::call_graph_tools::36` | 10.11 | CONVERTER | HIGH |
| `cqe_diagnose::cqe_tools::871` | 9.76 | CONVERTER | HIGH |
| `run_full_traversal::batch_processor::50` | 7.11 | CONVERTER | HIGH |
| `distill_patch_context::symbol_tools::723` | 5.60 | CONVERTER | MEDIUM |
| `cqe_get_mi_stats::cqe_tools::1150` | 4.79 | CONVERTER | MEDIUM |
| `build_reverse_index::registry_v2::293` | 4.09 | CONVERTER | MEDIUM |

# C7 Knowledge Base Index — Shadow Draft & Tools Chain

## Coverage Summary
- **Total symbols:** 139
- **Documented:** 139 (100%)
- **Last updated:** 2026-06-20
- **Mode:** INIT (initial full exploration completed)
- **Archetype:** Chain (Balanced Chain — Transitional Layer)
- **Coupling cluster:** SC70 (with C0, C1, C3, C8)

## Coverage Map

| Document | Status | Coverage |
|----------|--------|----------|
| `docs/architecture.md` | ✅ complete | 5 layers, 14 components |
| `docs/dataflow.md` | ✅ complete | 5 primary flows + cross-center |
| `docs/api.md` | ✅ complete | 50+ API surfaces documented |
| `docs/dependencies.md` | ✅ complete | Internal + cross-center + external |
| `docs/entry-points.md` | ✅ complete | 3 EPs + high-energy symbols |

## Core Modules

| Module | Status | Docs | Role |
|--------|--------|------|------|
| Shadow Draft Manager | ✅ documented | architecture, dataflow, api | Core chain |
| TypeScript Analyzer | ✅ documented | architecture, dataflow, api, entry-points | Entry point |
| TDA Graph Interface | ✅ documented | architecture, entry-points | Entry point |
| CQE Tools | ✅ documented | api, dependencies | Pipeline |
| Registry Operations | ✅ documented | api, dependencies | I/O Layer |
| MCP Tool Facade | ✅ documented | architecture, dataflow | Orchestration |

## Symbol Categories

| Category | Count | Examples |
|----------|-------|----------|
| Entry Points (CONVERTER) | 3 | `get_in_neighbors`, `get_draft_status`, `shutdown` |
| Shadow Draft (CONVERTER) | 15 | `create_shadow_draft`, `eject_shadow_draft`, `read_shadow` |
| TypeScript Analysis (CONVERTER) | 12 | `initialize`, `get_symbol_at_position`, `find_definition` |
| CQE Pipeline (CONVERTER) | 10 | `cqe_diagnose`, `cqe_query`, `cqe_train_mi` |
| Registry/DB (CONVERTER + EMITTER) | 18 | `insert_symbol`, `get_symbol_by_name`, `build_reverse_index` |
| Scanner (CONVERTER) | 6 | `scan_workspace`, `index_symbols`, `enrich` |
| Session Tools (CONVERTER) | 3 | `update_session`, `get_morph_alerts` |
| Other Tools (CONVERTER) | 72 | Various utility and tool symbols |

## Energy Snapshot

- **Sampled at:** 2026-06-20
- **High-energy symbols (>5.0 forward mag):** 5
- **Stable attractors:** 0 (no energy accumulation in chain archetype)
- **Top energy symbols:**
  1. `stop::typescript_probe::118` — FM: 29.62
  2. `get::registry::40` — FM: 16.38
  3. `commit_reasoning::qra_tools::68` — FM: 10.49
  4. `call_graph::call_graph_tools::36` — FM: 10.11
  5. `cqe_diagnose::cqe_tools::871` — FM: 9.76

## Key Metrics

| Metric | Value |
|--------|-------|
| Total symbols | 139 |
| Coverage | 100% |
| CONVERTER symbols | ~125 |
| EMITTER symbols | ~14 |
| CORE_ATTRACTOR symbols | 0 |
| SINK symbols | 0 |
| C0 coupling score | 632.92 |
| C1 coupling score | 150.60 |
| C3 coupling score | 140.53 |

> **Legend:** ✅ documented | ⚠️ partial | ❌ undocumented

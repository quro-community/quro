# C7 Architecture — Shadow Draft & Tools Chain

**Archetype:** Chain (Balanced Chain — Transitional Layer)
**Size:** 139 symbols
**Entry Strategy:** Sequential

## Overview

C7 is a **transitional chain** that bridges the MCP tool interface layer (C0 Hub) to downstream service layers. It pipelines code generation via shadow drafts, TypeScript analysis, CQE queries, and registry operations through a sequential converter chain.

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      L1 — Entry Points                          │
│  get_in_neighbors (TDA Graph)                                   │
│  get_draft_status (Shadow Draft Tools)                          │
│  shutdown (TypeScript Analyzer)                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     L2 — MCP Tool Facade                         │
│  MCPTools (tools.py)                MCPToolsModular             │
│  ShadowTools (shadow_tools.py)      SymbolTools                 │
│  CallGraphTools                     SessionTools                │
└─────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                  ▼
┌───────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  L3a — Shadow     │ │ L3b — TS     │ │ L3c — CQE/Search │
│  Draft Pipeline   │ │ Analyzer     │ │ Pipeline          │
│                   │ │              │ │                   │
│ ShadowDraftMgr    │ │ TypeScript   │ │ CQETools          │
│  └─create_draft   │ │  Analyzer    │ │  └─diagnose       │
│  └─eject_draft    │ │  └─initialize│ │  └─get_mi_stats   │
│  └─get_status     │ │  └─shutdown  │ │  └─query          │
│  └─approve_heal   │ │  └─diagnostics│ │  └─train_mi      │
│                   │ │  └─resolve    │ │                   │
│ MonteCarloSim     │ │ TypeScript    │ │ CQECommands       │
│ DSLAtomParser     │ │  Probe        │ │  └─run_update     │
│  └─parse_sequence │ │  (subprocess) │ │  └─run_build      │
│  └─validate_seq   │ │              │ │  └─run_rebuild    │
│  └─build_graph    │ │              │ │  └─run_query      │
│  └─detect_deadlock│ │              │ │                   │
│  └─gen_skeleton   │ │              │ │ QRA Tools          │
└───────────────────┘ └──────────────┘ │  └─commit_chain    │
                                       │  └─commit_reasoning│
            │                  │        │  └─get_chain       │
            ▼                  ▼        └──────────────────┘
┌───────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  L4a — Shadow IO  │ │ L4b — DB/    │ │ L4c — Registry   │
│  (Filesystem)     │ │ Registry     │ │ Operations        │
│                   │ │ Persistence  │ │                   │
│ read/write_shadow │ │              │ │ insert_symbol     │
│ delete_shadow     │ │ connect/     │ │ get_symbol_by_name│
│ list_shadows      │ │ disconnect   │ │ build_rev_index   │
│ validate_shadow   │ │ health_check │ │ insert_morphism   │
│ simulate_shadow   │ │ init/close   │ │ get_morphisms     │
│ detect_drift      │ │ get_node     │ │ upsert_node       │
│                   │ │ delete_node  │ │ delete_node       │
└───────────────────┘ └──────────────┘ └──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     L5 — Downstream Services                     │
│  C0 (Hub — Orchestration)    C1 (Fanout — Utilities)           │
│  C3 (Sink — I/O/Persistence)                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Component Roles

| Role | Count | Symbols |
|------|-------|---------|
| CONVERTER | ~125 | All 3 entry points + most internal symbols |
| EMITTER | ~14 | `get_symbol_by_name::protocol`, `compute_checksum::protocol`, `read_shadow::protocol`, `delete_shadow::protocol`, `list_shadows::protocol` |

No CORE_ATTRACTOR or SINK nodes detected (typical for chain archetype — no energy accumulation).

## Key Classes

1. **ShadowDraftManager** — Manages shadow drafts with Monte Carlo validation
2. **TypeScriptAnalyzer** — TypeScript code analysis with tree-sitter fallback
3. **TypeScriptProbe** — Subprocess-based TypeScript analysis via ts-node
4. **MCPTools** — 40+ tool facade for AI agents
5. **ShadowTools** — Shadow draft tool category
6. **CQETools** — CQE query and MI training pipeline
7. **MonteCarloSimulator** — Concurrent simulation engine for risk assessment
8. **DSLAtomParser** — Parses atom sequences into execution graphs

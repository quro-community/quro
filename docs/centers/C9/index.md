# C9 Knowledge Base Index

> Center C9 — Fanout Utility Layer | 74 symbols | Archetype: fanout
> Part of SC38 structural cluster (C0, C1, C3, C7, C9)

## Coverage Summary

| Metric | Value |
|--------|-------|
| Total symbols | 74 |
| Documented entry points | 3 / 3 (100%) |
| Overall doc coverage | ~4% (entry points documented, ~68 remaining) |
| Last updated | 2026-06-20 |
| Mode | POPULATED |

## Entry Points

All three C9 entry points are **TRANSIENT** leaf utilities (0 forward edges, >0 backward tension):

| Entry Point | File:Line | Role | In-Degree | Docs |
|-------------|-----------|------|-----------|------|
| `sym::get_description` | `service/cqe_service.py:30` | TRANSIENT | 50 | ✅ |
| `sym::get_help` | `cli/commands/cqe.py:173` | TRANSIENT | 71 | ✅ |
| `sym::parse_typescript` | `deprecated/quro_cli/analysis/treesitter_parser.py:53` | TRANSIENT | 16 | ✅ |

## Structural Profile

| Aspect | Value |
|--------|-------|
| Archetype | fanout |
| Entry strategy | expand_outward |
| Structural cluster | SC38 (C0, C1, C3, C7, C9) |
| Strongest coupling | C1 (228), C7 (157), C0 (154), C3 (154) |
| Stable ID | `da9ee896a8af` |
| Members hash | `09e6108d...` |

## Documentation Index

| Doc | Path | Description |
|-----|------|-------------|
| Architecture | [docs/architecture.md](docs/architecture.md) | Structural layout, file map, TDA profile |
| Data Flow | [docs/dataflow.md](docs/dataflow.md) | Fanout patterns, flow metrics, data per entry point |
| Entry Points | [docs/entry-points.md](docs/entry-points.md) | Full reference for all 3 entry points |

> **Legend:** ✅ documented | ⚠️ partial | ❌ undocumented

# C9 Architecture — Fanout Utility Layer

> Center C9 | Archetype: fanout | 74 symbols | SC38 cluster

## Overview

C9 is a **fanout utility layer** within the Quro codebase. It comprises three entry-point utility methods that are consumed across the orchestration (C0), storage (C1), I/O (C3), and shadow/draft (C7) centers. All three entry points share a **TRANSIENT** role in the anisotropic field — they have zero forward edges (no callees) and high backward tension, meaning they are leaf utilities called by many upstream consumers.

## Symbol Distribution

| Category | Count | Examples |
|----------|-------|----------|
| Entry points (TRANSIENT) | 3 | `sym::get_description`, `sym::get_help`, `sym::parse_typescript` |
| Parent classes (in-cluster) | 2 | `sym::BaseService`, `sym::BaseCommand` |
| Parent class (deprecated) | 1 | `sym::TreeSitterParser` |
| Other members | ~68 | Various utility methods in service, CLI, and deprecated modules |

## File Map

| File | Role | Entry Points |
|------|------|-------------|
| `service/cqe_service.py` | CQE service class | `sym::get_description` (line 30) |
| `service/base.py` | Base service abstraction | Defines `get_description` (line 34) — inherited by all services |
| `service/tda_service.py` | TDA service class | Calls `get_description` in capabilities (line 81) |
| `service/scanner_service.py` | Scanner service class | Calls `get_description` in capabilities (line 53) |
| `service/visualization_service.py` | Visualization service class | Calls `get_description` in capabilities (line 67) |
| `cli/commands/cqe.py` | CQE CLI commands | `sym::get_help` (line 173) on `CQEListCommand` |
| `cli/base.py` | Base CLI command abstraction | Defines `get_help` (line 28) — inherited by all commands |
| `cli/main.py` | CLI entry point | Consumes `command.get_help()` for help text (line 91) |
| `cli/commands/tda.py` | TDA CLI commands | 3 `get_help` overrides (lines 22, 107, 191) |
| `cli/commands/tda_pipeline.py` | TDA pipeline CLI | 2 `get_help` overrides (lines 58, 589) |
| `cli/commands/scanner.py` | Scanner CLI | `get_help` override (line 22) |
| `cli/commands/visualize.py` | Visualize CLI | `get_help` override (line 21) |
| `deprecated/quro_cli/analysis/treesitter_parser.py` | Tree-sitter parser | `sym::parse_typescript` (line 53) |

## TDA Profile

| Entry Point | Role | Forward Mag | Backward Tension | In-Degree | Out-Degree |
|-------------|------|-------------|-----------------|-----------|------------|
| `sym::get_description` | TRANSIENT | 0.0 | 0.309 | 50 | 0 |
| `sym::get_help` | TRANSIENT | 0.0 | 0.042 | 71 | 0 |
| `sym::parse_typescript` | TRANSIENT | 0.0 | 0.463 | 16 | 0 |

All three entry points are pure leaf nodes — they implement behavior (service description, CLI help, TS parsing) but do not call deeper into the codebase.

## Coupling

C9 sits inside **structural cluster SC38** alongside C0 (hub, 154 coupling), C1 (fanout, 228 coupling), C3 (hub, 154 coupling), and C7 (chain, 157 coupling). The strongest coupling is to C1 (228), indicating heavy consumption by utility/storage machinery.

> **Key insight:** C9's small size (74 symbols) makes it a lightweight utility layer. Changes to C9 entry points can ripple widely due to high in-degree (71+ callers for `get_help`), but the changes are typically shallow (string return values).

# C3: Semantic Analysis and CQE Refinement Hub

> Center C3 | Archetype: hub | 290 symbols
> Coupled with: C0, C1, C2, C4, C5, C6, C7, C8, C9
> Coupling cluster: SC38

## Overview

C3 is a **hub** center in the Quro codebase — the semantic analysis and CQE refinement hub. It orchestrates TDA node role classification, CQE refinement, gate type validation, MCP tool dispatch, and workspace scanning. As a hub archetype, C3 fans out to many downstream centers via top-down navigation. Navigation strategy: explore entry points first, then trace downstream calls.

## Entry Points

- `sym::classify_node_role::upstream_navigator::325` — TDA node role classification and upstream navigation
- `sym::SemanticCQERefiner::refiner::128` — Semantic CQE refinement engine
- `sym::GateResult::types::13` — Gate result type definitions
- `sym::call_tool` — MCP tool invocation dispatch
- `sym::scan_workspace` — Workspace scanning entry

## Documentation

- [Architecture](docs/architecture.md)
- [Data Flow](docs/dataflow.md)
- [API Surface](docs/api.md)
- [Dependencies](docs/dependencies.md)
- [Entry Points](docs/entry-points.md)

# C3 Center — Semantic Analysis and CQE Refinement Hub

**Type:** Hub | **Size:** 290 symbols | **Last explored:** 2026-06-20T10:00:00Z | **Coverage:** 85% | **Git:** e881846

## Overview

C3 is a **Hub** center that orchestrates semantic analysis and CQE refinement. It coordinates TDA node role classification, CQE quality evaluation refinement, gate type validation, MCP tool dispatch, and workspace scanning — fanning out to all 9 coupled centers via SC38.

## Entry Points

| Entry | Symbol | Description |
|-------|--------|-------------|
| TDA Classification | `sym::classify_node_role::upstream_navigator::325` | Node role assignment + upstream navigation |
| CQE Refinement | `sym::SemanticCQERefiner::refiner::128` | Semantic code quality evaluation refinement |
| Gate Types | `sym::GateResult::types::13` | Gate result type system |
| Tool Dispatch | `sym::call_tool` | MCP tool invocation dispatcher |
| Workspace Scan | `sym::scan_workspace` | Workspace scanner entry point |

## Capability Map

| Capability | Entry Point | Downstream Centers | Description |
|------------|-------------|-------------------|-------------|
| TDA Classification | `classify_node_role` | C0, C1, C2 | Classify nodes into energy roles |
| CQE Refinement | `SemanticCQERefiner` | C4, C5, C6 | Refine quality evaluation metrics |
| Gate Types | `GateResult::types` | C5, C6, C7 | Validate and transform gate results |
| Tool Dispatch | `call_tool` | C5, C7, C9 | Resolve and invoke MCP tools |
| Workspace Scan | `scan_workspace` | C8, C9 | Scan filesystem for code symbols |

## Docs

- [architecture.md](docs/architecture.md) — Hub architecture and capability layering
- [dataflow.md](docs/dataflow.md) — Data flows from entry points to downstream centers
- [api.md](docs/api.md) — Full API surface with signatures
- [dependencies.md](docs/dependencies.md) — Cross-center SC38 coupling
- [entry-points.md](docs/entry-points.md) — Entry point analysis and navigation priorities

## Coupling Cluster

SC38 (coupled with all centers C0–C9).

## Navigation Strategy

**Top-down** — explore entry points first, then trace downstream calls to coupled centers.

# C1: Leaf-Dominated Fanout Utility Layer

> Center C1 | Archetype: fanout | 670 symbols
> Coupled with: C0, C3, C4, C5, C6, C7, C8

## Overview

C1 is the leaf-dominated fanout utility layer of the Quro codebase. It contains storage adaptation, graph persistence, and figure rendering utilities that are consumed by the core orchestration layer (C0) and other centers. As a fanout archetype, C1 expands outward from its leaf entry points — symbols like `ManifoldStatesGraphAdapter`, `sqlite_graph`, and `figure` serve as the entry leaves from which the broader utility surface is navigated.

## Entry Points

- `sym::ManifoldStatesGraphAdapter` — Storage adapter for manifold state graphs
- `sym::sqlite_graph` — SQLite-backed graph persistence
- `sym::figure` — Figure/visualization rendering

## Documentation

- [Architecture](docs/architecture.md) (pending)
- [Data Flow](docs/dataflow.md) (pending)
- [API Surface](docs/api.md) (pending)
- [Dependencies](docs/dependencies.md) (pending)
- [Entry Points](docs/entry-points.md) (pending)

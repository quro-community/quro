# C0: Core Orchestration Layer

> Center C0 | Archetype: hub | 919 symbols
> Coupled with: C1, C3, C4, C5, C6, C7, C8

## Overview

C0 is the core orchestration hub of the Quro codebase. It contains the primary service layer (`QuroV3Service`), orchestrator classes, and the central coordination logic tying together the code analysis pipeline. As a hub archetype, C0 is the central attractor of the system — most other centers reference symbols in C0, and its orchestrators coordinate the flow through storage adapters (C1), traversal engines (C2), file I/O sinks (C3), CQE quality reporting (C4), the policy layer (C5), type system (C6), shadow/draft tools (C7), and LSH indexing (C8).

## Entry Points

- `sym::QuroV3Service::service::81` — Primary service entry point
- `sym::enrich::types::55` — Type enrichment
- `sym::get_all_nodes::memory::108` — Memory registry access

## Documentation

- [Architecture](docs/architecture.md) (pending)
- [Data Flow](docs/dataflow.md) (pending)
- [API Surface](docs/api.md) (pending)
- [Dependencies](docs/dependencies.md) (pending)
- [Entry Points](docs/entry-points.md) (pending)

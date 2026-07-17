---
type: CenterOverview
title: C7: Balanced Chain — Transitional Layer
description: Transitional chain layer containing shadow/draft tooling, graph neighbor traversal, and TypeScript analyzer lifecycle management.
tags: [center, C7, chain, shadow, draft]
---

# C7: Balanced Chain — Transitional Layer

> Center C7 | Archetype: chain | 139 symbols
> Coupled with: C0, C1, C3

## Overview

C7 is a transitional chain layer within the Quro codebase. It contains shadow/draft tooling, graph neighbor traversal utilities, and TypeScript analyzer lifecycle management. As a chain archetype, C7 symbols are traversed sequentially following the call chain — each step passes control to the next linked symbol. Its strongest coupling is with the core orchestration hub (C0, score: 632.9), with secondary couplings to storage adapters (C1, 150.6) and file I/O sinks (C3, 140.5).

## Entry Points

- `sym::get_in_neighbors` — Graph neighbor acquisition for traversal
- `sym::get_draft_status::shadow_draft_tools::252` — Draft status query in shadow draft tools
- `sym::shutdown::typescript_analyzer::79` — TypeScript analyzer shutdown lifecycle

## Documentation

- [Architecture](docs/architecture.md) (pending)
- [Data Flow](docs/dataflow.md) (pending)
- [API Surface](docs/api.md) (pending)
- [Dependencies](docs/dependencies.md) (pending)
- [Entry Points](docs/entry-points.md) (pending)

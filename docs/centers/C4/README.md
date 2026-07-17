---
type: CenterOverview
title: C4: I/O & Filesystem Sink
description: High fan-in sink center providing fundamental filesystem operations, LDS tool initialization, and Unix socket connections.
tags: [center, C4, sink, io, filesystem]
---

# C4: I/O & Filesystem Sink

> Center C4 | Archetype: sink | 284 symbols
> Coupled with: C0, C1, C2, C5 (SC1 cluster)

## Overview

C4 is the I/O and filesystem sink layer of the Quro codebase. It provides fundamental filesystem operations (`Path`, `exists`, `info`), LDS tool initialization (`_ensure_lds_tools`), and Unix socket connections (`open_unix_connection`). As a sink archetype, C4 is a high fan-in terminal layer that other centers converge upon for I/O and persistence operations. It belongs to the SC1 tight-coupling cluster with C5, indicating strong change coordination with the hub layer.

## Entry Points

- `sym::Path` — Pathlib filesystem path abstraction
- `sym::exists` — File/directory existence check
- `sym::info` — File metadata info
- `sym::_ensure_lds_tools` — LDS tool initialization
- `sym::open_unix_connection` — Unix socket connection

## Documentation

- [Architecture](docs/architecture.md)
- [Data Flow](docs/dataflow.md)
- [API Surface](docs/api.md)
- [Dependencies](docs/dependencies.md)
- [Entry Points](docs/entry-points.md)

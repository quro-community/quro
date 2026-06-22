# C8: MinHash LSH (High Fan-in Sink)

> Center C8 | Archetype: sink | 139 symbols
> Coupled with: C0 (672.3), C1 (171.4), C3 (163.4)

## Overview

C8 is a high fan-in sink center in the Quro codebase, representing the terminal layer of the LSH (Locality-Sensitive Hashing) indexing subsystem. As a sink archetype, it receives heavy inward coupling from C0 (672.3), C1 (171.4), and C3 (163.4) — the core orchestration, storage, and file I/O centers. Navigation strategy is upstream-first: explore incoming edges from coupled centers to understand data flow, then converge on the sink's internal structure.

## Entry Points

- `sym::MinHashLSH::lsh_engine::28` — LSH engine implementation
- `sym::MinHashLSH` — MinHash LSH class
- `sym::to_dict` — Serialization helper

## Documentation

- [Architecture](docs/architecture.md) (pending)
- [Data Flow](docs/dataflow.md) (pending)
- [API Surface](docs/api.md) (pending)
- [Dependencies](docs/dependencies.md) (pending)
- [Entry Points](docs/entry-points.md) (pending)

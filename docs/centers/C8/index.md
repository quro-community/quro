# C8 Knowledge Base Index — MinHash LSH Sink

## Coverage Summary
- Total symbols: 139
- Documented: 6 (4%) — core modules documented; full symbol coverage via semantic index
- Last updated: 2026-06-20
- Mode: INIT (first full exploration completed)

## Core Modules

| Module | Status | Docs |
|--------|--------|------|
| `core/lsh/__init__.py` | ✅ documented | architecture, dataflow, api |
| `core/lsh/types.py` | ✅ documented | api (LSHConfig, LSHSignature) |
| `core/lsh/kernel.py` | ✅ documented | api (LSHKernel protocol) |
| `core/lsh/minhash.py` | ✅ documented | architecture, dataflow, api, entry-points |
| `orchestrators/lsh.py` | ✅ documented | architecture, dataflow, api |
| `deprecated/.../lsh_engine.py` | ✅ documented | architecture, dataflow, api, entry-points |
| `pipeline/cqe/stability.py` | ✅ documented | entry-points (to_dict) |

## Generated Documents

| Document | Description |
|----------|-------------|
| [architecture.md](docs/architecture.md) | Internal architecture, layer structure, key design decisions |
| [dataflow.md](docs/dataflow.md) | Data flow between components, upstream call paths, cross-center coupling |
| [api.md](docs/api.md) | API surface: classes, methods, signatures, supporting types |
| [dependencies.md](docs/dependencies.md) | Internal + cross-center dependency graph, coupling scores |
| [entry-points.md](docs/entry-points.md) | Entry point analysis with TDA roles, call flows, navigation strategy |

## Entry Points

| Symbol | TDA Role | Forward Magnitude |
|--------|----------|-------------------|
| `sym::MinHashLSH::lsh_engine::28` | CONVERTER | 8.7604 |
| `sym::MinHashLSH` | CONVERTER | 2.4058 |
| `sym::to_dict` | TRANSIENT | 0.0 |

## Coupling

- Tight coupling cluster: **SC70** with C0, C1, C3, C7 (size=832)
- Strongest coupling: **C0 ↔ C8** (score 672.288)
- Boundary contracts: `MinHashLSH`, `LSHConfig`, `ManifoldAdapter`

> **Legend:** ✅ documented | ⚠️ partial | ❌ undocumented

# C8 Architecture — MinHash LSH Sink (Terminal Indexing Layer)

## Overview

C8 (MinHash LSH Sink) is a **high fan-in sink** archetype that provides MinHash-based
Locality Sensitive Hashing (LSH) for semantic similarity search. It implements a pure
computation kernel with a clean protocol/implementation separation, bridged to persistence
via an orchestrator layer.

## Layer Structure

```
┌──────────────────────────────────────────────────────────┐
│                  Upstream Callers (C0, C1, C3)           │
│  MCP Tools, Scanner, CLI, Indexer                        │
└──────────────────┬───────────────────────────────────────┘
                   │ calls
┌──────────────────▼───────────────────────────────────────┐
│  LSHOrchestrator (orchestrators/lsh.py)                  │
│  Bridge between pure kernel and Manifold persistence     │
│  ┌──────────────────────────────────────────────────┐    │
│  │  ManifoldAdapter (C0 boundary — not explored)    │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────┬───────────────────────────────────────┘
                   │ delegates
┌──────────────────▼───────────────────────────────────────┐
│  MinHashLSH (core/lsh/minhash.py)                        │
│  Pure MinHash kernel — implements LSHKernel protocol     │
│  Database-blind, file-blind, no side effects             │
│  ┌──────────────────────────────────────────────────┐    │
│  │  LSHSignature / LSHConfig (core/lsh/types.py)    │    │
│  │  Immutable dataclasses for data contracts        │    │
│  └──────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────┐    │
│  │  LSHKernel Protocol (core/lsh/kernel.py)         │    │
│  │  Pure function contract for implementations      │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  Deprecated LSH (deprecated/quro_cli/analysis/lsh_engine.py)│
│  Legacy MinHashLSH + LSHIndex + generate_minhash CLI    │
│  Used by MCP tools and scanner for backward compat      │
└──────────────────────────────────────────────────────────┘
```

## Module Inventory

| Module | File | Intent |
|--------|------|--------|
| `core/lsh/__init__.py` | core/lsh/__init__.py | Module exports |
| `core/lsh/types.py` | core/lsh/types.py | Pure data contracts (LSHConfig, LSHSignature) |
| `core/lsh/kernel.py` | core/lsh/kernel.py | LSHKernel protocol definition |
| `core/lsh/minhash.py` | core/lsh/minhash.py | Pure MinHash implementation |
| `orchestrators/lsh.py` | orchestrators/lsh.py | Bridge to Manifold persistence |
| `deprecated/.../lsh_engine.py` | deprecated/quro_cli/analysis/lsh_engine.py | Legacy LSH engine + index + CLI |

## Key Design Decisions

1. **Protocol-based purity**: `LSHKernel` enforces a contract where implementations
   must be pure (no I/O, no side effects, deterministic). This makes testing trivial.

2. **Immutable data contracts**: `LSHConfig` and `LSHSignature` are frozen dataclasses
   with validation in `__post_init__`.

3. **Vectorized minhash**: The core `MinHashLSH._compute_minhash` uses numpy
   broadcasting for O(k×n) computation across all tokens and hash functions.

4. **Two parallel codebases**: A production `core/lsh/` pure module and a legacy
   `deprecated/quro_cli/analysis/lsh_engine.py` used by the CLI/MCP toolchain.

## Archetype: Sink

C8 is a **sink** because:
- High fan-in: Called by 17+ upstream callers across C0, C1, C3
- Terminal computation: MinHash signature generation is a leaf operation
- CONVERTER role: MinHashLSH (forward_magnitude=2.41–8.76) transforms tokens → signatures
- TRANSIENT role: to_dict is a pure serialization helper

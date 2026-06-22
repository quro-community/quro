# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## STANDARDS

- Must follow documentation standard. [Documentation Standard](./DOCUMENTATION.md)

## CONSTRAINTS

- **MCP First**
  - Always choose MCP tools than shell / grep.

## Commands

```bash
# Install
pip install -e ".[dev]"

# Build index (scan workspace and build symbol registry + graph DB)
python -m quro.build_index [--workspace PATH] [--rebuild]

# CLI
quro scan                                  # Scan workspace
quro cqe-query <token> --tau 0.1           # CQE semantic query
quro cqe-symbol <name>                     # Symbol details
quro cqe-list                              # List symbols/categories
quro tda-pipeline all                      # Run TDA pipeline
quro tda-plan <start> <goal>               # Plan trajectory
quro tda-explore <token>                   # Explore codebase
quro tda-centers                           # Semantic centers
quro tda-populate-fields                   # Populate TDA energy fields
quro visualize all                         # Generate visualizations

# MCP server
python -m quro_mcp

# Tests (current tests live under deprecated/)
pytest deprecated/quro_cli/tests/

# Format/Lint/Type
black .
ruff check .
mypy .
```

## Architecture

Quro is a **semantic code navigation and analysis system** with a strict three-layer architecture and invariant protection.

### Layer Invariants

```
1. Kernel is pure (no side effects, deterministic, stateless)
2. Policy is declarative (data-only, can be wrong)
3. Extension is isolated (cannot access kernel)
4. Kernel NEVER depends on Policy (Policy MAY depend on Kernel)
```

### Core Pipeline

```
Raw Graph
   ↓
Policy Layer (mutable, heuristic — reweight/prune edges)
   ↓
Transformed Graph (frozen snapshot)
   ↓
Kernel (pure execution — argmax path scoring)
   ↓
Result
```

### Directory Layout

| Directory | Purpose |
|-----------|---------|
| `scanner/` | Workspace scanner — AST parser, feature extractor, filter gates, ignore rules |
| `index_builder/` | Builds graph index from scanned symbols using enrichers (hub pressure, path entropy, role, intent) |
| `core/cqe/` | CQE engine — pure kernel, policy, canonical layer, traversal modes (forward/reverse/field_guided/saddle_escape), refiner |
| `tda/` | Topological Data Analysis pipeline (phases 1-4) — energy fields, attractor/repeller detection, semantic centers, trajectory planning |
| `quro_mcp/` | MCP server exposing CQE and TDA tools over stdio |
| `cli/` | Argparse-based CLI with CommandRegistry pattern |
| `adapters/` | Storage adapters (graph, manifold, registry, shadows, skeleton) |
| `protocols/` | Kernel protocol, policy protocol, extension protocol |
| `orchestrators/` | Pipeline orchestrators (CQE, LSH, Morph, Phantom, Skeleton) |
| `service/` | Service layer (CQE, TDA, scanner, visualization, registry) |
| `pipeline/cqe/` | CQE pipeline components (stability, detox, input gates, MI adjuster, invariants) |
| `policy/` | Policy sub-packages (nrt, trust, self_heal) |
| `migrations/` | Database migration scripts |
| `io/` | I/O adapters (SQLite index loader) |
| `runtime/` | Runtime orchestration (CQE orchestrator) |

### Key Design Rules

- **Scanner pipeline**: File discovery → File gate filtering → AST parsing → Feature extraction → Symbol gate filtering → Feature gate validation → Output to adapter
- **Index builder**: Two-pass enrichment — Pass 1 builds graph structure (non-topology enrichers), Pass 2 runs topology-aware enrichers (HubPressureEnricher)
- **CQE traversal modes**: forward, reverse, field_guided, saddle_escape — auto-selected based on node state (sink/saddle/attractor/repeller)
- **CQE kernel** is strictly: `score(path) = Π w(e_i)`, `answer = argmax(score)`, `prune if score < tau`
- **Containment edges** (Class → Method) use structure-normalized weights to prevent bias
- **TDA phases**: Phase 1 (energy computation) → Phase 2 (manifold) → Phase 2.5 → Phase 3 → Phase 3.5 (semantic centers) → Phase 4 (trajectory planning)

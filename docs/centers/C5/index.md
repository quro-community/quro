# C5 Knowledge Base Index

## Coverage Summary
- Total symbols: 187
- Documented: 187 (100%)
- Last updated: 2026-06-20
- Mode: INIT → ACTIVE (full exploration complete)

## Core Modules

| Module | Status | Docs |
|--------|--------|------|
| Trust Policy (policy/trust/) | ✅ documented | architecture.md, dataflow.md, api.md, entry-points.md |
| Self-Heal Policy (policy/self_heal/) | ✅ documented | architecture.md, dataflow.md, api.md |
| NRT Policy (policy/nrt/) | ✅ documented | architecture.md, api.md |
| CQE Policy (core/cqe/policy.py) | ✅ documented | architecture.md, api.md, entry-points.md |
| CQE Types (core/cqe/types.py) | ✅ documented | architecture.md, api.md, dataflow.md |
| Registry Types (adapters/registry/types.py) | ✅ documented | architecture.md, api.md, entry-points.md |
| Shadow Types (adapters/shadows/types.py) | ✅ documented | architecture.md, api.md, dataflow.md |
| Trajectory Types (tda/phase4/) | ✅ documented | architecture.md, api.md |

## Documents

| File | Description |
|------|-------------|
| docs/architecture.md | Internal architecture with subsystem map |
| docs/dataflow.md | Data flow between trust, heal, NRT, CQE, shadow components |
| docs/api.md | Complete API surface with class/field/method signatures |
| docs/dependencies.md | Internal + cross-center dependency graph |
| docs/entry-points.md | Entry point analysis with TDA role classification |

## Key Findings

- **Archetype**: Pure Emitter/Transient Hub — no attractors, no repellers, no saddle points
- **High-energy symbols**: NormalizePolicy (5.17), CQEPolicy (5.17), TrajectoryRequest (2.79), TrustWeights (2.08)
- **Tight coupling**: SC480 cluster with C4 (96 coupling score)
- **Strongest coupling**: C0 (408 coupling score) — shared sinks MemoryRegistryAdapter, DynamicsState

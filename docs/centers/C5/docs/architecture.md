# C5 Architecture: Policy & Trust Hub

## Overview

C5 is the **Policy & Trust Hub** — a pure emitter hub (187 symbols) that consolidates all
policy-related data structures, trust computation logic, and configuration types used across
the Quro system. It has **no attractors or repellers** — it is purely a provider of types
and computation contracts consumed by other centers.

All symbols are either **EMITTER** (high forward magnitude, providing types/flows outward)
or **TRANSIENT** (pass-through types). The center has zero saddle points — a clean
one-directional data-flow hub.

## Subsystem Map

```
┌──────────────────────────────────────────────────────────────────┐
│                       C5 — Policy & Trust Hub                      │
│                                                                   │
│  ┌─────────────────────┐    ┌──────────────────────────┐          │
│  │   Trust Policy       │    │   Self-Heal Policy       │          │
│  │   policy/trust/      │    │   policy/self_heal/       │          │
│  │   • TrustSignals     │    │   • HealProposal          │          │
│  │   • TrustRecord      │    │   • HealDecision          │          │
│  │   • TrustWeights     │    │   • HealResult            │          │
│  │   • TrustComputeReq  │    │   • HealRequest           │          │
│  │   • TrustPropagation  │    │   • AtomPatch / Op       │          │
│  │   • TrustEngine      │    │   • SelfHealEngine        │          │
│  └─────────┬───────────┘    └──────────┬───────────────┘          │
│            │                          │                           │
│  ┌─────────▼───────────┐    ┌──────────▼───────────────┐          │
│  │   NRT Policy         │    │   Shadow Files           │          │
│  │   policy/nrt/        │    │   adapters/shadows/      │          │
│  │   • NRTResult        │    │   • ShadowFile           │          │
│  │   • ShadowRule       │    │   • ShadowReadRequest    │          │
│  │   • CrossSTAConflict │    │   • ShadowWriteRequest   │          │
│  │   • PatchSuggestion  │    │   • DSLAtom              │          │
│  │   • BreachCheckReq   │    │                          │          │
│  └─────────┬───────────┘    └──────────┬───────────────┘          │
│            │                          │                           │
│  ┌─────────▼───────────┐    ┌──────────▼───────────────┐          │
│  │   CQE Policy         │    │   CQE Types              │          │
│  │   core/cqe/policy.py │    │   core/cqe/types.py      │          │
│  │   • PrunePolicy      │    │   • CQEMultiTierResult   │          │
│  │   • BoostPolicy      │    │   • CQETier              │          │
│  │   • NormalizePolicy  │    │   • CQERefinedResult     │          │
│  │   • PathGrammarPolicy│    │   • CQEResult            │          │
│  │   • CQEPolicy        │    │   • GraphProtocol        │          │
│  └─────────────────────┘    └──────────────────────────┘          │
│                                                                   │
│  ┌─────────────────────┐    ┌──────────────────────────┐          │
│  │   Registry Types     │    │   Trajectory Types       │          │
│  │   adapters/registry/ │    │   tda/phase4/            │          │
│  │   • MorphInsertReq   │    │   • TrajectoryRequest    │          │
│  │   • SymbolInsertReq  │    │   • StepDecision         │          │
│  │   • FileRecord       │    │   • CandidateDecision    │          │
│  │   • SymbolRecord     │    │   • RejectedNode         │          │
│  │   • MorphismRecord   │    │   • TrajectoryPlan       │          │
│  └─────────────────────┘    └──────────────────────────┘          │
└──────────────────────────────────────────────────────────────────┘
```

## Key Architectural Properties

1. **Immutable-by-design**: All dataclasses are frozen (`@dataclass(frozen=True)`).
   Every type in C5 is immutable — no mutations, no side effects.

2. **Protocol-driven**: Trust computation is defined by a `TrustPolicy` Protocol
   (`policy/trust/protocol.py`) guaranteeing pure, deterministic computation.

3. **Configurable policies**: CQE traversals are parameterized by four independent
   sub-policies (Prune, Boost, Normalize, Grammar) composed into `CQEPolicy`.

4. **Blast radius isolation**: C5 types are consumed across C0 (408 coupling score),
   C1 (100), C4 (96), and C3 (73). Changes to C5 types must account for these
   coupling relationships, especially with C0 (shared sinks like MemoryRegistryAdapter,
   DynamicsState).

## Invariants

- All Policy dataclasses are frozen (immutable)
- Trust weights must sum to 1.0 (validated by `TrustWeights.__post_init__`)
- Trust computation is deterministic: same input → same output
- Signal ranges: all clamped to [0, 1], consumer_health to (0, 1]
- CQE Policy classes contain no methods except classmethod constructors

# C5: High fan-out hub: orchestration layer

> Center C5 | Archetype: hub | 187 symbols
> Coupled with: C0 (407.9), C1 (100.1), C3 (73.2), C4 (96.0)

## Overview

C5 is a high fan-out hub in the Quro orchestration layer. It contains the policy layer with `PathGrammarPolicy`, trust/weight mechanics via `TrustWeights`, and morphism request type definitions. As a hub archetype coupled tightly with C4 in the SC480 cluster, C5 orchestrates policy-driven symbol processing across the codebase.

## Entry Points

- `sym::MorphismInsertRequest::types::132` — Morphism insert request type
- `sym::TrustWeights::types::48` — Trust weights type
- `sym::PathGrammarPolicy::policy::141` — Path grammar policy

## Documentation

- [Architecture](docs/architecture.md) (pending)
- [Data Flow](docs/dataflow.md) (pending)
- [API Surface](docs/api.md) (pending)
- [Dependencies](docs/dependencies.md) (pending)
- [Entry Points](docs/entry-points.md) (pending)

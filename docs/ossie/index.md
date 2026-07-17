# Ossie Semantic Models

> Apache Ossie semantic model definitions for Quro's structured data layer.
> These YAML files describe tables, fields, relationships, and metrics so
> AI agents can query and reason about Quro's data without guessing at schemas.

## Models

- [TDA Graph](tda-graph.yaml) — Nodes, edges, energy fields, and morphism types for the semantic topology graph
- [CQE Pipeline](cqe-pipeline.yaml) — Gate evaluation, flow state, and invariant structures
- [Symbol Registry](symbol-registry.yaml) — Symbol metadata, TDA roles, and forward/backward magnitudes
- [LSH Index](lsh-index.yaml) — Locality-sensitive hashing configuration for semantic search
- [Center Coupling](center-coupling.yaml) — Cross-center mutual information scores and cluster assignments

## Conventions

- Each `.yaml` file is one `semantic_model` with datasets, relationships, fields, and metrics
- Default dialect is `ANSI_SQL` unless a model targets a specific engine
- `ai_context.instructions` should reference relevant OKF concept documents for narrative context

# C6: Type System & Validation Chain

| Metadata | Value |
|----------|-------|
| **Center ID** | C6 |
| **Archetype** | chain |
| **Size** | 176 symbols |
| **Entry Strategy** | sequential |
| **Entry Points** | `sym::SymbolInfo`, `sym::validate::input_gates::49`, `sym::StructuralTags` |

## Coverage: 5/5 docs (100%)

| Doc | Status | Description |
|-----|--------|-------------|
| `docs/architecture.md` | ✅ Complete | Internal architecture & subsystems |
| `docs/dataflow.md` | ✅ Complete | Data flow & transformations |
| `docs/api.md` | ✅ Complete | Full API surface |
| `docs/dependencies.md` | ✅ Complete | Internal & cross-center dependencies |
| `docs/entry-points.md` | ✅ Complete | Entry point analysis & navigation |

## Coupled Centers

| Center | Role | Coupling Score |
|--------|------|---------------|
| C0 | Hub | 159.0 |
| C1 | Fanout | 147.5 |
| C3 | Sink | 136.7 |
| C4 | Hub | 40.3 |

## Top Symbols by Energy

| Symbol | Role | Forward Magnitude |
|--------|------|-------------------|
| `SymbolInfo` (Entry) | CONVERTER | 9.88 |
| `GateResult` | CONVERTER | 7.56 |
| `StructuralTags` (Entry) | CONVERTER | 5.36 |
| `CQEPolicy` | EMITTER | 5.17 |
| `TypeBoundary` | CONVERTER | 3.13 |

## Last Explored
- **Git hash**: `8d5ee9b`
- **Date**: 2026-06-20
- **Mode**: INIT (fresh exploration)

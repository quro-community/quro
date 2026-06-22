# C6: Type System & Validation Chain — Dependency Graph

## Internal Dependency Map

```
scanner/types.py ──────┬──► scanner/gates/symbol_filter.py
                        │         └── uses: GateResult, ParsedSymbol
                        ├──► scanner/gates/feature_gate.py
                        │         └── uses: GateResult, SymbolFeatures
                        ├──► scanner/gates/file_filter.py
                        │         └── uses: GateResult
                        ├──► scanner/gates/chain.py
                        │         └── uses: GateResult, ParsedSymbol, SymbolFeatures
                        │         └── uses: FileFilterGate, SymbolFilterGate, FeatureGate
                        └──► scanner/__init__.py
                                  └── exports: SymbolInfo, ParsedSymbol, etc.

scanner/gates/types.py ──► GateResult (shared type)
scanner/gates/__init__.py ──► exports: GateResult, ScannerGateChain, etc.

pipeline/cqe/input_gates.py ──► GateResult (local), InputGateChain
                                  └── uses: SymbolBlacklistGate, FilePathIntegrityGate, FeatureCapGate

deprecated/quro_cli/analysis/structural_tag_extractor.py
    └── standalone: StructuralTags, extract_tags, merge_with_llm_tags

adapters/graph/protocol.py ──► GraphAdapter (Protocol)
adapters/graph/sqlite.py ──► SQLiteGraphAdapter (implements GraphAdapter)
adapters/graph/duckdb.py ──► DuckDBGraphAdapter (implements GraphAdapter)
adapters/graph/types.py ──► GraphNode, GraphEdge (used by adapters)
```

## DTO/Type Symbol Groups

C6 contains a large set of DTO/type symbols (TRANSIENT role) shared across centers:

### Request Types
- `HealRequest`, `TrajectoryRequest`, `TrustComputeRequest`, `TrustPropagationRequest`
- `ShadowWriteRequest`, `ShadowReadRequest`, `SymbolInsertRequest`, `NodeInsertRequest`
- `BreachCheckRequest`, `RuleLoadRequest`, `GraphInsertRequest`

### Result Types
- `HealResult`, `TrajectoryComparison`, `PathResult`, `CycleResult`, `DriftResult`
- `CQEResult`, `CQEMultiTierResult`, `CQERefinedResult`, `ScanResult`, `IndexResult`
- `BettiResult`, `CanonicalResult`, `PhantomResult`, `DetoxReport`, `DependencyResult`

### State/Status Types
- `DynamicsState`, `StabilityState`, `TrajectoryState`, `PhantomState`, `EnergyState`
- `AttractorBiasedState`, `OfflineEnergyState`, `NodeState`, `SimulationState`

### Analysis Types
- `CommunityInfo`, `IntentGroup`, `TrajectoryAnalysis`, `CQEIntegrationStats`, `TDAQualityReport`
- `StructuralMetrics`, `CognitiveMassComponents`, `RicciCurvatureComponents`
- `FrictionComponents`, `MIGateComponents`, `AnisotropicField`, `LandingHint`

### Config/Policy Types
- `CQEPolicy`, `BoostPolicy`, `NormalizePolicy`, `PrunePolicy`, `CQETier`
- `LSHConfig`, `EdgeWeightConfig`, `SimulationConfig`

## Cross-Center Coupling

| Partner Center | Coupling Score | Mechanism | Key Shared Symbols |
|----------------|---------------|-----------|-------------------|
| **C0** (Hub) | 159.0 | 10 bridge symbols → shared sinks | `MemoryRegistryAdapter`, `upsert_node`, `_process_event` |
| **C1** (Fanout) | 147.5 | 10 bridge symbols → shared sinks | `upsert_node`, `MemoryRegistryAdapter`, `_process_event` |
| **C3** (Sink) | 136.7 | 10 bridge symbols → shared sinks | `upsert_node`, `MemoryRegistryAdapter`, `argument` |
| **C4** (Hub) | 40.3 | Bridge symbols → shared sinks | `upsert_node`, `MemoryRegistryAdapter`, `argument` |

### Tight Coupling Cluster: SC1158
C6 belongs to coupling cluster **SC1158** (size: 633 symbols), indicating that changes in C6 are likely to require coordinated changes across its coupled centers.

## Dependency Rules

1. **C6 → C1/C3 (inbound)**: Consumes `ParsedSymbol` from AST parser (C1), file I/O utilities (C3)
2. **C6 → C0/C4 (outbound)**: Produces `SymbolInfo`, `ScanResult`, `GateResult` for orchestration (C0) and quality analysis (C4)
3. **No circular dependencies**: C6 types flow in one direction through the chain
4. **Bridge symbols**: `MemoryRegistryAdapter`, `upsert_node` are the primary bridge symbols — explore only boundary contracts, not internals

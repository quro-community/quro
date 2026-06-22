# C0 Knowledge Base Index

## Coverage Summary
- Total symbols: 919
- Documented: 17 (1.9%) — core symbols explored
- Last updated: 2026-06-20
- Mode: INIT (first full exploration) + INCREMENTAL (Phase-1 DuckDB findings)
- Phase-1 modules explored: 6 files, ~1190 lines (batch_processor, duckdb_processor, event_logger, schema, __init__, __main__)
- DuckDB storage layer: 4 files (coordinator, migration, schema, duckdb_event_writer)

## Coverage Map

### Architecture (`docs/architecture.md`) ✅
- Service layer: QuroV3Service, CQEService, TDAService, ScannerService, BaseService, ServiceRegistry
- Orchestrator layer: CQEOrchestrator, ScannerOrchestrator, Phase2Orchestrator, Phase3Orchestrator, Phase35Orchestrator, MorphOrchestrator, LSHOrchestrator, SkeletonOrchestrator, PhantomOrchestrator, TraversalOrchestrator
- TDA pipeline: Phase-2 (4 passes), Phase-3 (4 passes), Phase-3.5 (center detection)
- I/O adapters and boundary contracts

### Data Flow (`docs/dataflow.md`) ✅
- 4 major data flows documented: Scanning, CQE Query, TDA Pipeline, Sub-flows
- Cross-center data flow map
- Data persistence locations

### API Surface (`docs/api.md`) ✅
- 3 entry points with TDA classifications
- 6 service classes with method signatures
- 11 orchestrator classes with method signatures
- Supporting utility/internal symbols

### Dependencies (`docs/dependencies.md`) ✅
- Internal dependency graph (service → orchestrator → pipeline)
- Cross-center couplings with scores (C1: 674, C8: 672, C3: 636, C7: 633, C5: 408, C4: 200, C6: 159)
- SC70 tight-coupling cluster identification
- Adapter boundaries and persistence formats

### Entry Points (`docs/entry-points.md`) ✅
- 3 entry points analyzed with TDA role, forward/backward metrics
- High-energy internal symbols identified (CQEOrchestrator: 43.9)
- Call flow summary from external consumer

## Core Modules

| Module | Status | Docs |
|--------|--------|------|
| sym::QuroV3Service::service::81 | ✅ documented | architecture, api, entry-points, dataflow, dependencies |
| sym::enrich::types::55 | ✅ documented | entry-points (legacy CLI) |
| sym::get_all_nodes::memory::108 | ✅ documented | entry-points, dependencies |
| Phase1BatchProcessor | ✅ documented (this session) | architecture, dataflow |
| DuckDBPhase1Processor | ✅ documented (this session) | architecture, dataflow |
| GraphEventLogger | ✅ documented (this session) | dataflow |
| DuckDBEventWriter | ✅ documented (this session) | dataflow |
| StorageCoordinator | ✅ documented (this session) | architecture |
| MigrationRunner | ✅ documented (this session) | architecture |
| TdaSchema | ✅ documented (this session) | architecture |
| DuckDBGraphAdapter | ✅ documented (existing) | architecture |
| CQEOrchestrator (forward_mag: 43.9) | ✅ documented | architecture, api, dataflow, dependencies |
| PhantomOrchestrator (forward_mag: 29.6) | ✅ documented | architecture, api, dataflow |
| ServiceRegistry (forward_mag: 27.7) | ✅ documented | architecture, api |
| MorphOrchestrator (forward_mag: 19.1) | ✅ documented | architecture, api, dataflow |
| LSHOrchestrator (forward_mag: 17.1) | ✅ documented | architecture, api, dataflow |
| SkeletonOrchestrator (forward_mag: 16.6) | ✅ documented | architecture, api, dataflow |
| Phase2Orchestrator (forward_mag: 12.8) | ✅ documented | architecture, api, dataflow, dependencies |
| Phase3Orchestrator (forward_mag: 13.6) | ✅ documented | architecture, api, dataflow |
| Phase35Orchestrator (forward_mag: 13.6) | ✅ documented | architecture, api, dataflow |
| CQEService (forward_mag: 12.7) | ✅ documented | architecture, api |
| ScannerService (forward_mag: 12.0) | ✅ documented | architecture, api |
| ScannerOrchestrator (forward_mag: 5.9) | ✅ documented | architecture, api, dataflow |
| TDAService (forward_mag: 5.9) | ✅ documented | architecture, api |

## Symbol Categories
| Category | Description |
|----------|-------------|
| `cat::service` | Service layer — BaseService, ServiceRegistry, QuroV3Service, CQEService, TDAService, ScannerService |
| `cat::manager` | Manager classes — DatabaseManager, MigrationManager, ShadowDraftManager |

## Energy Snapshot

| Band | Count | Example |
|------|-------|---------|
| High (fwd > 20) | 4 | CQEOrchestrator (43.9), PhantomOrchestrator (29.6), ServiceRegistry (27.7), BaseService (20.0) |
| Medium (fwd 10-20) | 6 | MorphOrchestrator (19.1), LSHOrchestrator (17.1), SkeletonOrchestrator (16.6), Phase3Orchestrator (13.6), Phase35Orchestrator (13.6), Phase2Orchestrator (12.8), CQEService (12.7), TraversalOrchestrator (12.5), ScannerService (12.0) |
| Low (fwd < 10) | rest | QuroV3Service (7.0), ScannerOrchestrator (5.9), TDAService (5.9), entry points (< 1.0) |

> **Legend:** ✅ documented | ⚠️ partial | ❌ undocumented

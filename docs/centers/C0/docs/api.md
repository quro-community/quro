# C0: API Surface

> **Center:** C0 | **Archetype:** Hub | **Symbols:** 919
> **Status:** Populated — first exploration session complete

## Overview

C0's public API surface consists of:
1. **Entry point symbols** (3) — primary interfaces into C0
2. **Service classes** (6) — `BaseService` subclasses registered in `ServiceRegistry`
3. **Orchestrator classes** (10) — pipeline orchestrators

## Entry Points

| Symbol | File:Line | Role | Description |
|--------|-----------|------|-------------|
| `sym::QuroV3Service::service::81` | `quro_mcp/service.py:81` | TRANSIENT | Main MCP service — wraps scan, CQE query, TDA analysis, and symbol retrieval |
| `sym::enrich::types::55` | `types.py:55` | TRANSIENT | Type enrichment entry point (legacy CLI `quro enrich`) |
| `sym::get_all_nodes::memory::108` | `memory.py:108` | TRANSIENT | Memory registry node access |

## Service Classes

### `BaseService` (ABC) — `service/base.py:12`
**Role:** EMITTER (forward_mag: 20.0, out_degree: 39)
- `get_name() → str` — Return service name
- `get_description() → str` — Return description
- `initialize(workspace_root: Path) → None` — Initialize with workspace
- `get_capabilities() → Dict[str, Any]` — Return service capabilities
- `is_initialized() → bool` — Check initialization status
- `get_workspace_root() → Path | None` — Get workspace root
- `_ensure_initialized() → None` — Guard method (raises RuntimeError)

### `ServiceRegistry` — `service/registry.py:12`
**Role:** EMITTER (forward_mag: 27.7, out_degree: 34)
- `register(service: BaseService) → None` — Register a service (class method)
- `get(name: str) → BaseService` — Get service by name (class method)
- `get_optional(name: str) → BaseService | None` — Get service or None
- `list_services() → List[str]` — List all registered service names
- `get_all() → Dict[str, BaseService]` — Get all registered services
- `clear() → None` — Clear all services (testing only)

### `QuroV3Service` — `quro_mcp/service.py:81`
**Role:** CONVERTER (forward_mag: 7.0, in_deg: 28, out_deg: 84)
- `__init__(workspace_root, enable_flow_trace?)`
- `scan_workspace(progress: bool = False) → Dict[str, Any]` — Scan and build index
- `cqe_query(start, tau=0.05, max_depth=3, ...) → Dict[str, Any]` — CQE query
- `cqe_query_with_mode(start, tau, max_depth, traversal_mode, ...) → Dict[str, Any]` — CQE query with traversal mode
- `cqe_query_multi_tier(start, max_depth=3, ...) → Dict[str, Any]` — Multi-tier CQE query
- `get_symbol(symbol_name: str) → Dict | None` — Get symbol details
- `get_category(category_name: str) → Dict | None` — Get category details
- `list_categories() → List[str]` — List categories
- `list_symbols(limit: int = 100) → List[str]` — List symbols
- `get_stats() → Dict[str, Any]` — Get statistics
- `clear() → None` — Clear state
- `tda_find_upstream(symbol, top_k=5, max_depth=2) → Dict[str, Any]` — Find upstream sources
- `tda_escape_sink(symbol) → Dict[str, Any]` — Escape from sink node
- `tda_get_field_vector(symbol) → Dict[str, Any]` — Get field vector
- `tda_classify_role(symbol) → Dict[str, Any]` — Classify TDA role

### `CQEService` — `service/cqe_service.py:15`
**Role:** CONVERTER (forward_mag: 12.7, in_deg: 16, out_deg: 69)
- `get_name() → str` — Returns "cqe"
- `get_description() → str`
- `initialize(workspace_root) → None`
- `get_capabilities() → Dict`
- `query(start, tau=0.05, max_depth=3, use_semantic_refiner=True) → Dict`
- `query_multi_tier(start, max_depth=3, use_semantic_refiner=True) → Dict`
- `query_with_mode(start, tau, max_depth, traversal_mode) → Dict`
- `get_symbol(symbol_name) → Dict | None`
- `get_category(category_name) → Dict | None`
- `list_symbols(limit=100) → List[str]`
- `list_categories() → List[str]`
- `get_stats() → Dict`

### `TDAService` — `service/tda_service.py:14`
**Role:** CONVERTER (forward_mag: 5.9, in_deg: 16, out_deg: 79)
- `get_name() → str` — Returns "tda"
- `initialize(workspace_root) → None`
- `get_capabilities() → Dict`
- `find_upstream(symbol, ...) → Dict` (delegates to QuroV3Service)
- `escape_sink(symbol) → Dict`
- `classify_role(symbol) → Dict`
- `get_field_vector(symbol) → Dict`

### `ScannerService` — `service/scanner_service.py:13`
**Role:** CONVERTER (forward_mag: 12.0, in_deg: 8, out_deg: 39)
- `get_name() → str` — Returns "scanner"
- `initialize(workspace_root) → None`
- `get_capabilities() → Dict`
- `scan_workspace(rebuild=False, progress=True) → Dict` — Full scan + index build
- `get_stats() → Dict` — Index statistics

## Orchestrator Classes

### `CQEOrchestrator` — `orchestrators/cqe.py:17` / `runtime/orchestrator.py:24`
**Role:** CONVERTER (forward_mag: 43.9, in_deg: 8, out_deg: 48) — HIGHEST ENERGY
- `__init__(graph_adapter, policy?, use_tda?)`
- `from_index(index_path, policy?, use_tda?, ...) → CQEOrchestrator` — Factory from SQLite
- `query(entry_node, tau?) → CQEResult` — Run CQE query (load → transform → kernel)
- `get_path(result, target) → Tuple[str]` — Extract path from result
- `get_top_k(result, k=10) → Tuple[Tuple[str, float]]` — Get top-k results

### `Phase2Orchestrator` — `tda/phase2/__main__.py:18`
**Role:** CONVERTER (forward_mag: 12.8, in_deg: 8, out_deg: 14)
- `__init__(events_path, output_path, duckdb_conn?)`
- `run() → None` — Run 3-pass pipeline + field enrichment + cache saving

### `Phase3Orchestrator` — `tda/phase3/__main__.py:20`
**Role:** CONVERTER (forward_mag: 13.6, in_deg: 8, out_deg: 14)
- `__init__(manifold_states_path, output_path)`
- `run() → None` — Run 4-pass cognitive compilation

### `Phase35Orchestrator` — `tda/phase3_5/__main__.py:23`
**Role:** CONVERTER (forward_mag: 13.6, in_deg: 8, out_deg: 14)
- `__init__(manifold_states_path, output_path, centers_output_path?)`
- `run() → None` — Run center detection + SCG building

### `ScannerOrchestrator` — `scanner/orchestrator.py:40`
**Role:** CONVERTER (forward_mag: 5.9, in_deg: 16, out_deg: 24)
- `__init__(workspace_root, adapter, progress_callback?)`
- `scan_workspace() → ScanStats` — Scan entire workspace
- `scan_file(file_path) → ScanResult | None` — Scan single file
- `get_rejection_stats() → Dict` — Gate rejection statistics

### `TraversalOrchestrator` — (exact file TBD)
**Role:** CONVERTER (forward_mag: 12.5, in_deg: 8, out_deg: 19)
Coordinates graph traversal operations.

### `MorphOrchestrator` — `orchestrators/morph.py:15`
**Role:** EMITTER (forward_mag: 19.1, in_deg: 4, out_deg: 29)
- `detect_drift(symbol, old_fingerprint, new_fingerprint) → AdapterDriftResult`
- `compute_topology(symbol, fingerprint) → BettiResult`
- `get_drift_history(symbol, limit=10) → Tuple[AdapterDriftResult]`
- `find_drifted_symbols(threshold?) → Tuple[str]`

### `LSHOrchestrator` — `orchestrators/lsh.py:17`
**Role:** EMITTER (forward_mag: 17.1, in_deg: 4, out_deg: 24)
- `compute_and_store(symbol, content, metadata) → ManifoldNode`
- `compute_similarity(symbol_a, symbol_b) → float`
- `find_similar(symbol, threshold=0.7, limit=10) → Tuple[Tuple[str, float]]`

### `SkeletonOrchestrator` — `orchestrators/skeleton.py:25`
**Role:** EMITTER (forward_mag: 16.6, in_deg: 4, out_deg: 29)
- `build_and_store_graph(nodes, edges) → SkeletonGraph`
- `find_dependencies(module_uid, max_depth=3) → Tuple[str]`
- `find_dependents(module_uid, max_depth=3) → Tuple[str]`
- `get_cycles() → Tuple[AdapterCircularDependency]`

### `PhantomOrchestrator` — `orchestrators/phantom.py:24`
**Role:** EMITTER (forward_mag: 29.6, in_deg: 4, out_deg: 39)
- `set_kernel(kernel) → None`
- `simulate_from_shadow(file_path, config?) → Tuple[PhantomResult]`
- `simulate_and_store(file_path, atoms, config?) → Tuple[PhantomResult]`
- `validate_shadow(file_path, config?) → bool`
- `get_shadow_checksum(file_path) → str | None`
- `list_all_shadows() → Tuple[str]`

### `CQEPipelineBuilder` — `pipeline/cqe/builder.py:17`
- `__init__(workspace_root)`
- `build() → Dict[str, Any]` — Build complete CQE pipeline
- `query(entry_atom, tau=0.1) → Dict[str, Any]` — Run CQE query

## Utility / Internal Symbols

| Symbol | Module | Purpose |
|--------|--------|---------|
| `Phase2Orchestrator::__main__::17` | `tda/phase2/__main__.py` | Phase-2 orchestrator instance |
| `Phase3Orchestrator::__main__::20` | `tda/phase3/__main__.py` | Phase-3 orchestrator instance |
| `CQEOrchestrator::cqe::17` | `orchestrators/cqe.py` | CQE orchestrator instance |
| `LSHOrchestrator::lsh::17` | `orchestrators/lsh.py` | LSH orchestrator instance |
| `ScannerOrchestrator::orchestrator::40` | `scanner/orchestrator.py` | Scanner orchestrator instance |
| `SkeletonOrchestrator::skeleton::25` | `orchestrators/skeleton.py` | Skeleton orchestrator instance |
| `PhantomOrchestrator::phantom::24` | `orchestrators/phantom.py` | Phantom orchestrator instance |
| `MorphOrchestrator::morph::15` | `orchestrators/morph.py` | Morph orchestrator instance |
| `TraversalOrchestrator::traversal_orchestrator::66` | (TBD) | Traversal orchestrator instance |
| `TDAService::tda_service::14` | `service/tda_service.py` | TDA service instance |
| `BaseService::base::12` | `service/base.py` | Base service instance |
| `ServiceRegistry::registry::12` | `service/registry.py` | Service registry singleton |
| `ScannerService::scanner_service::13` | `service/scanner_service.py` | Scanner service instance |
| `CQEService::cqe_service::15` | `service/cqe_service.py` | CQE service instance |
| `VisualizationService::visualization_service::13` | `service/visualization_service.py` | Visualization service |
| `DatabaseManager::database::15` | `database.py` | Database manager |
| `MigrationManager::migrations::15` | `migrations.py` | Migration manager |
| `ShadowDraftManager::shadow_draft_tools::21` | `shadow_draft_tools.py` | Shadow draft manager |

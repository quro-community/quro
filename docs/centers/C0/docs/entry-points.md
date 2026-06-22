# C0: Entry Points

> **Center:** C0 | **Archetype:** Hub | **Symbols:** 919
> **Status:** Populated — first exploration session complete

## Overview

C0 has 3 recognized entry points from the TDA landscape partitioning. These serve as the primary interfaces into the center's functionality. Each has been classified via the TDA role system.

## Entry Point Analysis

### 1. `sym::QuroV3Service::service::81` — Primary MCP Service Entry

| Attribute | Value |
|-----------|-------|
| **File** | `quro_mcp/service.py:81` |
| **TDA Role** | TRANSIENT |
| **Forward Magnitude** | 0.54 |
| **Backward Tension** | 0.42 |
| **Source Diversity** | 0.96 |
| **In-Degree** | 7 |
| **Out-Degree** | 1 |
| **Callers** | `pipeline/cqe/builder.py`, `quro_mcp/__init__.py`, `quro_mcp/server.py`, `service/cqe_service.py`, `service/tda_service.py` |

**Description:** The main MCP service class wrapping all Quro functionality. This is the primary consumer-facing entry point, exposed through the MCP server (FastMCP). Provides methods for workspace scanning, CQE queries, TDA topological analysis, and symbol/category retrieval.

**Methods exposed via MCP:** `scan_workspace`, `cqe_query`, `cqe_query_with_mode`, `cqe_query_multi_tier`, `get_symbol`, `get_category`, `list_categories`, `list_symbols`, `get_stats`, `tda_find_upstream`, `tda_escape_sink`, `tda_get_field_vector`, `tda_classify_role`

**Boundary behavior:** Instantiates CQE orchestrators, scanner orchestrators, and index builders. Delegates TDA operations to `CQEService`/`TDAService`. Managed by `ServiceRegistry`.

---

### 2. `sym::enrich::types::55` — Type Enrichment Entry

| Attribute | Value |
|-----------|-------|
| **File** | `types.py:55` (legacy `quro_cli` entry) |
| **TDA Role** | TRANSIENT |
| **Forward Magnitude** | 0.0 (leaf) |
| **Backward Tension** | 0.30 |
| **Source Diversity** | 0.85 |
| **In-Degree** | 7 |
| **Out-Degree** | 0 |

**Description:** Type enrichment entry point from the legacy `quro_cli` system. Triggers AI-driven semantic re-scanning to populate role/intent tags. Uses `WorkspaceScanner` with `enable_semantic_analysis=True` for enrichment.

**Boundary behavior:** Connects to async PostgreSQL via `asyncpg`. Delegates to `WorkspaceScanner.scan()` with `use_ai` flag. This is a deprecated entry point — newer systems use `ScannerService` directly.

---

### 3. `sym::get_all_nodes::memory::108` — Memory Registry Access

| Attribute | Value |
|-----------|-------|
| **File** | `adapters/manifold/*/memory.py:108` (and SQLite adapter) |
| **TDA Role** | TRANSIENT |
| **Forward Magnitude** | 0.54 |
| **Backward Tension** | 0.46 |
| **Source Diversity** | 1.0 |
| **In-Degree** | 6 |
| **Out-Degree** | 1 |

**Description:** Retrieves all nodes from the memory registry / SQLite adapter. Used by `ScannerMemoryAdapter`, `SQLiteRegistryAdapter`, and the deprecated `ManifoldAdapter.postgres` variant.

**Boundary behavior:** Returns all stored `GraphNode` objects. Called by `QuroV3Service` for symbol enumeration and by upstream calls from C1 storage layer.

## Entry Point Call Flow Summary

```
External Consumer
  │
  ├─ MCP Server (FastMCP) → QuroV3Service
  │     ├─ .scan_workspace() → ScannerService → ScannerOrchestrator → IndexBuilder → C1
  │     ├─ .cqe_query() → CQEService → CQEOrchestrator → CQEKernel
  │     ├─ .cqe_query_multi_tier() → multiple CQE queries at different taus
  │     ├─ .get_symbol() / .get_category() / .list_*() → C1 (registry)
  │     ├─ .tda_find_upstream() → TDA (backward navigation)
  │     ├─ .tda_escape_sink() → TDA (upstream escape)
  │     ├─ .tda_classify_role() → TDA (role classification)
  │     └─ .get_stats() → combined statistics
  │
  ├─ CLI (deprecated `quro enrich`) → enrich() → WorkspaceScanner
  │
  └─ Programmatic API → CQEPipelineBuilder → QuroV3Service + ScannerOrchestrator + IndexBuilder
```

## Energy Profile Summary

| Entry Point | Forward Mag | Role | Energy Band |
|-------------|-------------|------|-------------|
| `QuroV3Service::service::81` | 0.54 | TRANSIENT | Low (entry proxy) |
| `enrich::types::55` | 0.0 | TRANSIENT (leaf) | Low (legacy CLI) |
| `get_all_nodes::memory::108` | 0.54 | TRANSIENT | Low (data access) |

Note: Entry points show low forward magnitude because they are TRANSIENT boundary symbols. The **true high-energy symbols** in C0 are the internal orchestrators:

| High-Energy Symbol | Forward Mag | Role |
|--------------------|-------------|------|
| CQEOrchestrator | 43.9 | CONVERTER |
| PhantomOrchestrator | 29.6 | EMITTER |
| ServiceRegistry | 27.7 | EMITTER |
| BaseService | 20.0 | EMITTER |
| MorphOrchestrator | 19.1 | EMITTER |
| LSHOrchestrator | 17.1 | EMITTER |
| SkeletonOrchestrator | 16.6 | EMITTER |

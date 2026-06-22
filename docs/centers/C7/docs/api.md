# C7 API Surface — Shadow Draft & Tools Chain

## Entry Points

### 1. `get_in_neighbors(node: str) -> List[str]`
- **Module:** tda/adapters/file_graph.py (7 variants across graph implementations)
- **Role:** CONVERTER (forward_magnitude: 2.54, in: 51, out: 36)
- **Description:** Returns all nodes that point to the given node (incoming edges). Part of the TDA graph abstraction layer. O(1) lookup via reverse index.
- **Callers:** TDA phase 3-5 algorithms (pass4_center_detection, pass5_inter_center_graph)

### 2. `get_draft_status(symbol: str) -> Dict[str, Any]`
- **Module:** shadow/shadow_draft_tools.py:252
- **Role:** CONVERTER (forward_magnitude: 1.42, in: 15, out: 8)
- **Description:** Polls the status of a shadow draft by symbol name. Returns status (PENDING/REJECTED/MATERIALIZED), risk_score, warnings, timestamps.
- **Callers:** MCPTools (tools.py:1854), ShadowTools (shadow_tools.py:148), tools_modular.py:367

### 3. `shutdown()`
- **Module:** analysis/typescript_analyzer.py:79
- **Role:** CONVERTER (forward_magnitude: 2.31, in: 15, out: 8)
- **Description:** Gracefully shuts down the TypeScript analyzer, stopping the probe subprocess.

## Shadow Draft Tools

### ShadowDraftManager (shadow_draft_tools.py:21)

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_shadow_draft` | `(symbol, atoms, language, target_path, auto_eject) → Dict` | Create shadow draft from atom sequence |
| `eject_shadow_draft` | `(symbol, force) → Dict` | Materialize draft to filesystem after MC validation |
| `get_draft_status` | `(symbol) → Dict` | Poll draft status |
| `approve_self_heal` | `(symbol, corrected_atoms) → Dict` | Approve self-heal with corrected atom sequence |
| `_generate_draft_id` | `(symbol, atoms) → str` | Generate unique draft ID (SHA256) |
| `_compute_checksum` | `(atoms) → str` | Compute checksum for atom sequence |

### MCP ShadowTools (mcp/tools/shadow_tools.py:21)

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_shadow_draft` | `(symbol, atoms, language, target_path, auto_eject) → Dict` | Create draft in staging area |
| `eject_shadow_draft` | `(symbol, force) → Dict` | Materialize draft to filesystem |
| `get_draft_status` | `(symbol) → Dict` | Poll draft status |

## TypeScript Analyzer

### TypeScriptAnalyzer (analysis/typescript_analyzer.py:55)

| Method | Signature | Description |
|--------|-----------|-------------|
| `initialize` | `() → None` | Start probe and initialize analyzer |
| `shutdown` | `() → None` | Stop probe and cleanup |
| `get_symbol_at_position` | `(file_path, line, character) → Optional[SymbolInfo]` | Get symbol at position (probe → tree-sitter fallback) |
| `find_definition` | `(file_path, line, character) → Optional[SymbolInfo]` | Find definition location |
| `resolve_import` | `(file_path, import_path) → Optional[str]` | Resolve import to absolute path |
| `get_file_imports` | `(file_path) → List[ImportInfo]` | Get all imports (tree-sitter) |
| `get_file_exports` | `(file_path) → List[SymbolInfo]` | Get all exports (tree-sitter) |
| `get_diagnostics` | `(file_path) → List[Diagnostic]` | Get TS diagnostics |
| `health_check` | `() → Dict` | Check analyzer health |

## CQE Pipeline

### CQETools (cqe_tools)

| Function | Description |
|----------|-------------|
| `cqe_diagnose` | Diagnose CQE pipeline health |
| `cqe_get_mi_stats` | Get mutual information statistics |
| `cqe_load_index` | Load CQE index |
| `cqe_train_mi` | Train MI scoring model |
| `cqe_query` | Execute CQE query |
| `cqe_query_enhanced` | Enhanced CQE query with refinements |

### CQECommands (cqe_commands)

| Function | Description |
|----------|-------------|
| `run_update` | Update CQE index |
| `run_build` | Build CQE index |
| `run_rebuild` | Rebuild CQE index |
| `run_query` | Execute query command |

## Registry Operations

### Symbol Registry

| Function | Module | Description |
|----------|--------|-------------|
| `get::registry::40` | registry | Generic dictionary get |
| `build_reverse_index::registry_v2::293` | registry_v2 | Build reverse symbol index |
| `build_reverse_index::protocol::152` | protocol | Protocol for reverse index |
| `get_symbol_by_name::protocol::52` | protocol | Query symbol by name |
| `get_symbol_by_name::registry_v2::259` | registry_v2 | Persisted symbol lookup |
| `get_symbol_by_uid::postgres::252` | postgres | Symbol lookup by UID |
| `insert_symbol::protocol::36` | protocol | Insert symbol (validation) |
| `insert_symbol::registry_v2::85` | registry_v2 | Insert symbol (persistence) |
| `insert_morphism::registry_v2::188` | registry_v2 | Insert morphism relationship |
| `insert_morphism::postgres::369` | postgres | Persist morphism |
| `insert_morphism::protocol::100` | protocol | Morphism protocol |
| `get_morphisms_from::postgres::429` | postgres | Query morphisms |
| `get_morphisms_from::protocol::116` | protocol | Morphism query protocol |
| `get_node::postgres::94` | postgres | Get node by ID |
| `delete_node::postgres::147` | postgres | Delete node |
| `delete_node::protocol::70` | protocol | Delete node protocol |
| `upsert_node::protocol::30` | protocol | Upsert node |

## Scanner Tools

| Function | Description |
|----------|-------------|
| `scan_workspace::scan_tools::416` | Scan workspace for symbols |
| `scan::scanner::295` | Core scanner |
| `scan::scan_tools::177` | Scan tool wrapper |
| `index_symbols::scan_tools::429` | Index found symbols |
| `enrich::scan_tools::361` | Enrich symbol metadata |
| `save_file_morphism::scan_tools::472` | Save file morphism |
| `main::scanner::1451` | Scanner main entry |

## QRA Tools

| Function | Description |
|----------|-------------|
| `commit_reasoning::qra_tools::68` | Commit reasoning chain |
| `commit_chain::qra_tools::113` | Commit reasoning chain |
| `get_chain::qra_tools::32` | Get reasoning chain |

## Database Management

| Function | Description |
|----------|-------------|
| `connect::database::31` | Connect to database |
| `disconnect::database::49` | Disconnect from database |
| `health_check::database::124` | Database health check |
| `init_database::database::163` | Initialize database |
| `close_database::database::183` | Close database connection |

## Session Tools

| Function | Description |
|----------|-------------|
| `update_session::session_tools::30` | Update session metadata |
| `get_morph_alerts::session_tools::69` | Get morph alerts |
| `get_nrt_alerts::session_tools::132` | Get near-real-time alerts |

## Other Symbol Tools

| Function | Description |
|----------|-------------|
| `identify_symbol::symbol_tools::117` | Identify symbol with behavioral tags |
| `distill_patch_context::symbol_tools::723` | Extract patch context |
| `read_source_symbol::symbol_tools::556` | Read symbol source code |
| `trace_logic_path::symbol_tools::849` | Trace logic path |
| `verify_symbol_integrity::symbol_tools::636` | Verify symbol integrity |
| `query_semantic_inventory::symbol_tools::1329` | Query semantic inventory |
| `get_vocabulary::symbol_tools::1414` | Get vocabulary |
| `get_pitfall::symbol_tools::920` | Get common pitfalls |
| `project_panorama::symbol_tools::973` | Project panorama overview |
| `compact_context::symbol_tools::782` | Compact symbol context |
| `quro_explore::symbol_tools::1126` | Explore Quro workspace |
| `compute_checksum::protocol::84` | Compute checksum |

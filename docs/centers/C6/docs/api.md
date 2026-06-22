# C6: Type System & Validation Chain — API Surface

## Scanner Types (`scanner/types.py`)

### `ParsedSymbol` (dataclass, frozen)
Immutable raw symbol data from AST.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Symbol name |
| `kind` | `str` | `function`, `async_function`, `class`, `method`, `async_method`, `variable` |
| `file_path` | `str` | Relative file path |
| `line` | `int` | 1-indexed line number |
| `char` | `int` | 0-indexed character offset |
| `signature` | `Optional[str]` | Function/method signature |
| `calls` | `Tuple[str, ...]` | Called symbol names |
| `imports` | `Tuple[str, ...]` | Import paths |
| `decorators` | `Tuple[str, ...]` | Decorator names |
| `docstring` | `Optional[str]` | Docstring (first line) |
| `ast_kind` | `Optional[str]` | Raw AST node kind |

### `SymbolFeatures` (dataclass, frozen)
Behavioral features extracted from symbol.

| Field | Type | Description |
|-------|------|-------------|
| `behavioral_tags` | `Tuple[str, ...]` | Behavioral tags (async, lock, raii, network) |
| `structural_tags` | `Tuple[str, ...]` | Structural tags (entry_point, factory, singleton) |
| `risk_anchors` | `Tuple[str, ...]` | Risk patterns (orphan_lock, unguarded_await) |
| `lsh_signature` | `Optional[str]` | MinHash LSH signature (128-band) |

### `SymbolInfo` (dataclass, frozen) — **Entry Point 1**
Enriched symbol combining ParsedSymbol + SymbolFeatures.

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `ParsedSymbol` | Core symbol data |
| `features` | `SymbolFeatures` | Extracted features |
| `fingerprint` | `str` | Content-based SHA256 fingerprint |
| `metadata` | `Dict[str, Any]` | Optional metadata (file size, language) |

### `FileInfo` (dataclass, frozen)
File metadata.

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | `str` | Relative file path |
| `language` | `str` | `python`, `typescript`, `javascript` |
| `fingerprint` | `str` | SHA256 fingerprint |
| `size_bytes` | `int` | File size |
| `symbol_count` | `int` | Extracted symbols count |
| `scan_time_ms` | `float` | Scan time in milliseconds |

### `ScanResult` (dataclass, frozen)
Complete scan result.

| Field | Type | Description |
|-------|------|-------------|
| `file_info` | `FileInfo` | File metadata |
| `symbols` | `Tuple[SymbolInfo, ...]` | Extracted symbols |
| `edges` | `Tuple[Tuple[str, str, str], ...]` | Call graph edges: (from, to, kind) |
| `errors` | `Tuple[str, ...]` | Parse errors |

## Scanner Gate Chain (`scanner/gates/`)

### `GateResult` (dataclass, frozen) — **High traffic** (in=32, out=13)
Validation result shared across all gates.

| Field | Type | Description |
|-------|------|-------------|
| `passed` | `bool` | True if validation passed |
| `reason` | `Optional[str]` | Rejection reason (None if passed) |
| `modified_data` | `Optional[Dict]` | Modified data (for transform gates) |
| `metadata` | `Optional[Dict]` | Additional metadata |

### `SymbolFilterGate` (class, static methods)

| Method | Signature | Description |
|--------|-----------|-------------|
| `validate` | `(symbol: ParsedSymbol) -> GateResult` | Validate against blacklist, length, private, test, lambda |
| `is_noise_symbol` | `(symbol: ParsedSymbol) -> bool` | Convenience: returns `not validate(symbol).passed` |

### `FileFilterGate` (class)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(workspace_root: Path, quroignore_patterns: Set[str] \| None)` | Initialize with workspace root |
| `validate` | `(file_path: Path) -> GateResult` | Validate: exists → is_file → extension → quroignore → size → binary |

### `FeatureGate` (class, static methods)

| Method | Signature | Description |
|--------|-----------|-------------|
| `validate` | `(features: SymbolFeatures) -> GateResult` | Cap features at 100, priority sort |
| `validate_tag_format` | `(tag: str) -> bool` | Check lowercase, alphanumeric, 2-50 chars |
| `deduplicate_features` | `(features: SymbolFeatures) -> SymbolFeatures` | Remove duplicate tags |

### `ScannerGateChain` (class, orchestrator)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(workspace_root: Path)` | Initialize gate chain |
| `validate_file` | `(file_path: Path) -> GateResult` | Validate file through file gate |
| `validate_symbol` | `(symbol: ParsedSymbol) -> GateResult` | Validate symbol through symbol gate |
| `validate_features` | `(features: SymbolFeatures) -> GateResult` | Validate/cap features |
| `get_rejection_stats` | `() -> Dict[str, int]` | Get rejection statistics |
| `reset_stats` | `() -> None` | Reset statistics |

## Pipeline Input Gates (`pipeline/cqe/input_gates.py`)

### `GateResult` (dataclass, frozen) — **CQE-specific**
Same shape as scanner GateResult but in the pipeline context.

### `SymbolBlacklistGate` (class, static)

| Method | Signature | Description |
|--------|-----------|-------------|
| `validate` | `(symbol_name: str) -> GateResult` | Check against generic name blacklist |

### `FilePathIntegrityGate` (class)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(project_root: Path, ignore_parser=None)` | Initialize |
| `validate` | `(file_path: str) -> GateResult` | Check exists, not ignored, has directory |

### `FeatureCapGate` (class, static)

| Method | Signature | Description |
|--------|-----------|-------------|
| `validate` | `(features: List) -> GateResult` | Cap at 1000 features, return modified_data |

### `InputGateChain` (class, orchestrator)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(project_root: Path, ignore_parser=None)` | Initialize chain |
| `validate_atom` | `(symbol_name: str, file_path: str, features: List) -> GateResult` | **Entry Point 2**: Sequential validation through all 3 gates |
| `get_rejection_stats` | `() -> Dict[str, int]` | Get rejection stats |
| `_track_rejection` | `(reason: str) -> None` | Track rejection reason |

## Structural Tag Extraction (`deprecated/quro_cli/analysis/structural_tag_extractor.py`)

### `StructuralTags` (dataclass, frozen) — **Entry Point 3**
Immutable tag extraction result.

| Field | Type | Description |
|-------|------|-------------|
| `tags` | `Tuple[str, ...]` | Sorted tuple of tag strings |
| `role` | `str` | Inferred role (see ROLE_* constants) |
| `source` | `str` | `structural`, `llm`, or `merged` |

### Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `extract_tags` | `(*, kind, source_code, symbol_name, file_path, decorators, call_count) -> StructuralTags` | Primary tag extraction — deterministic, closed-vocabulary |
| `_infer_role` | `(*, kind, tags, symbol_name, file_path, call_count, decorators) -> str` | Priority-ordered role inference |
| `merge_with_llm_tags` | `(structural: StructuralTags, llm_tags: Optional[List[str]]) -> StructuralTags` | Additive LLM merge (structural authoritative) |

### Role Constants

| Constant | Value |
|----------|-------|
| `ROLE_RESOURCE_MANAGER` | class + raii/lock/atomic |
| `ROLE_IO_HANDLER` | filesystem/network/database/io_bound tags |
| `ROLE_COORDINATOR` | call_count >= 5 or name matches |
| `ROLE_TRANSFORMER` | parse tag or name matches |
| `ROLE_CONFIGURATION` | config file or name matches |
| `ROLE_CONTAINER` | class with no behavioral tags |
| `ROLE_CORE_INFRASTRUCTURE` | engine/registry/daemon naming |
| `ROLE_UNKNOWN` | Default fallback |

## Graph Adapter Protocol (`adapters/graph/protocol.py`)

### `GraphAdapter` (Protocol)
Read-only graph access interface.

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_node` | `(node_id: str) -> GraphNode \| None` | Get node by ID |
| `neighbors` | `(node_id: str) -> Iterable[Tuple[str, float]]` | Get (neighbor_id, weight) tuples |
| `edges` | `(node_id: str) -> Iterable[GraphEdge]` | Get outgoing edges |
| `out_degree` | `(node_id: str) -> int` | Get out-degree |
| `tags` | `(node_id: str) -> Tuple[str, ...]` | Get node tags |
| `reverse_neighbors` | `(node_id: str) -> Iterable[Tuple[str, float]]` | Get incoming edges |
| `in_degree` | `(node_id: str) -> int` | Get in-degree |

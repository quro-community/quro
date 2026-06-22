# C3 API Surface — Semantic Analysis and CQE Refinement Hub

## TDA Classification API

### classify_node_role (`upstream_navigator::325`)
| Parameter | Type | Description |
|-----------|------|-------------|
| symbol | `str` | Symbol ID to classify |
| return | `dict` | Role classification with {role, confidence, forward_magnitude, backward_tension} |

### upstream_navigator (`upstream_navigator::325`)
| Parameter | Type | Description |
|-----------|------|-------------|
| symbol | `str` | Symbol ID to navigate from |
| max_depth | `int` | Maximum upstream traversal depth |
| return | `list[dict]` | Upstream sources with {symbol, distance, score} |

## CQE Refinement API

### SemanticCQERefiner (`refiner::128`)
| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `refine` | `(evaluation_data: dict) → RefinedReport` | `RefinedReport` | Apply semantic refinement to CQE results |
| `compute_confidence` | `(metrics: dict) → float` | `float` | Compute confidence score from quality metrics |
| `generate_report` | `(refined: RefinedReport) → str` | `str` | Generate human-readable quality report |

## Gate Result Types API

### GateResult (`types::13`)
| Type | Fields | Description |
|------|--------|-------------|
| `GateResult` | `status, code, message, data` | Standard gate operation result |
| `GateError` | `code, message, details` | Gate error with error details |
| `GateWarning` | `code, message, severity` | Gate warning with severity level |
| `GateSummary` | `total, passed, failed, warnings` | Aggregated gate statistics |

## MCP Tool Dispatch API

### call_tool
| Parameter | Type | Description |
|-----------|------|-------------|
| tool_name | `str` | Registered tool name |
| arguments | `dict` | Tool-specific arguments |
| return | `dict` | Tool execution result |

## Workspace Scanning API

### scan_workspace
| Parameter | Type | Description |
|-----------|------|-------------|
| workspace_path | `str` | Root path to scan |
| include_patterns | `list[str]` | Glob patterns to include |
| exclude_patterns | `list[str]` | Glob patterns to exclude |
| return | `ScanResult` | Scan summary with symbol list |

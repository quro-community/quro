# C9 Data Flow

> Fanout Utility Layer — 74 symbols

## Flow Pattern

C9 is a **pure fanout** center: all data flows are inward-to-outward. Consumers across C0, C1, C3, and C7 call into C9 entry points to retrieve descriptive metadata, help text, or parse results. C9 itself never initiates calls outward; it responds to queries.

```
┌─────────────────────────────────────────────────────┐
│                     Consumers                        │
│  C0 (Hub)   C1 (Fanout)   C3 (Hub)   C7 (Chain)    │
│         │          │            │          │          │
│         ▼          ▼            ▼          ▼          │
│  ┌───────────────────────────────────────────────┐   │
│  │              C9 Fanout Utility Layer            │   │
│  │                                                 │   │
│  │  sym::get_description   sym::get_help           │   │
│  │  sym::parse_typescript                          │   │
│  └───────────────────────────────────────────────┘   │
│              │          │            │                │
│              ▼          ▼            ▼                │
│  ┌───────────────────────────────────────────────┐   │
│  │              Backing Implementations            │   │
│  │  BaseService    BaseCommand    TreeSitterParser │   │
│  └───────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Data Flow by Entry Point

### 1. `sym::get_description` — Service Description

```
CLI / API Caller
  │
  ├─► CQEService.get_capabilities()      [cqe_service.py:66]
  │     └─► get_description()             [cqe_service.py:30]
  │           Returns: "CQE semantic query and graph navigation"
  │
  ├─► TDAService.get_capabilities()      [tda_service.py:76]
  │     └─► get_description()             [tda_service.py:30]
  │
  ├─► ScannerService.get_capabilities()  [scanner_service.py:47]
  │     └─► get_description()             [scanner_service.py:27]
  │
  └─► VisualizationService.get_capabilities() [visualization_service.py:61]
        └─► get_description()             [visualization_service.py:28]
```

**Data:** `get_description` returns a static `str` — no external data sources, transformations, or side effects.

### 2. `sym::get_help` — CLI Help Text

```
CLI Parser (argparse)
  │
  ├─► cli/main.py:91
  │     └─► command.get_help()
  │           Returns: Help string for each command verb
  │
  ├─► Every CLI command class overrides get_help():
  │     ├── CQEQueryCommand     → "Execute CQE semantic query"
  │     ├── CQESymbolCommand    → "Get symbol details"
  │     ├── CQEListCommand      → "List symbols or categories"
  │     ├── TDAQueryCommand     → "Query TDA graph"
  │     ├── TDACommand          → "TDA pipeline subcommand"
  │     ├── ScannerCommand      → "Scan workspace"
  │     ├── VisualizeCommand    → "Visualize knowledge graph"
  │     └── TDAPipeline*        → Pipeline-specific help
```

**Data:** Each `get_help()` returns a static `str` — no variable inputs, just constant text.

### 3. `sym::parse_typescript` — TypeScript Parsing

```
Code Analysis Pipeline
  │
  └─► TreeSitterParser.parse_typescript(file_path)
        │
        ├── Input:  str (file path)
        ├── Process: Try tree-sitter, fall back to regex
        ├── Output: Optional[Any] (parse tree or None)
        └── Status: ⚠️ Stub — currently always returns None
                     (tree-sitter libraries not installed)
```

**Data:**
- **Input:** `file_path: str` — absolute path to `.ts` file
- **Transformation:** Attempts tree-sitter native parsing; on `ImportError` or failure, returns `None`
- **Output:** `Optional[Any]` — either a tree-sitter parse tree or `None`
- **Side effects:** None (pure function of file contents)
- **Deprecation note:** This lives in `deprecated/quro_cli/` — replaced by the newer AST analysis pipeline

## Flow Metrics

| Entry Point | Avg Backward Tension | Consumer Count | Data Volume |
|-------------|---------------------|----------------|-------------|
| `get_description` | 0.309 | 50 callers | ~40 chars per return |
| `get_help` | 0.042 | 71 callers | ~30 chars per return |
| `parse_typescript` | 0.463 | 16 callers | Variable (file content) |

## Key Observations

1. **No cascading data flow** — C9 is a sink in terms of data dependency; it does not chain to other data sources.
2. **Purely synchronous** — No async, no streaming, no batching.
3. **Trivially testable** — All three entry points are deterministic functions with no external state.
4. **Deprecation risk** — `parse_typescript` is a stub in a deprecated module; its data flow will cease when the legacy pipeline is removed.

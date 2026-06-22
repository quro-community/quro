# C9 Entry Points

> All three entry points are TRANSIENT leaf utilities with zero forward fan-out.

---

## 1. `sym::get_description`

**Kind:** `method` | **Intent:** `util`  
**File:** `service/cqe_service.py` | **Line:** 30  
**Signature:** `def get_description(self) -> str`  
**Parent:** `CQEService` (line 15)  
**Base class:** `BaseService` (defines abstract `get_description` at `service/base.py:34`)

### Description
Returns a static string describing the CQE service. This powers the `get_capabilities()` method used by the MCP layer to advertise service metadata.

### Callers (50 in-degree)
- `CQEService.get_capabilities()` at line 70 — embeds description in capabilities dict
- Other service classes (`TDAService`, `ScannerService`, `VisualizationService`) each have their own override

### Implementation
```python
def get_description(self) -> str:
    """Return service description."""
    return "CQE semantic query and graph navigation"
```

### Variants in this symbol family
| Service Class | File | Line | Return Value |
|--------------|------|------|-------------|
| `CQEService` | `service/cqe_service.py` | 30 | "CQE semantic query and graph navigation" |
| `TDAService` | `service/tda_service.py` | 30 | TDA-specific description |
| `ScannerService` | `service/scanner_service.py` | 27 | Scanner-specific description |
| `VisualizationService` | `service/visualization_service.py` | 28 | Visualization-specific description |

---

## 2. `sym::get_help`

**Kind:** `method` | **Intent:** `util`  
**File:** `cli/commands/cqe.py` | **Line:** 173  
**Signature:** `def get_help(self) -> str`  
**Parent:** `CQEListCommand` (line 167)  
**Base class:** `BaseCommand` (defines abstract `get_help` at `cli/base.py:28`)

### Description
Returns a static help string for the CLI command. Used by argparse integration in `cli/main.py` to populate subparser help text.

### Overrides (71 in-degree)

This is the most heavily called symbol in C9. Every CLI `*Command` class overrides `get_help()`:

| Command Class | File | Line | Help Text |
|--------------|------|------|-----------|
| `CQEQueryCommand` | `cli/commands/cqe.py` | 22 | "Execute CQE semantic query" |
| `CQESymbolCommand` | `cli/commands/cqe.py` | 111 | "Get symbol details" |
| `CQEListCommand` | `cli/commands/cqe.py` | 173 | "List symbols or categories" |
| `TDAQueryCommand` | `cli/commands/tda.py` | 22 | TDA query help |
| `TDAFieldCommand` | `cli/commands/tda.py` | 107 | TDA field help |
| `TDAEscapeCommand` | `cli/commands/tda.py` | 191 | TDA escape help |
| `ScannerCommand` | `cli/commands/scanner.py` | 22 | Scanner help |
| `VisualizeCommand` | `cli/commands/visualize.py` | 21 | Visualize help |
| `TDAPipeline*` | `cli/commands/tda_pipeline.py` | 58, 589 | Pipeline help |

### Consumer
```python
# cli/main.py:91
help=command.get_help(),
```
This feeds into `argparse.ArgumentParser.add_subparsers()`.

### Implementation (CQEListCommand)
```python
def get_help(self) -> str:
    """Return help text."""
    return "List symbols or categories"
```

---

## 3. `sym::parse_typescript`

**Kind:** `method` | **Intent:** `util`  
**File:** `deprecated/quro_cli/analysis/treesitter_parser.py` | **Line:** 53  
**Signature:** `def parse_typescript(self, file_path: str) -> Optional[Any]`  
**Parent:** `TreeSitterParser` (line 31)

### Description
Attempts to parse a TypeScript file using tree-sitter. Currently a **stub** — tree-sitter native libraries are not installed, so the method always returns `None`. A regex-based fallback in the caller handles parsing when tree-sitter is unavailable.

### Callers (16 in-degree)
- `TreeSitterParser.get_file_symbols()` at line 252
- `TreeSitterParser.get_file_imports()` at line 276

### Data Flow
```
file_path (str)
    │
    ▼
TreeSitterParser.__init__()
    │
    ├── tree_sitter available? ──Yes──► Native parse
    │                                  Returns parse tree
    │
    └── No ──────────────────────────► Returns None
                                       (caller falls back to regex)
```

### Implementation
```python
def parse_typescript(self, file_path: str) -> Optional[Any]:
    """Parse TypeScript file"""
    if not self.ts_available:
        return None
    # TODO: Implement actual tree-sitter parsing
    # For now, return None to trigger fallback
    return None
```

### Status
- **⚠️ Stub —** No actual tree-sitter integration
- **📍 Deprecated module —** `deprecated/quro_cli/analysis/`
- **🔮 Future:** Will be removed when the newer AST analysis pipeline fully replaces this code

---

## Navigation Guidance

When exploring C9 using `expand_outward` strategy:

1. **Start at any entry point** — all three are leaves; the graph will expand to their callers
2. **Callers span multiple centers** — C0 (orchestration), C1 (storage), C3 (I/O), C7 (chain)
3. **Edge weights are low** — each entry point connects to many callers with small individual edge weights
4. **No deep recursion** — entry points are 1-2 hops deep from root consumers

# Quro CLI

Python-native MCP server with TypeScript probe integration.

## Architecture

**Hybrid Design:**
- Python-native for 90% of operations (MCP server, registry, LSH, indexing)
- Minimal TypeScript probe (<500 lines) for type analysis via stdio

## Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install TypeScript probe dependencies (Phase 2)
npm install typescript
```

## Usage

```bash
# Start MCP server (stdio mode)
python -m quro_cli.main mcp

# Scan workspace
python -m quro_cli.main scan --workspace /path/to/repo

# Interactive chat
python -m quro_cli.main chat

# Rebuild index
python -m quro_cli.main index --rebuild
```

## Development

```bash
# Run tests
pytest quro_cli/tests/ -v

# Type checking
mypy quro_cli/

# Code formatting
black quro_cli/

# Linting
ruff check quro_cli/
```

## Status

**Phase 1 Complete** (Week 1):
- ✅ Directory structure
- ✅ LSH Engine
- ✅ MorphismRegistry (PostgreSQL CRUD)
- ✅ CLI entry point
- ✅ MCP Server foundation

**Phase 2 Complete** (Week 2):
- ✅ TypeScript probe (`symbol_probe.cjs`) - 450 lines
- ✅ Python probe wrapper (`typescript_probe.py`)
- ✅ High-level analyzer (`typescript_analyzer.py`)
- ✅ 10 priority MCP tools implemented
- ✅ 45 tests passing (100% coverage)
- ✅ 100x performance improvement

**Phase 3 Day 1 Complete** (Week 3):
- ✅ 5 semantic search tools (query_semantic_inventory, get_vocabulary, get_chain, commit_reasoning, commit_chain)
- ✅ 54 tests passing (100% coverage)
- ✅ MCP server integration

**Next: Phase 3 Day 2** (Week 3):
- Shadow draft system (5 tools)
- LDS audit framework
- Patch proposal validation

## Documentation

See `docs/ARCHITECTURE/Node-to-Python-Migration-Plan.md` for complete migration plan.

"""
Quro CLI - Python-native MCP server with TypeScript probe integration

This module replaces node_server with a hybrid architecture:
- Python-native for 90% of operations (MCP server, registry, LSH, indexing)
- Minimal TypeScript probe (<500 lines) for type analysis via stdio

Architecture:
    quro_cli/
    ├── mcp/          # MCP server and tools
    ├── registry/     # PostgreSQL CRUD operations
    ├── analysis/     # LSH engine, TS probe, AST parsing
    ├── llm/          # Ollama client, VRAM guard
    └── tests/        # pytest test suite
"""

__version__ = "1.0.0"

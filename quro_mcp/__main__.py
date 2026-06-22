#!/usr/bin/env python3
"""MCP Server entry point.

Usage:
    python -m quro_mcp
"""

import os
import asyncio
from pathlib import Path

from quro_mcp.server import app


async def main():
    """Main entry point."""
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    # Initialize workspace
    workspace = os.environ.get("QURO_PROJECT_ROOT", str(Path.cwd()))
    from quro_mcp.server import _initialize_workspace
    _initialize_workspace(workspace)
    
    asyncio.run(main())

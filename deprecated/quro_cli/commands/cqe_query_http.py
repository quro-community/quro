#!/usr/bin/env python3
"""CLI command for querying HTTP endpoints from CQE index.

Usage:
    quro cqe-query-http <symbol_pattern> [--json]

Examples:
    quro cqe-query-http quro_morph
    quro cqe-query-http server --json
"""

import sys
from pathlib import Path
import click

from quro_cli.mcp.tools.http_query import query_http_endpoints


@click.command()
@click.argument('symbol_pattern')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
@click.option('--index', default='.quro_context/cqe_index.db', help='Path to CQE index')
def main(symbol_pattern: str, output_json: bool, index: str):
    """Query HTTP endpoints from CQE index."""
    index_path = Path(index)

    if not index_path.exists():
        click.echo(f"❌ CQE index not found: {index_path}", err=True)
        sys.exit(1)

    output_format = 'json' if output_json else 'text'
    result = query_http_endpoints(index_path, symbol_pattern, output_format)
    click.echo(result)


if __name__ == '__main__':
    main()

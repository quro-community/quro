"""
CLI command for querying CQE with semantic filtering

@module quro_cli.commands.cqe_query_semantic
@intent Provide CLI interface for semantic-filtered CQE queries

Usage:
    quro cqe-query-semantic <query> <entry_token> [--framework http] [--type endpoint] [--method GET]

Examples:
    quro cqe-query-semantic "authentication logic" "quro_morph" --framework http --type endpoint --method GET
    quro cqe-query-semantic "user data" "user_service" --framework graphql --type resolver
"""

import sys
from pathlib import Path
import click

from quro_cli.mcp.tools.cqe_query_enhanced import (
    cqe_query_enhanced,
    SemanticFilter,
    format_semantic_results,
)


@click.command()
@click.argument('query')
@click.argument('entry_token')
@click.option('--framework', help='Framework filter (http, graphql, grpc)')
@click.option('--type', 'filter_type', help='Type filter (endpoint, middleware, resolver)')
@click.option('--method', help='HTTP method filter (GET, POST, etc.)')
@click.option('--path-pattern', help='Path pattern filter (/api/*)')
@click.option('--tau', default=0.1, help='MI-gate threshold [0,1]')
@click.option('--max-depth', default=3, help='Maximum BFS hops')
@click.option('--index', default='.quro_context/cqe_index.db', help='Path to CQE index')
def main(
    query: str,
    entry_token: str,
    framework: str | None,
    filter_type: str | None,
    method: str | None,
    path_pattern: str | None,
    tau: float,
    max_depth: int,
    index: str,
):
    """Query CQE with semantic filtering."""
    import asyncio

    index_path = Path(index)

    if not index_path.exists():
        click.echo(f"❌ CQE index not found: {index_path}", err=True)
        sys.exit(1)

    # Build semantic filter
    semantic_filter = None
    if framework or filter_type or method or path_pattern:
        semantic_filter = SemanticFilter(
            framework=framework,
            type=filter_type,
            method=method,
            path_pattern=path_pattern,
        )

    # Run query
    result = asyncio.run(cqe_query_enhanced(
        index_path=index_path,
        query=query,
        entry_token=entry_token,
        tau=tau,
        max_depth=max_depth,
        semantic_filter=semantic_filter,
    ))

    # Format and print results
    output = format_semantic_results(result)
    click.echo(output)


if __name__ == '__main__':
    main()

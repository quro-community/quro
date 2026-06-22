"""
LSH Commands - CLI plugin for MinHash LSH Engine

@module quro_cli.commands.lsh_commands
@intent Provide CLI commands for MinHash signature generation

Commands:
  - lsh generate: Generate MinHash signatures for all symbols in database
"""

import click
import asyncio

from quro_cli.config import QURO_DB_URL


METADATA = {
    "description": "MinHash LSH Engine - Semantic similarity signature generation",
    "commands": {
        "lsh generate": {
            "description": "Generate MinHash signatures for all symbols in database",
            "usage": "quro lsh generate [--db-url postgres://localhost/quro] [--batch-size 100]",
            "implementation": "quro_cli/commands/lsh_commands.py:lsh_generate",
        },
    },
}


def register(cli: click.Group):
    """Register LSH commands with CLI"""
    cli.add_command(lsh_group)


@click.group("lsh")
def lsh_group():
    """MinHash LSH Engine - Semantic similarity signature generation"""
    pass


@lsh_group.command("generate")
@click.option(
    "--db-url",
    default=QURO_DB_URL,
    help="PostgreSQL database URL (default: QURO_DB_URL env)",
)
@click.option(
    "--batch-size", default=100, type=int, help="Number of symbols to process per batch"
)
def lsh_generate(db_url: str, batch_size: int):
    """Generate MinHash signatures for all symbols in database

    Examples:
        quro lsh generate
        quro lsh generate --batch-size 200
    """
    from quro_cli.analysis.lsh_engine import generate_minhash_for_all_symbols

    click.echo("🔍 MinHash LSH Generation")
    click.echo("=" * 60)
    click.echo(f"DB URL: {db_url}")
    click.echo(f"Batch size: {batch_size}")
    click.echo()

    try:
        asyncio.run(
            generate_minhash_for_all_symbols(db_url=db_url, batch_size=batch_size)
        )
        click.echo("\n✅ MinHash generation complete")
    except Exception as e:
        click.echo(f"\n❌ Generation failed: {e}", err=True)
        raise

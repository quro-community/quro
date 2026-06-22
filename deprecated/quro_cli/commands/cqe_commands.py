"""
CQE Commands - CLI plugin for Categorical Query Engine

@module quro_cli.commands.cqe_commands
@intent Provide CLI commands for CQE index building and management

Commands:
  - cqe-build: Build CQE offline index from PostgreSQL registry
  - cqe-stats: Show CQE index statistics
  - cqe-rebuild: Force rebuild CQE index
  - cqe-update: Incremental update of CQE index (fast)
  - cqe-daemon: Manage CQE daemon service
"""

import click
import asyncio
from pathlib import Path


# Plugin metadata for command indexing
METADATA = {
    'description': 'Categorical Query Engine - Offline index building and management',
    'commands': {
        'cqe-build': {
            'description': 'Build CQE offline index from PostgreSQL registry',
            'usage': 'quro cqe-build [--force] [--project-root .]',
            'implementation': 'quro_cli/commands/cqe_commands.py:cqe_build'
        },
        'cqe-stats': {
            'description': 'Show CQE index statistics',
            'usage': 'quro cqe-stats',
            'implementation': 'quro_cli/commands/cqe_commands.py:cqe_stats'
        },
        'cqe-rebuild': {
            'description': 'Force rebuild CQE index',
            'usage': 'quro cqe-rebuild [--project-root .]',
            'implementation': 'quro_cli/commands/cqe_commands.py:cqe_rebuild'
        },
        'cqe-update': {
            'description': 'Incremental update of CQE index (fast)',
            'usage': 'quro cqe-update [--force-full]',
            'implementation': 'quro_cli/commands/cqe_commands.py:cqe_update'
        },
        'cqe-daemon': {
            'description': 'Manage CQE daemon service (start/stop/status/reload)',
            'usage': 'quro cqe-daemon [start|stop|status|reload]',
            'implementation': 'quro_cli/commands/cqe_daemon_commands.py'
        },
        'cqe-query': {
            'description': 'Query CQE with semantic search and MI-gate traversal',
            'usage': 'quro cqe-query "query text" entry_token [tau] [max_depth]',
            'implementation': 'quro_cli/commands/cqe_commands.py:cqe_query'
        },
        'cqe-diagnose': {
            'description': 'Diagnose a CQE query by ID — show voids, delivery stats, atom breakdown',
            'usage': 'quro cqe-diagnose <query_id>',
            'implementation': 'quro_cli/commands/cqe_commands.py:cqe_diagnose'
        }
    }
}


def register(cli: click.Group):
    """Register CQE commands with CLI"""
    cli.add_command(cqe_build)
    cli.add_command(cqe_stats)
    cli.add_command(cqe_rebuild)
    cli.add_command(cqe_update)
    cli.add_command(cqe_query)
    cli.add_command(cqe_diagnose)

    # Register daemon commands
    from quro_cli.commands.cqe_daemon_commands import cqe_daemon_group
    cli.add_command(cqe_daemon_group)


@click.command('cqe-build')
@click.option('--force', is_flag=True, help='Force rebuild even if index exists')
@click.option('--project-root', type=click.Path(exists=True), default='.',
              help='Project root directory')
def cqe_build(force: bool, project_root: str):
    """Build CQE offline index from PostgreSQL registry"""
    from quro_sovereign.cqe_index_pipeline import CQEIndexPipeline
    import json

    click.echo("🔨 Building CQE Offline Index")
    click.echo("="*60)

    async def run_build():
        pipeline = CQEIndexPipeline(project_root=project_root)
        stats = await pipeline.build_offline_index(force_rebuild=force)
        return stats

    try:
        stats = asyncio.run(run_build())

        click.echo("\n✅ CQE Index Build Complete!")
        click.echo(f"\n📊 Statistics:")
        click.echo(json.dumps(stats, indent=2))

        # Show index location
        index_path = Path(project_root) / '.quro_context' / 'cqe_index.db'
        click.echo(f"\n💾 Index saved to: {index_path}")

    except Exception as e:
        click.echo(f"\n❌ Build failed: {e}", err=True)
        raise


@click.command('cqe-stats')
@click.option('--project-root', type=click.Path(exists=True), default='.',
              help='Project root directory')
def cqe_stats(project_root: str):
    """Show CQE index statistics"""
    from quro_sovereign.cqe_index_pipeline import CQEIndexPipeline
    import json

    click.echo("📊 CQE Index Statistics")
    click.echo("="*60)

    pipeline = CQEIndexPipeline(project_root=project_root)
    stats = pipeline._get_index_stats()

    if not stats:
        click.echo("\n⚠️  No CQE index found. Run 'quro cqe-build' first.")
        return

    click.echo(json.dumps(stats, indent=2))


@click.command('cqe-rebuild')
@click.option('--project-root', type=click.Path(exists=True), default='.',
              help='Project root directory')
def cqe_rebuild(project_root: str):
    """Force rebuild CQE index"""
    from quro_sovereign.cqe_index_pipeline import CQEIndexPipeline
    import json

    click.echo("🔄 Rebuilding CQE Index (Force)")
    click.echo("="*60)

    async def run_rebuild():
        pipeline = CQEIndexPipeline(project_root=project_root)
        stats = await pipeline.build_offline_index(force_rebuild=True)
        return stats

    try:
        stats = asyncio.run(run_rebuild())

        click.echo("\n✅ CQE Index Rebuild Complete!")
        click.echo(f"\n📊 Statistics:")
        click.echo(json.dumps(stats, indent=2))

    except Exception as e:
        click.echo(f"\n❌ Rebuild failed: {e}", err=True)
        raise


@click.command('cqe-update')
@click.option('--force-full', is_flag=True, help='Force full rebuild instead of incremental')
@click.option('--project-root', type=click.Path(exists=True), default='.',
              help='Project root directory')
def cqe_update(force_full: bool, project_root: str):
    """Incremental update of CQE index (fast)"""
    from quro_sovereign.cqe_index_pipeline import CQEIndexPipeline
    import json

    click.echo("🔄 CQE Incremental Update")
    click.echo("="*60)

    async def run_update():
        pipeline = CQEIndexPipeline(project_root=project_root)
        stats = await pipeline.update_incremental_auto(force_full=force_full)
        return stats

    try:
        stats = asyncio.run(run_update())

        if stats.get('status') == 'up-to-date':
            click.echo("\n✅ Index is already up-to-date")
        else:
            click.echo("\n✅ Incremental Update Complete!")
            click.echo(f"\n📊 Statistics:")
            click.echo(f"  Modified symbols: {stats.get('symbols_updated', 0)}")
            click.echo(f"  Update time: {stats.get('update_time_sec', 0):.2f}s")

            if 'atoms_count' in stats:
                click.echo(f"  Total atoms: {stats['atoms_count']:,}")
                click.echo(f"  Total morphisms: {stats['morphisms_count']:,}")

    except Exception as e:
        click.echo(f"\n❌ Update failed: {e}", err=True)
        raise


@click.command('cqe-query')
@click.argument('query')
@click.argument('entry_token')
@click.argument('tau', type=float, default=0.1)
@click.argument('max_depth', type=int, default=3)
@click.option('--project-root', type=click.Path(exists=True), default='.',
              help='Project root directory')
@click.option('--auto-resolve/--no-auto-resolve', default=True,
              help='Enable automatic token resolution')
@click.option('--semantic-match/--no-semantic-match', default=True,
              help='Use semantic matching for category resolution')
def cqe_query(query: str, entry_token: str, tau: float, max_depth: int,
              project_root: str, auto_resolve: bool, semantic_match: bool):
    """Query CQE with semantic search and MI-gate traversal

    Examples:
        quro cqe-query "async lock patterns" async 0.1 3
        quro cqe-query "hash functions" hash 0.0 2
        quro cqe-query "database operations" infra 0.1 3
    """
    from quro_cli.mcp.tools.cqe_tools import CQETools

    click.echo("🔍 CQE Query")
    click.echo("="*60)
    click.echo(f"Query: {query}")
    click.echo(f"Entry: {entry_token}")
    click.echo(f"Tau: {tau}")
    click.echo(f"Max depth: {max_depth}")
    click.echo()

    async def run_query():
        tools = CQETools(workspace_root=Path(project_root))

        result = await tools.cqe_query(
            query=query,
            entry_token=entry_token,
            tau=tau,
            max_depth=max_depth,
            auto_resolve=auto_resolve,
            use_semantic_match=semantic_match
        )

        return result

    try:
        result = asyncio.run(run_query())

        # Show token resolution if auto-resolve fired
        if result.get('resolution_method'):
            click.echo(f"📎 Resolved: {result['original_token']} → {result.get('entry', entry_token)}")
            click.echo(f"   Method: {result['resolution_method']} (confidence: {result.get('confidence', 0):.2f})")
            click.echo()

        if result.get('status') == 'success':
            click.echo(f"✅ Query successful")
            click.echo(f"   Entry used: {result.get('entry', entry_token)}")
            click.echo(f"   Nodes visited: {result.get('exec', {}).get('v', 0)}")

            # Show delivery-layered results (same as MCP — filtered by structural match)
            delivery = result.get('delivery', {})
            primary = delivery.get('primary', [])
            secondary = delivery.get('secondary', {})
            total_raw = len(result.get('result', []))

            click.echo(f"   Raw results: {total_raw}, Primary (filtered): {len(primary)}")

            if primary:
                click.echo(f"\n📊 Primary Results ({len(primary)}):")
                for i, res in enumerate(primary[:10], 1):
                    atom_id = res.get('atom_id', 'unknown')
                    score = res.get('score', 0)
                    tier = res.get('delivery_tier', res.get('tier', ''))
                    click.echo(f"   {i}. {atom_id} (w: {score:.4f}, tier: {tier})")

            if secondary:
                click.echo(f"\n📋 Secondary Summary:")
                for atom_type, count in secondary.items():
                    if count > 0:
                        click.echo(f"   {atom_type}: {count}")

            # Fallback: if no delivery layers, show raw results
            if not primary and not secondary and total_raw > 0:
                click.echo(f"\n📊 Top {min(10, total_raw)} Results (raw):")
                for i, res in enumerate(result['result'][:10], 1):
                    atom_id = res.get('id', 'unknown')
                    w = res.get('w', 0)
                    click.echo(f"   {i}. {atom_id} (w: {w:.4f})")
            elif not primary and not secondary:
                click.echo("\n⚠️  No results found")

        else:
            error = result.get('error', 'Unknown error')
            click.echo(f"❌ Query failed: {error}", err=True)
            raise click.Abort()

    except Exception as e:
        click.echo(f"\n❌ Query failed: {e}", err=True)
        raise


@click.command('cqe-diagnose')
@click.argument('query_id')
@click.option('--project-root', type=click.Path(exists=True), default='.',
              help='Project root directory')
def cqe_diagnose(query_id: str, project_root: str):
    """Diagnose a CQE query by ID — semantic voids, delivery efficiency, atom breakdown

    Pass the query_id from a cqe-query response or cqe_reflect output.

    Examples:
        quro cqe-diagnose cqe::1776125874201
        quro cqe-diagnose cqe::1776125874201 --project-root /path/to/project
    """
    from quro_cli.mcp.tools.cqe_tools import CQETools

    click.echo(f"Diagnosing CQE query: {query_id}")
    click.echo("=" * 60)

    async def run_diagnose():
        tools = CQETools(workspace_root=Path(project_root))
        return await tools.cqe_diagnose(query_id)

    try:
        import json
        result = asyncio.run(run_diagnose())

        if result.get('status') != 'success':
            click.echo(f"Error: {result.get('error', 'Unknown')}", err=True)
            hint = result.get('hint')
            if hint:
                click.echo(f"Hint: {hint}")
            return

        traversal = result.get('traversal', {})
        delivery = result.get('delivery', {})
        voids = result.get('semantic_voids')

        click.echo(f"Entry atom: {result.get('entry_atom', 'unknown')}")
        click.echo()
        click.echo("Traversal:")
        click.echo(f"  Atoms built:  {traversal.get('atoms_built', 0)}")
        click.echo(f"  Categories:   {traversal.get('categories', 0)}")
        click.echo(f"  Symbols:      {traversal.get('symbols', 0)}")
        click.echo(f"  Pitfalls:     {traversal.get('pitfalls', 0)}")
        click.echo(f"  path_mi:      {traversal.get('path_mi', 0):.4f}")
        click.echo(f"  payload_rate: {traversal.get('payload_rate', 0):.2%}")
        click.echo()
        click.echo("Delivery:")
        click.echo(f"  Primary:   {delivery.get('primary', 0)}")
        click.echo(f"  Secondary: {delivery.get('secondary', 0)}")
        click.echo(f"  Dropped:   {delivery.get('drop', 0)}")
        rules = delivery.get('rules_applied')
        if rules:
            click.echo(f"  Rules:")
            for rule, count in sorted(rules.items()):
                click.echo(f"    {rule}: {count}")
        click.echo()

        if voids:
            click.echo(f"Semantic voids ({len(voids)}):")
            for v in voids:
                click.echo(f"  - {v}")
            click.echo()
        else:
            click.echo("Semantic voids: none")

        breakdown = result.get('atom_breakdown', {})
        cats = breakdown.get('categories', [])
        syms = breakdown.get('symbols', [])
        pits = breakdown.get('pitfalls', [])

        if cats:
            click.echo(f"Categories ({len(cats)}):")
            for c in cats:
                click.echo(f"  - {c}")
            trunc = breakdown.get('categories_truncated', 0)
            if trunc:
                click.echo(f"  ... and {trunc} more")
        if syms:
            click.echo(f"\nSymbols ({len(syms)}):")
            for s in syms:
                click.echo(f"  - {s}")
            trunc = breakdown.get('symbols_truncated', 0)
            if trunc:
                click.echo(f"  ... and {trunc} more")
        if pits:
            click.echo(f"\nPitfalls ({len(pits)}):")
            for p in pits:
                click.echo(f"  - {p}")

        click.echo()
        click.echo(json.dumps(result, indent=2))

    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        raise

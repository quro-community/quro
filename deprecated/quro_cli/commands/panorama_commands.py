"""
Quro CLI - Panorama Commands

@module panorama_commands
@intent Provide CLI commands for project panorama generation and querying

Commands:
  quro panorama generate  - Generate/update panorama.json
  quro panorama show      - Show current panorama summary
  quro panorama stats     - Show detailed statistics
  quro panorama health    - Show health metrics
"""

import click
import json
import asyncio
from pathlib import Path
from typing import Dict, Any


async def _gather_panorama_data(project_root: Path, include_stats: bool = True, include_health: bool = True) -> Dict[str, Any]:
    """Gather panorama data from project files."""
    panorama = {
        "workspace_root": str(project_root),
        "generated_at": None,  # Will be filled by caller
    }

    if include_stats:
        stats = {
            "total_files": 0,
            "total_symbols": 0,
            "shadow_files": 0,
            "qra_archives": 0,
            "qra_reasoning_entries": 0,
        }

        # Count source files
        for ext in [".py", ".ts", ".js", ".tsx", ".jsx"]:
            stats["total_files"] += len(list(project_root.rglob(f"*{ext}")))

        # Count shadow files
        shadows_path = project_root / ".quro_context" / "shadows"
        if shadows_path.exists():
            stats["shadow_files"] = len(list(shadows_path.rglob("*.qss")))

        # Count QRA archives and reasoning entries
        qra_path = project_root / ".quro_context" / "qra"
        if qra_path.exists():
            stats["qra_archives"] = len(list(qra_path.glob("*.qra")))
            stats["qra_reasoning_entries"] = len(list(qra_path.glob("*.reasoning.jsonl")))

        # Count symbols from registry
        registry_path = project_root / ".quro_context" / "registry.db"
        if registry_path.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(str(registry_path))
                cursor = conn.execute("SELECT COUNT(*) FROM symbols")
                stats["total_symbols"] = cursor.fetchone()[0]
                conn.close()
            except Exception:
                pass

        panorama["stats"] = stats

    if include_health:
        health = {
            "shadow_coverage": 0.0,
            "qra_coverage": 0.0,
            "nrt_alerts": 0,
        }

        # Calculate shadow coverage
        stats = panorama.get("stats", {})
        total_files = stats.get("total_files", 0)
        shadow_files = stats.get("shadow_files", 0)
        if total_files > 0:
            health["shadow_coverage"] = round(shadow_files / total_files, 2)

        # Calculate QRA coverage
        total_symbols = stats.get("total_symbols", 0)
        qra_archives = stats.get("qra_archives", 0)
        if total_symbols > 0:
            health["qra_coverage"] = round(qra_archives / total_symbols, 2)

        # Count NRT alerts
        nrt_alerts_path = project_root / ".quro_context" / "nrt_alerts.jsonl"
        if nrt_alerts_path.exists():
            try:
                with open(nrt_alerts_path, 'r') as f:
                    health["nrt_alerts"] = sum(1 for _ in f)
            except Exception:
                pass

        panorama["health"] = health

    return panorama


@click.group()
def panorama():
    """Project panorama management commands"""
    pass


@panorama.command()
@click.option('--workspace', type=click.Path(exists=True), default='.',
              help='Workspace root directory')
@click.option('--output', type=click.Path(), default=None,
              help='Output file path (default: .quro_context/knowledge/panorama.json)')
@click.option('--force', is_flag=True, help='Force regeneration even if recent')
def generate(workspace: str, output: str, force: bool):
    """Generate or update panorama.json"""
    import datetime as dt

    project_root = Path(workspace).resolve()
    output_path = Path(output) if output else project_root / ".quro_context" / "panorama.json"

    click.echo(f"📊 Generating panorama for: {project_root}")

    # Check if recent panorama exists (unless --force)
    if not force and output_path.exists():
        try:
            mtime = output_path.stat().st_mtime
            age_seconds = dt.datetime.now().timestamp() - mtime
            if age_seconds < 3600:  # Less than 1 hour old
                click.echo(f"⚠️  Panorama is recent ({age_seconds/60:.0f} min old). Use --force to regenerate.")
                return
        except Exception:
            pass

    from quro_cli.panorama.builder import build_panorama_sync, load_symbols_pg
    import asyncio

    async def run_generate():
        symbols = await load_symbols_pg()
        panorama = build_panorama_sync(symbols, project_root)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write panorama
        with open(output_path, 'w') as f:
            json.dump(panorama, f, indent=2)

        click.echo(f"✅ Panorama saved to: {output_path}")
        meta = panorama.get('meta', {})
        click.echo(f"   Symbols: {meta.get('symbol_count', 0)}")
        click.echo(f"   Files: {meta.get('file_count', 0)}")
        click.echo(f"   Domains: {len(panorama.get('domains', []))}")
        click.echo(f"   Hubs: {len(panorama.get('hubs', []))}")

    asyncio.run(run_generate())


@panorama.command()
@click.option('--workspace', type=click.Path(exists=True), default='.',
              help='Workspace root directory')
def show(workspace: str):
    """Show current panorama summary"""
    project_root = Path(workspace).resolve()
    panorama_path = project_root / ".quro_context" / "panorama.json"

    if not panorama_path.exists():
        click.echo(f"❌ Panorama not found: {panorama_path}")
        click.echo("   Run 'quro panorama generate' first.")
        return

    with open(panorama_path, 'r') as f:
        panorama = json.load(f)

    click.echo(f"📊 Project Panorama")
    meta = panorama.get('meta', {})
    click.echo(f"   Schema: {panorama.get('$schema', 'unknown')}")
    click.echo(f"   Generated: {meta.get('generated_at', 'unknown')}")
    click.echo(f"   Symbols: {meta.get('symbol_count', 0)}")
    click.echo(f"   Files: {meta.get('file_count', 0)}")

    if 'domains' in panorama:
        click.echo(f"\n🏷️  Domains ({len(panorama['domains'])}):")
        for d in panorama['domains']:
            click.echo(f"   {d['id']}: anchor={d['anchor']}, members={d['member_count']}, risk={d['risk_level']}")

    if 'hubs' in panorama:
        click.echo(f"\n🔗 Hubs ({len(panorama['hubs'])}):")
        for h in panorama['hubs']:
            centrality = h.get('manifold_centrality', h.get('centrality', 0))
            domains = h.get('crosses_domains', h.get('domains', []))
            click.echo(f"   {h['symbol']}: centrality={centrality}, domains={domains}")

    if 'architecture_shape' in panorama:
        shape = panorama['architecture_shape']
        click.echo(f"\n🏛️  Architecture:")
        click.echo(f"   Topology: {shape.get('topology', 'unknown')}")
        click.echo(f"   Coupling Entropy: {shape.get('coupling_entropy', 0)}")

    if 'session_hint' in panorama:
        hint = panorama['session_hint']
        click.echo(f"\n💡 Session Hint:")
        click.echo(f"   Load Order: {hint.get('load_order', [])}")
        click.echo(f"   High Priority Fix: {hint.get('high_priority_fix', 'none')}")


@panorama.command()
@click.option('--workspace', type=click.Path(exists=True), default='.',
              help='Workspace root directory')
def stats(workspace: str):
    """Show detailed statistics"""
    import asyncio
    from quro_cli.panorama.builder import load_symbols_pg, build_panorama_sync

    project_root = Path(workspace).resolve()

    async def run_stats():
        symbols = await load_symbols_pg()
        panorama = build_panorama_sync(symbols, project_root)

        click.echo(f"📊 Detailed Statistics")
        click.echo(f"   Symbol Count: {panorama['symbol_count']}")
        click.echo(f"   File Count: {panorama['file_count']}")
        click.echo(f"   Domains: {len(panorama['domains'])}")
        click.echo(f"   Hubs: {len(panorama['hubs'])}")
        click.echo(f"   Topology: {panorama['architecture_shape']['topology']}")
        click.echo(f"   Coupling Entropy: {panorama['architecture_shape']['coupling_entropy']}")

    asyncio.run(run_stats())


@panorama.command()
@click.option('--workspace', type=click.Path(exists=True), default='.',
              help='Workspace root directory')
def health(workspace: str):
    """Show health metrics"""
    import asyncio
    from quro_cli.panorama.builder import load_symbols_pg, build_panorama_sync

    project_root = Path(workspace).resolve()

    async def run_health():
        symbols = await load_symbols_pg()
        panorama = build_panorama_sync(symbols, project_root)

        high_risk = [d for d in panorama['domains'] if d['risk_level'] == 'high']
        medium_risk = [d for d in panorama['domains'] if d['risk_level'] == 'medium']

        click.echo(f"🏥 Health Metrics")
        click.echo(f"   High Risk Domains: {len(high_risk)}")
        click.echo(f"   Medium Risk Domains: {len(medium_risk)}")
        click.echo(f"   Coupling Entropy: {panorama['architecture_shape']['coupling_entropy']}")
        if high_risk:
            click.echo(f"\n⚠️  High Risk:")
            for d in high_risk:
                click.echo(f"   {d['id']}: {', '.join(d['active_risks'])}")

    asyncio.run(run_health())


# Plugin metadata
METADATA = {
    "description": "Project panorama generation and querying",
    "commands": {
        "panorama generate": {
            "description": "Generate or update panorama.json",
            "usage": "quro panorama generate [--workspace PATH] [--output PATH] [--force]",
            "implementation": "quro_cli.commands.panorama_commands.generate"
        },
        "panorama show": {
            "description": "Show current panorama summary",
            "usage": "quro panorama show [--workspace PATH]",
            "implementation": "quro_cli.commands.panorama_commands.show"
        },
        "panorama stats": {
            "description": "Show detailed statistics",
            "usage": "quro panorama stats [--workspace PATH]",
            "implementation": "quro_cli.commands.panorama_commands.stats"
        },
        "panorama health": {
            "description": "Show health metrics",
            "usage": "quro panorama health [--workspace PATH]",
            "implementation": "quro_cli.commands.panorama_commands.health"
        }
    }
}


def register(cli: click.Group):
    """Register panorama commands with CLI"""
    cli.add_command(panorama)

"""
Quro CLI - Main entry point

Replaces node_server/cli/index.ts

Core Commands:
- scan: Scan workspace and index symbols
- chat: Interactive chat session
- mcp: Start MCP server (stdio mode)
- index: Rebuild semantic index

Plugin Commands (auto-discovered from quro_cli/commands/):
- mi-*: MI-path training system commands
- cqe-*: CQE query and analysis commands
- ai-kb-*: AI Knowledge Base management
- telemetry-*: Telemetry analysis commands
- (more plugins can be added without modifying this file)
"""

import click
import asyncio
import sys
import logging
from pathlib import Path

from quro_cli.config import QURO_DB_URL


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Quro CLI - Local Knowledge Base for AI Agents"""
    pass


# Discover and register plugins at module load time
from quro_cli.plugins import get_registry

_registry = get_registry()
_registry.discover_plugins()
_registry.register_all(cli)


@cli.command()
@click.option(
    "--workspace",
    type=click.Path(exists=True),
    default=".",
    help="Workspace root directory",
)
@click.option("--force", is_flag=True, help="Force rescan all files")
@click.option(
    "--files",
    type=str,
    default=None,
    help="Comma-separated list of files to scan (partial scan)",
)
@click.option(
    "--use-ai",
    is_flag=True,
    default=False,
    help="Enable AI-driven semantic analysis (Phase 2)",
)
def scan(workspace: str, force: bool, files: str, use_ai: bool):
    """Scan workspace and index symbols

    Phase 1 (scan): Always runs. Parse, tag, LSH fingerprint.
    Phase 2 (enrich): Runs only with --use-ai. AI-driven role/intent.

    Examples:
      quro scan                      # Incremental scan (skip scan_completed)
      quro scan --force              # Force rescan all files
      quro scan --files guard.ts     # Partial scan specific files
      quro scan --force --use-ai     # Full rescan + AI enrichment
    """
    workspace_path = Path(workspace).resolve()

    file_paths = None
    if files:
        file_paths = [f.strip() for f in files.split(",") if f.strip()]

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    async def run_scan():
        import asyncpg
        from quro_cli.scanner import WorkspaceScanner

        db_url = QURO_DB_URL
        db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)

        try:
            scanner = WorkspaceScanner(
                workspace_root=workspace_path,
                db_pool=db_pool,
                enable_v2_write=True,
                enable_semantic_analysis=use_ai,
            )
            await scanner.setup()

            click.echo(f"Scanning workspace: {workspace_path}", err=True)
            if file_paths:
                click.echo(f"  Target files: {file_paths}", err=True)
            if force:
                click.echo(f"  Mode: force", err=True)
            click.echo(
                f"  AI analysis: {'enabled' if use_ai else 'disabled'}", err=True
            )

            result = await scanner.scan(
                force=force,
                use_ai=use_ai,
                file_paths=file_paths,
            )

            if result["status"] != "success":
                click.echo(f"Scan failed: {result.get('error', 'unknown')}", err=True)
                sys.exit(1)

            click.echo(f"\nScan results:")
            click.echo(f"  Files scanned: {result['files_scanned']}")
            click.echo(f"  Symbols found: {result['symbols_found']}")
            click.echo(f"  Symbols skipped: {result.get('symbols_skipped', 0)}")
            click.echo(f"  Errors: {result.get('errors', 0)}")
            click.echo(f"  Duration: {result['duration_ms']}ms")

        finally:
            await scanner.cleanup()
            await db_pool.close()

    try:
        asyncio.run(run_scan())
        click.echo("Scan complete")
    except KeyboardInterrupt:
        click.echo("\nScan interrupted by user")
        sys.exit(1)
    except Exception as e:
        click.echo(f"\nScan failed: {e}", err=True)
        sys.exit(1)


@cli.command()
def chat():
    """Start interactive chat session"""
    click.echo("💬 Starting Quro chat...")
    click.echo("(Not yet implemented)")


@cli.command()
def mcp():
    """Start MCP server (stdio mode)"""
    click.echo("🚀 Starting MCP server...", err=True)

    # Import and run MCP server
    from quro_cli.mcp.server import main as mcp_server_main

    try:
        asyncio.run(mcp_server_main())
    except KeyboardInterrupt:
        click.echo("\n✓ MCP server stopped", err=True)
        sys.exit(0)


@cli.command()
@click.option("--rebuild", is_flag=True, help="Rebuild entire index")
def index(rebuild: bool):
    """Rebuild semantic index"""
    click.echo("📚 Indexing workspace...")

    if rebuild:
        click.echo("⚠️  Rebuilding entire index...")

    # TODO: Implement indexing logic
    click.echo("✓ Index complete (placeholder)")


@cli.command()
@click.option(
    "--workspace",
    type=click.Path(exists=True),
    default=".",
    help="Workspace root directory",
)
@click.option(
    "--files", type=str, default=None, help="Comma-separated list of files to enrich"
)
@click.option("--use-ai", is_flag=True, default=False, help="Enable AI enrichment")
def enrich(workspace: str, files: str, use_ai: bool):
    """AI enrichment — re-scan with AI-driven semantic analysis

    Re-runs scan with --use-ai to populate role/intent tags.

    Examples:
      quro enrich --use-ai                # Enrich all pending files
      quro enrich --files guard.ts --use-ai  # Enrich specific files
    """
    workspace_path = Path(workspace).resolve()

    file_paths = None
    if files:
        file_paths = [f.strip() for f in files.split(",") if f.strip()]

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    async def run_enrich():
        import asyncpg
        from quro_cli.scanner import WorkspaceScanner

        db_url = QURO_DB_URL
        db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)

        try:
            scanner = WorkspaceScanner(
                workspace_root=workspace_path,
                db_pool=db_pool,
                enable_v2_write=True,
                enable_semantic_analysis=True,
            )
            await scanner.setup()

            click.echo(f"Enriching workspace: {workspace_path}", err=True)
            if file_paths:
                click.echo(f"  Target files: {file_paths}", err=True)

            if not use_ai:
                click.echo(
                    "  Note: --use-ai not set, using heuristic analysis only", err=True
                )

            result = await scanner.scan(
                use_ai=use_ai,
                file_paths=file_paths,
            )

            click.echo(f"\nEnrich results:")
            click.echo(f"  Files scanned: {result['files_scanned']}")
            click.echo(f"  Symbols found: {result['symbols_found']}")
            click.echo(f"  Duration: {result['duration_ms']}ms")

        finally:
            await scanner.cleanup()
            await db_pool.close()

    try:
        asyncio.run(run_enrich())
        click.echo("Enrichment complete")
    except KeyboardInterrupt:
        click.echo("\nEnrichment interrupted by user")
        sys.exit(1)
    except Exception as e:
        click.echo(f"\nEnrichment failed: {e}", err=True)
        sys.exit(1)


@cli.command("deep-scan")
@click.option(
    "--workspace",
    type=click.Path(exists=True),
    default=".",
    help="Workspace root directory",
)
@click.option(
    "--file",
    type=str,
    default=None,
    help="Single file to audit (relative to workspace)",
)
@click.option(
    "--class",
    "class_name",
    type=str,
    default=None,
    help="Single class to audit (requires --file)",
)
def deep_scan(workspace: str, file: str, class_name: str):
    """DeepScanner — structural uncertainty audit

    Read-only AST-based diagnostics. No DB writes.
    Detects: unbound attributes, structural mismatches, deprecated references,
    dual-write patterns.

    Examples:
      quro deep-scan                      # Workspace-level audit
      quro deep-scan --file scanner.py     # Single-file audit
      quro deep-scan --file scanner.py --class WorkspaceScanner  # Single-class audit
    """
    workspace_path = Path(workspace).resolve()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    async def run():
        from quro_cli.scanner_deep.class_signature import extract_class_signature
        from quro_cli.scanner_deep.audit_rules import (
            check_unbound_attributes,
            check_dual_write_patterns,
        )

        # --- Mode: single class ---
        if file and class_name:
            abs_path = workspace_path / file
            if not abs_path.exists():
                click.echo(f"Error: file not found: {file}", err=True)
                sys.exit(1)

            source = abs_path.read_text(encoding="utf-8")
            sigs = extract_class_signature(source, file, class_name=class_name)

            if not sigs:
                click.echo(f"No class '{class_name}' found in {file}")
                sys.exit(0)

            sig = sigs[0]
            diags = check_unbound_attributes(file, source, sigs)

            click.echo(f"Class: {sig.class_name} ({file})")
            click.echo(f"  observation_scope: {sig.observation_scope}")
            click.echo(f"  explicit_attrs:   {list(sig.explicit_attrs) or '(none)'}")
            click.echo(f"  property_attrs:  {list(sig.property_attrs) or '(none)'}")
            click.echo(f"  method_names:    {list(sig.method_names) or '(none)'}")
            click.echo(f"  diagnostics:     {len(diags)}")

            if diags:
                for d in diags:
                    click.echo(f"    [{d['type']}] {d['class_name']}.{d['attribute']}")
            else:
                click.echo("    No unbound attributes detected.")
            return

        # --- Mode: single file ---
        if file:
            abs_path = workspace_path / file
            if not abs_path.exists():
                click.echo(f"Error: file not found: {file}", err=True)
                sys.exit(1)

            source = abs_path.read_text(encoding="utf-8")
            sigs = extract_class_signature(source, file)

            unbound = check_unbound_attributes(file, source, sigs)
            dual_write = check_dual_write_patterns(source, file)
            all_diags = unbound + dual_write

            click.echo(f"File: {file}")
            click.echo(f"  Classes:         {len(sigs)}")
            for sig in sigs:
                click.echo(
                    f"    {sig.class_name}: {len(sig.explicit_attrs)} attrs, {len(sig.method_names)} methods"
                )
            click.echo(f"  Diagnostics:     {len(all_diags)}")

            if all_diags:
                for d in all_diags:
                    if d["type"] == "UNBOUND_ATTRIBUTE_REFERENCE":
                        click.echo(f"    [UNBOUND] {d['class_name']}.{d['attribute']}")
                    elif d["type"] == "DUAL_WRITE_PATTERN":
                        click.echo(f"    [DUAL_WRITE] tables={d['tables']}")
            else:
                click.echo("    No diagnostics.")
            return

        # --- Mode: workspace scan ---
        import subprocess

        # Collect Python files via git ls-files
        result = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            click.echo("Error: not a git repository", err=True)
            sys.exit(1)

        py_files = [line.strip() for line in result.stdout.split("\n") if line.strip()]

        click.echo(f"DeepScanner workspace audit: {workspace_path}")
        click.echo(f"  Python files:    {len(py_files)}")

        total_classes = 0
        total_unbound = 0

        for rel_path in py_files:
            abs_path = workspace_path / rel_path
            if not abs_path.exists():
                continue

            try:
                source = abs_path.read_text(encoding="utf-8")
            except Exception:
                continue

            sigs = extract_class_signature(source, rel_path)
            if not sigs:
                continue

            diags = check_unbound_attributes(rel_path, source, sigs)

            total_classes += len(sigs)
            total_unbound += len(diags)

            if diags:
                for d in diags:
                    click.echo(
                        f"  [UNBOUND] {rel_path} — {d['class_name']}.{d['attribute']}"
                    )

        click.echo(f"\nSummary:")
        click.echo(f"  Classes scanned:  {total_classes}")
        click.echo(f"  Unbound attrs:    {total_unbound}")

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        click.echo("\nDeep scan interrupted")
    except Exception as e:
        click.echo(f"\nDeep scan failed: {e}", err=True)
        sys.exit(1)


def index_commands():
    """Generate command index for Claude (hidden command)"""
    from quro_cli.plugins import get_registry

    registry = get_registry()
    registry.discover_plugins()

    index_path = Path(".quro_context/command_index.md")
    registry.generate_index(index_path)

    click.echo(f"✅ Command index generated: {index_path}")


if __name__ == "__main__":
    cli()

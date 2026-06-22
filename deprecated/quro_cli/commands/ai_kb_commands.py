"""AI Knowledge Base CLI commands.

@module quro_cli.commands.ai_kb_commands
@intent Expose AI Knowledge Base compilation via Quro CLI.
"""
from pathlib import Path

import asyncio
import click

from quro_sovereign.ai_kb_compiler import compile_ai_knowledge_base


# Plugin metadata for discovery
METADATA = {
    "name": "ai-kb",
    "description": "AI Knowledge Base management commands",
    "commands": {
        "compile": "Compile AI Knowledge Base artifacts",
        "status": "Check status of AI Knowledge Base artifacts"
    }
}


def register(cli):
    """Register AI KB commands with the main CLI."""
    cli.add_command(ai_kb, name="ai-kb")


@click.group()
def ai_kb():
    """AI Knowledge Base management commands.

    Compile deterministic artifacts for AI consumption.
    CRITICAL: These artifacts are for AI to read, NOT for CQE to load.
    """
    pass


@ai_kb.command("compile")
@click.option(
    "--project-root",
    type=click.Path(exists=True, path_type=Path),
    default=Path.cwd(),
    help="Project root directory"
)
def compile_cmd(project_root: Path):
    """Compile AI Knowledge Base artifacts.

    Generates:
      - .quro_context/ai_kb/tool_catalog.json
      - .quro_context/ai_kb/failure_catalog.json

    These artifacts are for AI consumption only. CQE never loads them.
    """
    click.echo("\n🔨 Compiling AI Knowledge Base...\n")

    summary = asyncio.run(compile_ai_knowledge_base(project_root))

    click.echo("✅ Compilation Complete\n")
    click.echo(f"Tool Catalog:    {summary['tool_catalog']} ({summary['tool_count']} tools)")
    click.echo(f"Failure Catalog: {summary['failure_catalog']} ({summary['failure_count']} patterns)")
    click.echo(f"Output Dir:      {summary['output_dir']}")
    click.echo("\n📚 These artifacts are for AI consumption only. CQE never loads them.\n")


@ai_kb.command("status")
@click.option(
    "--project-root",
    type=click.Path(exists=True, path_type=Path),
    default=Path.cwd(),
    help="Project root directory"
)
def status_cmd(project_root: Path):
    """Check status of AI Knowledge Base artifacts.

    Reports which artifacts exist and their freshness.
    """
    import json
    from datetime import datetime, timezone

    ai_kb_dir = project_root / ".quro_context" / "ai_kb"

    click.echo("\n📊 AI Knowledge Base Status\n")

    artifacts = ["tool_catalog.json", "failure_catalog.json"]

    for artifact in artifacts:
        artifact_path = ai_kb_dir / artifact

        if artifact_path.exists():
            with artifact_path.open("r") as f:
                data = json.load(f)

            generated_at = data.get("generated_at", "unknown")
            click.echo(f"✅ {artifact}")
            click.echo(f"   Generated: {generated_at}")
            click.echo(f"   Version: {data.get('version', 'unknown')}")
        else:
            click.echo(f"❌ {artifact}")
            click.echo("   Not found. Run 'quro-cli ai-kb compile' to generate.")

    click.echo()

"""
Quro CLI - Agent Commands

@module quro_cli.commands.agent_commands
@intent CLI interface for quro_agent: run tasks, list tasks, check status.

Commands:
  quro agent run     - Submit and run a task
  quro agent list    - List all tasks
  quro agent status  - Check task status
"""

import asyncio
import json
import tempfile
from pathlib import Path

import click


@click.group()
def agent():
    """Quro Agent - Task execution with tool dispatch and pluggable backends"""
    pass


@agent.command()
@click.argument("goal")
@click.option("--generator", type=click.Choice(["ollama", "mlx"]), default="ollama",
              help="Generator backend (default: ollama)")
@click.option("--judge", type=click.Choice(["anthropic", "gemini", "local"]), default="anthropic",
              help="Judge backend (default: anthropic)")
@click.option("--tools", type=click.Choice(["all", "quro", "filesystem"]), default="all",
              help="Tool set to enable (default: all)")
@click.option("--workspace", type=click.Path(exists=True), default=".",
              help="Workspace root directory")
@click.option("--model", type=str, default=None,
              help="Override generator model")
@click.option("--dry-run", is_flag=True,
              help="Show config and tool count without executing")
@click.option("--db-url", type=str, default=None,
              help="PostgreSQL URL for Quro tools")
def run(goal: str, generator: str, judge: str, tools: str,
        workspace: str, model: str, dry_run: bool, db_url: str):
    """Run a task with the specified configuration."""
    try:
        from quro_agent.config import AgentConfig
        from quro_ftp.core.config import FTPConfig
        from quro_ftp.core.packet import TaskSpec
    except ImportError as exc:
        raise click.ClickException(
            f"Agent/FTP modules not available: {exc}. "
            "These are Track B (deferred) modules."
        ) from exc

    workspace_root = Path(workspace).resolve()

    # Build config
    ftp_config = FTPConfig(db_path=Path(tempfile.mktemp(suffix=".db")))
    overrides = {
        "ftp": ftp_config,
        "generator_backend": generator,
        "judge_backend": judge,
        "workspace_root": str(workspace_root),
    }

    if tools == "quro":
        overrides["filesystem_tools_enabled"] = False
        overrides["quro_tools_enabled"] = True
    elif tools == "filesystem":
        overrides["filesystem_tools_enabled"] = True
        overrides["quro_tools_enabled"] = False

    if model:
        if generator == "ollama":
            ftp_config_kwargs = dict(db_path=ftp_config.db_path, g_model=model)
            overrides["ftp"] = FTPConfig(**ftp_config_kwargs)
        else:
            overrides["mlx_model_path"] = model

    if db_url:
        overrides["db_url"] = db_url

    config = AgentConfig(**overrides)

    if dry_run:
        click.echo("=== Agent Dry Run ===")
        click.echo(f"Goal:       {goal}")
        click.echo(f"Generator:  {config.generator_backend}")
        click.echo(f"Judge:      {config.judge_backend}")
        click.echo(f"Workspace:  {config.workspace_root}")
        click.echo(f"FS Tools:   {'enabled' if config.filesystem_tools_enabled else 'disabled'}")
        click.echo(f"Quro Tools: {'enabled' if config.quro_tools_enabled else 'disabled'}")
        if model:
            click.echo(f"Model:      {model}")
        return

    # Initialize runtime and run
    from quro_agent.runtime import AgentRuntime

    async def _run():
        runtime = AgentRuntime(config)
        click.echo(f"Tools registered: {len(runtime.tool_registry.tool_names)}")
        click.echo(f"Submitting task: {goal}")
        task_id = await runtime.submit(TaskSpec(goal=goal))
        click.echo(f"Task ID: {task_id}")
        click.echo("Running...")
        result = await runtime.run(TaskSpec(goal=goal))
        click.echo(f"Result: {json.dumps(result, indent=2, default=str)}")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        click.echo("\nInterrupted.")


@agent.command()
@click.option("--limit", type=int, default=10, help="Max tasks to show (default: 10)")
@click.option("--state", type=str, default=None, help="Filter by FSM state")
@click.option("--workspace", type=click.Path(exists=True), default=".",
              help="Workspace root directory")
def list(limit: int, state: str, workspace: str):
    """List all tasks with their current state."""
    import sqlite3
    from pathlib import Path

    workspace_root = Path(workspace).resolve()
    db_path = workspace_root / ".quro_context" / "ftp.db"

    if not db_path.exists():
        click.echo("No FTP database found. Run a task first.")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    query = "SELECT task_id, fsm_state, audit_count, created_at FROM ftp_packet"
    params: list = []
    if state:
        query += " WHERE fsm_state = ?"
        params.append(state)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        click.echo("No tasks found.")
        return

    click.echo(f"{'Task ID':<12} {'State':<16} {'Audits':<8} {'Created'}")
    click.echo("-" * 60)
    for row in rows:
        click.echo(f"{row['task_id']:<12} {row['fsm_state']:<16} {row['audit_count']:<8} {row['created_at']}")


@agent.command()
@click.argument("task_id")
@click.option("--workspace", type=click.Path(exists=True), default=".",
              help="Workspace root directory")
def status(task_id: str, workspace: str):
    """Show detailed status of a task."""
    import sqlite3
    from pathlib import Path

    workspace_root = Path(workspace).resolve()
    db_path = workspace_root / ".quro_context" / "ftp.db"

    if not db_path.exists():
        click.echo("No FTP database found.")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT * FROM ftp_packet WHERE task_id = ?", (task_id,)
    ).fetchone()
    conn.close()

    if not row:
        click.echo(f"Task '{task_id}' not found.")
        return

    click.echo(f"Task:     {row['task_id']}")
    click.echo(f"State:    {row['fsm_state']}")
    click.echo(f"Level:    {row['level']}")
    click.echo(f"Audits:   {row['audit_count']}")
    click.echo(f"Version:  {row['version']}")
    click.echo(f"Created:  {row['created_at']}")
    if row['spec_json']:
        spec = json.loads(row['spec_json'])
        click.echo(f"Goal:     {spec.get('goal', 'N/A')}")
        click.echo(f"Domain:   {spec.get('domain', 'N/A')}")


# Plugin metadata
METADATA = {
    "description": "Quro Agent - Task execution with tool dispatch",
    "commands": {
        "agent run": {
            "description": "Run a task with specified configuration",
            "usage": "quro agent run GOAL [--generator ollama|mlx] [--judge anthropic|gemini|local]",
            "implementation": "quro_cli.commands.agent_commands.run"
        },
        "agent list": {
            "description": "List all tasks with current state",
            "usage": "quro agent list [--limit N] [--state STATE]",
            "implementation": "quro_cli.commands.agent_commands.list"
        },
        "agent status": {
            "description": "Show detailed task status",
            "usage": "quro agent status TASK_ID",
            "implementation": "quro_cli.commands.agent_commands.status"
        },
    }
}


def register(cli: click.Group):
    """Register agent commands with CLI."""
    cli.add_command(agent)

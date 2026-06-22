"""Telemetry analysis CLI commands.

@module quro_cli.commands.telemetry_commands
@intent Expose telemetry analysis via Quro CLI.
"""
from pathlib import Path
import sys

import click

# Add scripts directory to path for import
scripts_dir = Path(__file__).parent / "scripts"
if scripts_dir not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from quro_cli.scripts.analyze_telemetry import generate_report


# Plugin metadata for discovery
METADATA = {
    "name": "telemetry",
    "description": "Telemetry analysis commands",
    "commands": {
        "analyze": "Analyze CQE telemetry logs",
        "status": "Check telemetry data availability"
    }
}


def register(cli):
    """Register telemetry commands with the main CLI."""
    cli.add_command(telemetry, name="telemetry")


@click.group()
def telemetry():
    """Telemetry analysis commands.

    Generate descriptive statistics from CQE telemetry logs.
    CRITICAL: Analysis is strictly descriptive. NO recommendations or guidance.
    """
    pass


@telemetry.command("analyze")
@click.option(
    "--project-root",
    type=click.Path(exists=True, path_type=Path),
    default=Path.cwd(),
    help="Project root directory"
)
def analyze_cmd(project_root: Path):
    """Analyze CQE telemetry logs.

    Generates descriptive statistics:
      - Per-pattern query counts
      - Average MI scores
      - Decision distributions

    Output: .quro_context/reports/telemetry_stats.json

    This analysis is DESCRIPTIVE ONLY. No recommendations or guidance provided.
    AI interprets the data. CQE never sees this report.
    """
    click.echo("\n📊 Analyzing Telemetry Logs...\n")

    output_path = generate_report(project_root)

    import json
    stats = json.loads(output_path.read_text())

    click.echo("✅ Telemetry Statistics Generated\n")
    click.echo(f"Output:     {output_path}")
    click.echo(f"Records:    {stats['total_records']}")
    click.echo(f"Patterns:   {stats['pattern_count']}\n")

    if stats['pattern_count'] > 0:
        click.echo("Top 5 Patterns by Count:")
        sorted_patterns = sorted(
            stats['patterns'].items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        for i, (pattern, data) in enumerate(sorted_patterns[:5], 1):
            click.echo(f"  {i}. {pattern}")
            click.echo(f"     count={data['count']}, avg_mi={data['avg_mi']:.3f}")

    click.echo("\n⚠️  This report is DESCRIPTIVE ONLY.")
    click.echo("    No recommendations or guidance provided.")
    click.echo("    AI interprets this data. CQE never sees it.\n")


@telemetry.command("status")
@click.option(
    "--project-root",
    type=click.Path(exists=True, path_type=Path),
    default=Path.cwd(),
    help="Project root directory"
)
def status_cmd(project_root: Path):
    """Check telemetry data availability.

    Reports on telemetry log existence and size.
    """
    import json

    telemetry_path = project_root / ".quro_context" / "cqe_telemetry.jsonl"
    report_path = project_root / ".quro_context" / "reports" / "telemetry_stats.json"

    click.echo("\n📊 Telemetry Status\n")

    # Telemetry log
    if telemetry_path.exists():
        size_kb = telemetry_path.stat().st_size / 1024
        record_count = sum(1 for _ in telemetry_path.open("r"))
        click.echo(f"✅ Telemetry Log: {telemetry_path}")
        click.echo(f"   Size: {size_kb:.1f} KB")
        click.echo(f"   Records: {record_count}")
    else:
        click.echo(f"❌ Telemetry Log: {telemetry_path}")
        click.echo("   Not found. Run some CQE queries to generate telemetry.")

    click.echo()

    # Analysis report
    if report_path.exists():
        with report_path.open("r") as f:
            stats = json.load(f)
        click.echo(f"✅ Analysis Report: {report_path}")
        click.echo(f"   Generated: {stats.get('version', 'unknown')}")
        click.echo(f"   Patterns: {stats.get('pattern_count', 0)}")
    else:
        click.echo(f"❌ Analysis Report: {report_path}")
        click.echo("   Not found. Run 'quro-cli telemetry analyze' to generate.")

    click.echo()

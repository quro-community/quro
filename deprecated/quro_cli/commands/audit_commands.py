"""
Audit Commands - CLI plugin for data quality auditing

@module quro_cli.commands.audit_commands
@intent Provide CLI commands for database and CQE index quality auditing

Commands:
  - audit-db: Audit PostgreSQL database quality
  - audit-cqe: Audit CQE index quality
  - audit-all: Run all audits
"""

import click
import asyncio
from pathlib import Path


# Plugin metadata for command indexing
METADATA = {
    'description': 'Data Quality Auditing - Database and CQE index quality checks',
    'commands': {
        'audit-db': {
            'description': 'Audit PostgreSQL database quality',
            'usage': 'quro audit-db [--db-url postgresql://localhost/quro_db]',
            'implementation': 'quro_cli/commands/audit_commands.py:audit_db'
        },
        'audit-cqe': {
            'description': 'Audit CQE index quality',
            'usage': 'quro audit-cqe [--index-path .quro_context/cqe_index.db]',
            'implementation': 'quro_cli/commands/audit_commands.py:audit_cqe'
        },
        'audit-all': {
            'description': 'Run all quality audits',
            'usage': 'quro audit-all',
            'implementation': 'quro_cli/commands/audit_commands.py:audit_all'
        }
    }
}


def register(cli: click.Group):
    """Register audit commands with CLI"""
    cli.add_command(audit_db)
    cli.add_command(audit_cqe)
    cli.add_command(audit_all)


@click.command('audit-db')
@click.option('--db-url', default='postgresql://localhost/quro_db',
              help='PostgreSQL database URL')
@click.option('--output', type=click.Path(),
              default='.quro_context/audit/data_quality_report.json',
              help='Output file for report')
def audit_db(db_url: str, output: str):
    """Audit PostgreSQL database quality"""
    from quro_cli.audit.data_quality import DatabaseQualityAuditor

    output_path = Path(output)

    click.echo("🔍 Database Quality Audit")
    click.echo("="*60)

    async def run_audit():
        auditor = DatabaseQualityAuditor(db_url)
        try:
            report = await auditor.audit()
            auditor.print_report(report)
            await auditor.save_report(report, output_path)
            return report
        finally:
            await auditor.cleanup()

    try:
        report = asyncio.run(run_audit())

        click.echo(f"\n✅ Audit complete!")
        click.echo(f"📄 Report saved to: {output_path}")
        click.echo(f"🎯 Quality Grade: {report.quality_grade}")

        if not report.ready_for_mi_estimator:
            click.echo("\n⚠️  Database not ready for MI Estimator")
            click.echo("Issues:")
            for issue in report.issues:
                click.echo(f"  - {issue}")

    except Exception as e:
        click.echo(f"\n❌ Audit failed: {e}", err=True)
        raise


@click.command('audit-cqe')
@click.option('--index-path', type=click.Path(exists=True),
              default='.quro_context/cqe_index.db',
              help='CQE index database path')
@click.option('--output', type=click.Path(),
              default='.quro_context/audit/cqe_quality_report.json',
              help='Output file for report')
def audit_cqe(index_path: str, output: str):
    """Audit CQE index quality"""
    from quro_cli.audit.cqe_quality import CQEQualityAuditor

    index_path = Path(index_path)
    output_path = Path(output)

    click.echo("🔍 CQE Index Quality Audit")
    click.echo("="*60)

    if not index_path.exists():
        click.echo(f"\n❌ CQE index not found: {index_path}", err=True)
        click.echo("Run 'quro cqe-build' first to create the index.")
        return

    auditor = CQEQualityAuditor(index_path)
    try:
        report = auditor.audit()
        auditor.print_report(report)
        auditor.save_report(report, output_path)

        click.echo(f"\n✅ Audit complete!")
        click.echo(f"📄 Report saved to: {output_path}")
        click.echo(f"🎯 Quality Grade: {report.quality_grade}")

        if report.quality_grade in ('D', 'F'):
            click.echo("\n⚠️  CQE index quality issues detected")
            click.echo("Issues:")
            for issue in report.issues:
                click.echo(f"  - {issue}")

    except Exception as e:
        click.echo(f"\n❌ Audit failed: {e}", err=True)
        raise
    finally:
        auditor.cleanup()


@click.command('audit-all')
@click.option('--db-url', default='postgresql://localhost/quro_db',
              help='PostgreSQL database URL')
@click.option('--index-path', type=click.Path(exists=True),
              default='.quro_context/cqe_index.db',
              help='CQE index database path')
def audit_all(db_url: str, index_path: str):
    """Run all quality audits"""
    click.echo("🔍 Running All Quality Audits")
    click.echo("="*60)

    # Run database audit
    click.echo("\n1️⃣  Database Quality Audit")
    click.echo("-"*60)
    ctx = click.get_current_context()
    ctx.invoke(audit_db, db_url=db_url,
               output='.quro_context/audit/data_quality_report.json')

    # Run CQE audit
    click.echo("\n2️⃣  CQE Index Quality Audit")
    click.echo("-"*60)
    ctx.invoke(audit_cqe, index_path=index_path,
               output='.quro_context/audit/cqe_quality_report.json')

    click.echo("\n✅ All audits complete!")
    click.echo("📁 Reports saved to: .quro_context/audit/")

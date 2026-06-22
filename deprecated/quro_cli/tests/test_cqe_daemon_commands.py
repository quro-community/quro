"""Tests for CQE Daemon CLI commands.

@module quro_cli.tests.test_cqe_daemon_commands
@intent Verify CLI command registration and argument handling.
"""
from click.testing import CliRunner
from quro_cli.commands.cqe_daemon_commands import cqe_daemon_group


class TestCompileCommand:
    """CQE daemon compile CLI command tests."""

    def test_compile_help(self) -> None:
        """compile command has help text."""
        runner = CliRunner()
        result = runner.invoke(cqe_daemon_group, ["compile", "--help"])
        assert result.exit_code == 0
        assert "Compile CQE index" in result.output
        assert "--index-path" in result.output
        assert "--output" in result.output

    def test_compile_missing_index(self) -> None:
        """compile handles missing index gracefully."""
        runner = CliRunner()
        result = runner.invoke(
            cqe_daemon_group,
            ["compile", "--index-path", "/nonexistent.db"],
        )
        assert result.exit_code == 1
        assert "Index not found" in result.output

    def test_compile_defaults(self) -> None:
        """compile command has index-path and output options."""
        runner = CliRunner()
        result = runner.invoke(cqe_daemon_group, ["compile", "--help"])
        assert result.exit_code == 0
        assert "--index-path" in result.output
        assert "--output" in result.output
        assert "--project-root" in result.output

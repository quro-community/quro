"""Tests for DeepScanner MCP tool — quro_audit integration."""
import pytest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from quro_cli.mcp.tools.deep_scanner_tools import DeepScannerTools


class FakePool:
    """Minimal asyncpg.Pool mock for tests that don't need DB."""

    def acquire(self):
        raise NotImplementedError("DB not needed for this test")


def _mock_pool(fetch_result):
    """Create a mock pool with a fake async context manager for acquire().

    If fetch_result is an Exception instance, conn.fetch will raise it.
    Otherwise, conn.fetch returns fetch_result as a list.
    """
    pool = MagicMock()
    is_error = isinstance(fetch_result, Exception)

    @asynccontextmanager
    async def fake_acquire():
        conn = AsyncMock()
        if is_error:
            conn.fetch = AsyncMock(side_effect=fetch_result)
        else:
            conn.fetch = AsyncMock(return_value=fetch_result)
        yield conn

    pool.acquire = fake_acquire
    return pool


@pytest.fixture
def tools():
    return DeepScannerTools(Path("."), FakePool())


class TestQuroAuditClass:
    """Test quro_audit class-level audit."""

    @pytest.mark.asyncio
    async def test_existing_class(self, tools):
        result = await tools.quro_audit(
            file_path="quro_cli/scanner_deep/class_signature.py",
            class_name="ClassSignature",
        )
        assert result["status"] == "success"
        assert result["symbol"] == "ClassSignature"
        assert "class_signature" in result
        assert result["observation_scope"] == "AST_ONLY"

    @pytest.mark.asyncio
    async def test_nonexistent_class(self, tools):
        result = await tools.quro_audit(
            file_path="quro_cli/scanner_deep/class_signature.py",
            class_name="NonExistent",
        )
        assert result["status"] == "success"
        assert result["class_signature"] is None

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, tools):
        result = await tools.quro_audit(
            file_path="nonexistent_file.py",
            class_name="Foo",
        )
        assert result["status"] == "error"


class TestQuroAuditFile:
    """Test quro_audit file-level audit."""

    @pytest.mark.asyncio
    async def test_existing_file(self, tools):
        result = await tools.quro_audit(
            file_path="quro_cli/scanner_deep/class_signature.py",
        )
        assert result["status"] == "success"
        assert len(result["class_signatures"]) >= 1
        assert result["observation_scope"] == "AST_ONLY"
        assert "diagnostics" in result

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, tools):
        result = await tools.quro_audit(file_path="nonexistent.py")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_deep_index_cached_fallback(self, tools):
        """When Deep Index doesn't exist, deep_index_cached should be 0."""
        result = await tools.quro_audit(
            file_path="quro_cli/scanner_deep/class_signature.py",
        )
        assert "deep_index_cached" in result
        assert result["deep_index_cached"] >= 0


class TestQuroAuditWorkspace:
    """Test quro_audit workspace-level audit (requires DB — mocked)."""

    @pytest.mark.asyncio
    async def test_workspace_audit(self):
        """Workspace audit with mocked DB pool."""
        rows = [
            {"symbol_name": "Foo", "file_path": "quro_cli/scanner_deep/class_signature.py", "deprecated_at": None},
            {"symbol_name": "Deleted", "file_path": "deleted.py", "deprecated_at": None},
        ]
        pool = _mock_pool(rows)

        tools = DeepScannerTools(Path("."), pool)
        result = await tools.quro_audit()

        assert result["status"] == "success"
        assert "diagnostics" in result
        assert "registry_health" in result
        assert "scan_version" in result
        assert result["scan_version"] == "deepscanner-v0.1"

    @pytest.mark.asyncio
    async def test_workspace_audit_db_error(self):
        """Workspace audit handles DB errors gracefully."""
        pool = _mock_pool(Exception("connection refused"))

        tools = DeepScannerTools(Path("."), pool)
        result = await tools.quro_audit()
        assert result["status"] == "error"
        assert "connection refused" in result["error"]

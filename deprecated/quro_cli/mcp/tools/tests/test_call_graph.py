"""Tests for CallGraphTools — call_graph MCP tool."""
import pytest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from quro_cli.mcp.tools.call_graph_tools import CallGraphTools


class FakePool:
    """Minimal asyncpg.Pool mock — raises if acquire() is called."""

    def acquire(self):
        raise NotImplementedError("DB not needed for this test")


def _mock_pool(fetch_results: dict):
    """Create a mock pool with routed fetch/fetchrow results.

    Keys: 'symbol_lookup', 'morphism_type', 'edges'.
    Values: lists of dicts (fetch) or single dict (fetchrow returns first).
    """
    pool = MagicMock()

    @asynccontextmanager
    async def fake_acquire():
        conn = AsyncMock()

        async def mock_fetch(query, *args):
            if "SELECT s.id, s.symbol_name" in query:
                return fetch_results.get("symbol_lookup", [])
            if "morphism_types" in query:
                return fetch_results.get("morphism_type", [])
            if "morphism_edges" in query:
                return fetch_results.get("edges", [])
            return []

        async def mock_fetchrow(query, *args):
            if "SELECT s.id, s.symbol_name" in query:
                rows = fetch_results.get("symbol_lookup", [])
                return rows[0] if rows else None
            if "morphism_types" in query:
                rows = fetch_results.get("morphism_type", [])
                return rows[0] if rows else None
            return None

        conn.fetch = mock_fetch
        conn.fetchrow = mock_fetchrow
        yield conn

    pool.acquire = fake_acquire
    return pool


@pytest.fixture
def tools():
    return CallGraphTools(Path("."), FakePool())


class TestCallGraphSymbolNotFound:

    @pytest.mark.asyncio
    async def test_symbol_not_found(self, tools):
        pool = _mock_pool({
            "symbol_lookup": [],
            "morphism_type": [{"id": 1}],
            "edges": [],
        })
        tools.db_pool = pool

        result = await tools.call_graph("NonexistentSymbol")
        assert result["status"] == "not_found"
        assert "NonexistentSymbol" in result["error"]


class TestCallGraphNoEdges:

    @pytest.mark.asyncio
    async def test_no_edges(self, tools):
        pool = _mock_pool({
            "symbol_lookup": [{"id": 10, "symbol_name": "IsolatedFunc"}],
            "morphism_type": [{"id": 1}],
            "edges": [],
        })
        tools.db_pool = pool

        result = await tools.call_graph("IsolatedFunc")
        assert result["status"] == "success"
        assert result["symbol"] == "IsolatedFunc"
        assert result["calls"] == []
        assert result["called_by"] == []
        assert result["edges"] == []


class TestCallGraphOutgoingEdges:

    @pytest.mark.asyncio
    async def test_outgoing_calls(self, tools):
        now = datetime.now(timezone.utc)
        pool = _mock_pool({
            "symbol_lookup": [{"id": 10, "symbol_name": "LlmGuard"}],
            "morphism_type": [{"id": 1}],
            "edges": [
                {
                    "from_symbol_id": 10,
                    "to_symbol_id": 20,
                    "from_name": "LlmGuard",
                    "from_file": "quro_cli/scanner.py",
                    "to_name": "acquire",
                    "to_file": "quro_cli/lock.py",
                    "weight": 0.9,
                    "updated_at": now,
                },
                {
                    "from_symbol_id": 10,
                    "to_symbol_id": 30,
                    "from_name": "LlmGuard",
                    "from_file": "quro_cli/scanner.py",
                    "to_name": "release",
                    "to_file": "quro_cli/lock.py",
                    "weight": 0.9,
                    "updated_at": now,
                },
            ],
        })
        tools.db_pool = pool

        result = await tools.call_graph("LlmGuard")
        assert result["status"] == "success"
        assert set(result["calls"]) == {"acquire", "release"}
        assert len(result["edges"]) == 2


class TestCallGraphIncomingEdges:

    @pytest.mark.asyncio
    async def test_incoming_calls(self, tools):
        now = datetime.now(timezone.utc)
        pool = _mock_pool({
            "symbol_lookup": [{"id": 20, "symbol_name": "acquire"}],
            "morphism_type": [{"id": 1}],
            "edges": [
                {
                    "from_symbol_id": 10,
                    "to_symbol_id": 20,
                    "from_name": "LlmGuard",
                    "from_file": "quro_cli/scanner.py",
                    "to_name": "acquire",
                    "to_file": "quro_cli/lock.py",
                    "weight": 0.9,
                    "updated_at": now,
                },
                {
                    "from_symbol_id": 40,
                    "to_symbol_id": 20,
                    "from_name": "guard_wrapper",
                    "from_file": "quro_cli/wrapper.py",
                    "to_name": "acquire",
                    "to_file": "quro_cli/lock.py",
                    "weight": 0.7,
                    "updated_at": now,
                },
            ],
        })
        tools.db_pool = pool

        result = await tools.call_graph("acquire")
        assert result["status"] == "success"
        assert "LlmGuard" in result["called_by"]
        assert "guard_wrapper" in result["called_by"]


class TestCallGraphDepth:

    @pytest.mark.asyncio
    async def test_depth_1_limits_traversal(self, tools):
        fetch_count = 0
        pool = MagicMock()

        @asynccontextmanager
        async def fake_acquire():
            nonlocal fetch_count
            conn = AsyncMock()

            async def mock_fetchrow(query, *args):
                if "SELECT s.id" in query and "symbol_name" in query:
                    return {"id": 10, "symbol_name": "A"}
                if "morphism_types" in query:
                    return {"id": 1}
                return None

            async def mock_fetch(query, *args):
                nonlocal fetch_count
                fetch_count += 1
                return [
                    {
                        "from_symbol_id": 10,
                        "to_symbol_id": 20,
                        "from_name": "A",
                        "from_file": "a.py",
                        "to_name": "B",
                        "to_file": "b.py",
                        "weight": 0.9,
                        "updated_at": datetime.now(timezone.utc),
                    },
                ]

            conn.fetchrow = mock_fetchrow
            conn.fetch = mock_fetch
            yield conn

        pool.acquire = fake_acquire
        tools.db_pool = pool

        result = await tools.call_graph("A", depth=1)
        assert result["status"] == "success"
        # depth=1: one fetch for edges of A, no further expansion
        assert fetch_count == 1


class TestCallGraphDeprecatedExcluded:

    @pytest.mark.asyncio
    async def test_deprecated_filtered(self, tools):
        pool = _mock_pool({
            "symbol_lookup": [{"id": 10, "symbol_name": "ActiveFunc"}],
            "morphism_type": [{"id": 1}],
            "edges": [],
        })
        tools.db_pool = pool

        result = await tools.call_graph("ActiveFunc")
        assert result["calls"] == []
        assert result["called_by"] == []


class TestCallGraphNoDBPool:

    @pytest.mark.asyncio
    async def test_no_pool(self):
        tools = CallGraphTools(Path("."), db_pool=None)
        result = await tools.call_graph("anything")
        assert result["status"] == "error"
        assert "Database connection" in result["error"]


class TestCallGraphMorphismTypeMissing:

    @pytest.mark.asyncio
    async def test_no_calls_type(self, tools):
        pool = _mock_pool({
            "symbol_lookup": [{"id": 10, "symbol_name": "A"}],
            "morphism_type": [],
            "edges": [],
        })
        tools.db_pool = pool

        result = await tools.call_graph("A")
        assert result["status"] == "error"
        assert "CALLS" in result["error"]


class TestCallGraphDepthClamping:

    @pytest.mark.asyncio
    async def test_depth_zero_clamped_to_one(self, tools):
        pool = _mock_pool({
            "symbol_lookup": [{"id": 10, "symbol_name": "A"}],
            "morphism_type": [{"id": 1}],
            "edges": [],
        })
        tools.db_pool = pool

        result = await tools.call_graph("A", depth=0)
        assert result["status"] == "success"
        assert result["depth"] == 1

    @pytest.mark.asyncio
    async def test_depth_excessive_clamped_to_ten(self, tools):
        pool = _mock_pool({
            "symbol_lookup": [{"id": 10, "symbol_name": "A"}],
            "morphism_type": [{"id": 1}],
            "edges": [],
        })
        tools.db_pool = pool

        result = await tools.call_graph("A", depth=999)
        assert result["status"] == "success"
        assert result["depth"] == 10

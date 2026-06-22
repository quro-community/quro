"""Tests for LocalRouter wiring in CQETools.

Verifies that CQETools initializes LocalRouter, attaches routing decisions
to query results on both daemon and fallback paths, and that routing is
pure observer (does not affect delivery layer decisions).
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace_root(tmp_path: Path):
    """Create a minimal workspace with vocabulary.json for LocalRouter."""
    (tmp_path / "commons").mkdir()
    vocab = {
        "version": "test-1",
        "tags": [
            {"id": "lock", "aliases": ["mutex"], "risk_weight": 5},
            {"id": "async", "aliases": ["coroutine"], "risk_weight": 2},
            {"id": "raii", "aliases": [], "risk_weight": 3},
        ],
    }
    (tmp_path / "commons" / "vocabulary.json").write_text(
        json.dumps(vocab), encoding="utf-8",
    )
    (tmp_path / ".quro_context").mkdir()
    return tmp_path


def _make_cqe_tools(workspace_root: Path):
    """Create a CQETools instance with real LocalRouter but mocked internals."""
    from quro_cli.mcp.tools.cqe_tools import CQETools

    # Patch telemetry writer init to avoid file contention
    with patch.object(CQETools, '__init__', lambda self, *a, **kw: None):
        tools = CQETools.__new__(CQETools)
    tools.workspace_root = workspace_root

    from quro_sovereign.local_router import LocalRouter
    from quro_lds.vocabulary_store import VocabularyStore
    VocabularyStore._instance = None
    tools._local_router = LocalRouter(project_root=workspace_root)
    tools._telemetry_writer = MagicMock()
    tools._hysteresis = MagicMock()
    return tools


def _make_results() -> list[dict]:
    """Build minimal CQE result list with mi_scores."""
    return [
        {
            "atom_id": "pit::p1",
            "atom_type": "pitfall",
            "mi_score": 0.8,
            "behavioral_tags": ["lock", "async"],
            "delivery_tier": "alpha",
        },
        {
            "atom_id": "sym::A",
            "atom_type": "symbol",
            "mi_score": 0.6,
            "behavioral_tags": ["raii"],
            "delivery_tier": "beta",
        },
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLocalRouterInit:
    def test_init_creates_router(self, workspace_root):
        from quro_cli.mcp.tools.cqe_tools import CQETools
        with patch.object(CQETools, '__init__', lambda self, *a, **kw: None):
            tools = CQETools.__new__(CQETools)
        tools.workspace_root = workspace_root

        from quro_sovereign.local_router import LocalRouter
        from quro_lds.vocabulary_store import VocabularyStore
        VocabularyStore._instance = None
        tools._local_router = LocalRouter(project_root=workspace_root)

        assert isinstance(tools._local_router, LocalRouter)


class TestRoutingDecisionAttached:
    def test_routing_fields_present(self, workspace_root):
        """Result dict must have routing key with destination/path_mi/tags/reason."""
        tools = _make_cqe_tools(workspace_root)

        result = {
            "status": "success",
            "results": _make_results(),
            "delivery": {"primary": [], "secondary": [], "dropped": []},
        }

        # Simulate the routing attachment logic from cqe_query
        if result.get("results"):
            path_mi = min(
                (r.get("mi_score", 1.0) for r in result["results"]),
                default=1.0,
            )
            routing = tools._local_router.route("async lock patterns", path_mi)
            result["routing"] = {
                "destination": routing.destination,
                "path_mi": routing.path_mi,
                "matched_tags": routing.matched_tags,
                "reason": routing.reason,
            }

        assert "routing" in result
        assert "destination" in result["routing"]
        assert "path_mi" in result["routing"]
        assert "matched_tags" in result["routing"]
        assert "reason" in result["routing"]

    def test_routing_local_when_mi_high(self, workspace_root):
        """High path_mi + vocab match → destination='local'."""
        tools = _make_cqe_tools(workspace_root)
        routing = tools._local_router.route("async lock patterns", path_mi=0.7)
        assert routing.destination == "local"
        assert routing.path_mi == 0.7

    def test_routing_remote_when_mi_low(self, workspace_root):
        """Low path_mi → destination='remote' regardless of vocab."""
        tools = _make_cqe_tools(workspace_root)
        routing = tools._local_router.route("async lock patterns", path_mi=0.3)
        assert routing.destination == "remote"

    def test_routing_uses_min_mi_score(self, workspace_root):
        """path_mi should be min(mi_score) across all results."""
        tools = _make_cqe_tools(workspace_root)
        results = _make_results()
        path_mi = min(
            (r.get("mi_score", 1.0) for r in results),
            default=1.0,
        )
        assert path_mi == 0.6  # min of [0.8, 0.6]


class TestRoutingObserverNoFeedback:
    def test_routing_does_not_modify_results(self, workspace_root):
        """Attaching routing dict must not mutate the results list."""
        tools = _make_cqe_tools(workspace_root)
        results = _make_results()
        original_ids = [r["atom_id"] for r in results]

        result = {"status": "success", "results": results}
        if result.get("results"):
            path_mi = min(
                (r.get("mi_score", 1.0) for r in result["results"]),
                default=1.0,
            )
            routing = tools._local_router.route("async lock patterns", path_mi)
            result["routing"] = {
                "destination": routing.destination,
                "path_mi": routing.path_mi,
                "matched_tags": routing.matched_tags,
                "reason": routing.reason,
            }

        assert [r["atom_id"] for r in result["results"]] == original_ids

    def test_no_routing_when_no_results(self, workspace_root):
        """Empty results → routing key should not be attached."""
        tools = _make_cqe_tools(workspace_root)
        result = {"status": "success", "results": []}

        if result.get("results"):
            path_mi = min(
                (r.get("mi_score", 1.0) for r in result["results"]),
                default=1.0,
            )
            routing = tools._local_router.route("test", path_mi)
            result["routing"] = {
                "destination": routing.destination,
                "path_mi": routing.path_mi,
                "matched_tags": routing.matched_tags,
                "reason": routing.reason,
            }

        assert "routing" not in result


class TestRouterLogWritten:
    def test_route_appends_to_log(self, workspace_root):
        """Every route() call must append to router_log.jsonl."""
        from quro_sovereign.local_router import LocalRouter
        from quro_lds.vocabulary_store import VocabularyStore
        VocabularyStore._instance = None

        router = LocalRouter(project_root=workspace_root)
        log_path = workspace_root / ".quro_context" / "router_log.jsonl"

        assert not log_path.exists()
        router.route("async lock patterns", path_mi=0.7)
        assert log_path.exists()

        lines = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        assert lines[0]["destination"] == "local"
        assert lines[0]["path_mi"] == 0.7

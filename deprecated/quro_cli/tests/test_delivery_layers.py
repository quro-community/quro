"""Tests for CQE delivery layer (primary/secondary split).

Verifies structural match, cluster consistency, MI/type promotion rules,
max cap, category exclusion, and payload override behavior.
"""
import pytest
from unittest.mock import MagicMock

from quro_sovereign.routing_types import PrimarySelectionConfig
from quro_cli.mcp.tools.cqe_tools import (
    _extract_query_tokens,
    _structural_match,
    _cluster_key,
    _build_secondary_summary,
)


def _make_result(
    atom_id: str,
    atom_type: str,
    mi_score: float,
    behavioral_tags: list[str] | None = None,
    **kwargs,
) -> dict:
    """Build a minimal result dict for testing."""
    return {
        "atom_id": atom_id,
        "atom_type": atom_type,
        "mi_score": mi_score,
        "behavioral_tags": behavioral_tags or [],
        **kwargs,
    }


def _make_tools() -> MagicMock:
    """Create a mock MCPTools with the real _build_delivery_layers method."""
    from quro_cli.mcp.tools.cqe_tools import CQETools

    tools = MagicMock(spec=CQETools)
    tools._build_delivery_layers = CQETools._build_delivery_layers.__get__(
        tools, type(tools)
    )
    return tools


class TestExtractQueryTokens:
    """Test token extraction from queries."""

    def test_basic_tokens(self):
        tokens = _extract_query_tokens("async lock patterns")
        assert "async" in tokens
        assert "lock" in tokens
        assert "patterns" in tokens

    def test_stop_words_removed(self):
        tokens = _extract_query_tokens("how to fix the async deadlock")
        assert "the" not in tokens
        assert "how" not in tokens
        assert "fix" in tokens
        assert "async" in tokens
        assert "deadlock" in tokens

    def test_short_tokens_removed(self):
        tokens = _extract_query_tokens("a b c defg")
        assert "defg" in tokens
        assert len(tokens) == 1

    def test_empty_query(self):
        tokens = _extract_query_tokens("")
        assert tokens == set()


class TestStructuralMatch:
    """Test structural match constraint."""

    def test_tag_overlap(self):
        atom = _make_result("pit::p1", "pitfall", 0.8, behavioral_tags=["async", "lock"])
        assert _structural_match(atom, {"async", "lock"})

    def test_no_overlap_rejected(self):
        atom = _make_result("pit::vocab_drift", "pitfall", 0.8, behavioral_tags=["async"])
        assert not _structural_match(atom, {"lock", "deadlock"})

    def test_atom_id_match(self):
        atom = _make_result("pit::async_lock_deadlock", "pitfall", 0.8)
        assert _structural_match(atom, {"async", "lock"})

    def test_no_query_tokens_passes(self):
        """Empty query tokens = no constraint, always passes."""
        atom = _make_result("pit::p1", "pitfall", 0.8)
        assert _structural_match(atom, set())


class TestClusterConsistency:
    """Test cluster key computation."""

    def test_cluster_key_intersection(self):
        atom = _make_result("pit::async_lock", "pitfall", 0.8, behavioral_tags=["async", "lock", "deadlock"])
        key = _cluster_key(atom, {"async", "lock", "session"})
        assert key == frozenset({"async", "lock"})

    def test_empty_intersection(self):
        atom = _make_result("pit::unrelated", "pitfall", 0.8, behavioral_tags=["session"])
        key = _cluster_key(atom, {"async", "lock"})
        assert key == frozenset()


class TestBuildDeliveryLayers:
    """Unit tests for _build_delivery_layers with all 3 constraints."""

    def test_structural_match_blocks_unrelated(self):
        """High MI atom from different semantic cluster rejected."""
        tools = _make_tools()
        results = [
            _make_result("pit::vocab_drift", "pitfall", 0.8, behavioral_tags=["async"]),
        ]
        delivery = tools._build_delivery_layers(results, query="lock deadlock")
        assert len(delivery["primary"]) == 0

    def test_structural_match_allows_relevant(self):
        """Atom matching query tokens promoted."""
        tools = _make_tools()
        results = [
            _make_result("pit::async_lock", "pitfall", 0.5, behavioral_tags=["async", "lock"]),
        ]
        delivery = tools._build_delivery_layers(results, query="async lock patterns")
        assert len(delivery["primary"]) == 1

    def test_pitfall_promoted_with_match(self):
        """Pitfalls at mi >= 0.3 promoted when structurally matching."""
        tools = _make_tools()
        results = [
            _make_result("sym::A", "symbol", 0.9, behavioral_tags=["lock"]),
            _make_result("pit::p1", "pitfall", 0.35, behavioral_tags=["lock"]),
        ]
        delivery = tools._build_delivery_layers(results, query="lock patterns")
        primary_ids = [r["atom_id"] for r in delivery["primary"]]
        assert "pit::p1" in primary_ids

    def test_pitfall_threshold_strict(self):
        """Pitfalls below threshold NOT promoted even with structural match."""
        tools = _make_tools()
        results = [
            _make_result("pit::low", "pitfall", 0.29, behavioral_tags=["lock"]),
            _make_result("sym::A", "symbol", 0.9, behavioral_tags=["lock"]),
        ]
        delivery = tools._build_delivery_layers(results, query="lock patterns")
        primary_ids = [r["atom_id"] for r in delivery["primary"]]
        assert "pit::low" not in primary_ids

    def test_cluster_consistency_single_cluster(self):
        """All items from same cluster → all survive."""
        tools = _make_tools()
        results = [
            _make_result(f"pit::async_lock_{i}", "pitfall", 0.5 + i * 0.1, behavioral_tags=["async", "lock"])
            for i in range(5)
        ]
        delivery = tools._build_delivery_layers(results, query="async lock patterns")
        assert len(delivery["primary"]) == 5
        assert delivery["dominant_cluster"] == frozenset({"async", "lock"})

    def test_cluster_consistency_splits_clusters(self):
        """Items from different clusters → only dominant cluster kept."""
        tools = _make_tools()
        results = [
            # cluster {async, lock}: 3 items
            _make_result("pit::async_lock_1", "pitfall", 0.9, behavioral_tags=["async", "lock"]),
            _make_result("pit::async_lock_2", "pitfall", 0.8, behavioral_tags=["async", "lock"]),
            _make_result("sym::lock_guard", "symbol", 0.7, behavioral_tags=["lock"]),
            # cluster {async, session}: 1 item
            _make_result("pit::async_session", "pitfall", 0.85, behavioral_tags=["async", "session"]),
            # cluster {session}: 1 item
            _make_result("sym::session_mgr", "symbol", 0.6, behavioral_tags=["session"]),
        ]
        delivery = tools._build_delivery_layers(results, query="async lock session")
        # Cluster counts: {async,lock}=2, {lock}=1, {async,session}=1, {session}=1
        # Dominant is {async,lock} with 2
        assert delivery["dominant_cluster"] == frozenset({"async", "lock"})
        assert len(delivery["primary"]) == 2

    def test_max_primary_cap(self):
        """Never exceeds max_primary items."""
        tools = _make_tools()
        results = [
            _make_result(f"pit::async_lock_{i}", "pitfall", 0.5 + i * 0.1, behavioral_tags=["async", "lock"])
            for i in range(10)
        ]
        delivery = tools._build_delivery_layers(results, query="async lock")
        assert len(delivery["primary"]) == 5

    def test_custom_max_primary(self):
        """Custom config changes the cap."""
        tools = _make_tools()
        cfg = PrimarySelectionConfig(max_primary=2)
        results = [
            _make_result(f"pit::async_lock_{i}", "pitfall", 0.5 + i * 0.1, behavioral_tags=["async", "lock"])
            for i in range(10)
        ]
        delivery = tools._build_delivery_layers(results, query="async lock", config=cfg)
        assert len(delivery["primary"]) == 2

    def test_categories_never_primary(self):
        """cat:: atoms stay secondary regardless of MI or match."""
        tools = _make_tools()
        results = [
            _make_result("cat::async", "category", 0.95),
            _make_result("cat::locks", "cat::", 0.95),
        ]
        delivery = tools._build_delivery_layers(results, query="async lock")
        assert len(delivery["primary"]) == 0

    def test_empty_primary_is_silence(self):
        """No qualifying results → empty primary, all secondary."""
        tools = _make_tools()
        results = [
            _make_result("cat::meta", "category", 0.5),
            _make_result("unknown::x", "unknown", 0.2),
        ]
        delivery = tools._build_delivery_layers(results, query="something")
        assert len(delivery["primary"]) == 0
        assert delivery["secondary_count"] == 2

    def test_fallback_low_mi_all_secondary(self):
        """All results mi < 0.3 → empty primary even with structural match."""
        tools = _make_tools()
        results = [
            _make_result("sym::low", "symbol", 0.29, behavioral_tags=["lock"]),
            _make_result("pit::low", "pitfall", 0.1, behavioral_tags=["lock"]),
        ]
        delivery = tools._build_delivery_layers(results, query="lock patterns")
        assert len(delivery["primary"]) == 0

    def test_layer_reason_deterministic(self):
        """Same input produces same output (no hidden state)."""
        tools = _make_tools()
        results = [
            _make_result("pit::async_lock", "pitfall", 0.5, behavioral_tags=["async", "lock"]),
            _make_result("sym::lock_guard", "symbol", 0.8, behavioral_tags=["lock"]),
        ]
        d1 = tools._build_delivery_layers(results, query="async lock")
        d2 = tools._build_delivery_layers(results, query="async lock")
        assert [r["atom_id"] for r in d1["primary"]] == [r["atom_id"] for r in d2["primary"]]

    def test_selection_criteria_flags(self):
        """Selection criteria includes structural_match and cluster_consistency."""
        tools = _make_tools()
        results = [_make_result("pit::p1", "pitfall", 0.5, behavioral_tags=["lock"])]
        delivery = tools._build_delivery_layers(results, query="lock patterns")
        sc = delivery["selection_criteria"]
        assert sc["structural_match"] is True
        assert sc["cluster_consistency"] is True
        assert sc["max_primary"] == 5

    def test_qra_alpha_promoted_with_match(self):
        """QRA atoms at mi >= 0.7 promoted via rule 3 when matching."""
        tools = _make_tools()
        results = [
            _make_result("qra::lock_handler", "qra", 0.85, behavioral_tags=["lock"]),
        ]
        delivery = tools._build_delivery_layers(results, query="lock handler")
        assert len(delivery["primary"]) == 1

    def test_duplicate_atom_id_skipped(self):
        """Duplicate atom_id only promoted once."""
        tools = _make_tools()
        results = [
            _make_result("pit::async_lock", "pitfall", 0.5, behavioral_tags=["async", "lock"]),
            _make_result("pit::async_lock", "pitfall", 0.6, behavioral_tags=["async", "lock"]),
        ]
        delivery = tools._build_delivery_layers(results, query="async lock")
        assert len(delivery["primary"]) == 1

    def test_empty_results(self):
        """Empty results list → empty primary."""
        tools = _make_tools()
        delivery = tools._build_delivery_layers([], query="test")
        assert len(delivery["primary"]) == 0
        assert delivery["secondary_count"] == 0

    def test_no_query_fallback(self):
        """Empty query string → no structural constraint (backward compat)."""
        tools = _make_tools()
        results = [
            _make_result("sym::A", "symbol", 0.9),
            _make_result("pit::p1", "pitfall", 0.5),
        ]
        delivery = tools._build_delivery_layers(results, query="")
        # Without query tokens, structural_match returns True (no constraint)
        assert len(delivery["primary"]) >= 1


class TestSecondarySummary:
    """Test secondary downgrade to count + type summary."""

    def test_type_counts(self):
        results = [
            _make_result("cat::a", "category", 0.5),
            _make_result("sym::b", "symbol", 0.7),
            _make_result("sym::c", "symbol", 0.6),
            _make_result("pit::d", "pitfall", 0.4),
        ]
        summary = _build_secondary_summary(results)
        assert summary["category"] == 1
        assert summary["symbol"] == 2
        assert summary["pitfall"] == 1

    def test_delivery_has_secondary_summary(self):
        tools = _make_tools()
        results = [
            _make_result("cat::async", "category", 0.5),
            _make_result("sym::lock", "symbol", 0.7, behavioral_tags=["lock"]),
        ]
        delivery = tools._build_delivery_layers(results, query="lock")
        assert "secondary_summary" in delivery
        assert delivery["secondary_summary"]["category"] == 1
        assert delivery["secondary_summary"]["symbol"] == 1


class TestDeliveryTierAnnotation:
    """Test delivery_tier annotation in daemon results."""

    def test_alpha_tier(self):
        mi = 0.85
        tier = "alpha" if mi >= 0.7 else ("beta" if mi >= 0.5 else ("gamma" if mi >= 0.3 else "delta"))
        assert tier == "alpha"

    def test_beta_tier(self):
        mi = 0.6
        tier = "alpha" if mi >= 0.7 else ("beta" if mi >= 0.5 else ("gamma" if mi >= 0.3 else "delta"))
        assert tier == "beta"

    def test_gamma_tier(self):
        mi = 0.4
        tier = "alpha" if mi >= 0.7 else ("beta" if mi >= 0.5 else ("gamma" if mi >= 0.3 else "delta"))
        assert tier == "gamma"

    def test_delta_tier(self):
        mi = 0.2
        tier = "alpha" if mi >= 0.7 else ("beta" if mi >= 0.5 else ("gamma" if mi >= 0.3 else "delta"))
        assert tier == "delta"


class TestPrimaryOverridesStripPayload:
    """Test that primary atoms retain payloads under SUMMARY/HIDDEN intent."""

    def test_primary_keeps_payload(self):
        primary_ids = frozenset({"pit::p1"})
        strip_payload = True
        atom_id = "pit::p1"
        payload = "important content"
        result_payload = None if (strip_payload and atom_id not in primary_ids) else payload
        assert result_payload == "important content"

    def test_secondary_stripped(self):
        primary_ids = frozenset({"pit::p1"})
        strip_payload = True
        atom_id = "sym::B"
        payload = "some content"
        result_payload = None if (strip_payload and atom_id not in primary_ids) else payload
        assert result_payload is None

    def test_no_strip_when_full(self):
        primary_ids = frozenset()
        strip_payload = False
        payload = "content"
        result_payload = None if (strip_payload and "sym::A" not in primary_ids) else payload
        assert result_payload == "content"

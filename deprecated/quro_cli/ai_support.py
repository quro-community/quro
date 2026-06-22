"""AI Decision Support — Descriptive suggestions for AI query strategy.

@module quro_cli.ai_support
@intent Provide descriptive suggestions for AI to consider when planning queries.
        CRITICAL: Suggestions are for AI interpretation only. CQE never sees them.
        NO recommendations, NO guidance, NO "should", NO "optimize".

Design constraints (from Final Roadmap):
  - AI makes all decisions, NOT this module
  - Suggestions are strictly descriptive
  - No execution guidance or routing strategies
  - CQE remains pure deterministic execution engine

This module provides:
  - Query strategy suggestions based on historical telemetry
  - Tool selection hints based on failure catalog
  - Cost awareness signals from telemetry statistics

Usage:
    from quro_cli.ai_support import suggest_query_strategy

    suggestions = suggest_query_strategy("async lock pattern", context)
    # AI reads suggestions → AI decides → AI calls CQE
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core Suggestion Engine
# ---------------------------------------------------------------------------

def suggest_query_strategy(
    query: str,
    context: dict[str, Any],
    project_root: Path | None = None
) -> list[str]:
    """Generate descriptive suggestions for AI to consider.

    @intent Help AI understand query landscape without prescribing actions.
            AI reads these → makes informed decision → calls CQE appropriately.

    CRITICAL: This is NOT called by CQE. This is called by AI agent BEFORE
              deciding which query to run. Output is descriptive only.

    Args:
        query: Natural language query string
        context: Additional context (e.g., entry_token, target_symbol)
        project_root: Project root directory (defaults to cwd)

    Returns:
        List of descriptive suggestion strings. AI interprets these.
    """
    if project_root is None:
        project_root = Path.cwd()

    suggestions = []

    # Load AI Knowledge Base artifacts
    tool_catalog = _load_catalog(project_root, "tool_catalog.json")
    failure_catalog = _load_catalog(project_root, "failure_catalog.json")
    telemetry_stats = _load_report(project_root, "telemetry_stats.json")

    # Extract query tokens for pattern matching
    query_tokens = set(query.lower().split())

    # ── Suggestion Type 1: Relevant Tool Hints ─────────────────────────────

    relevant_tools = _find_relevant_tools(query_tokens, tool_catalog)
    if relevant_tools:
        suggestions.append(
            f"Tools matching your query: {', '.join(relevant_tools[:3])}. "
            f"Each tool has specific parameters and failure modes documented in tool_catalog.json."
        )

    # ── Suggestion Type 2: Failure Mode Awareness ──────────────────────────

    common_failures = _find_common_failures(query_tokens, failure_catalog)
    if common_failures:
        failure_hints = [f["pattern"] for f in common_failures[:2]]
        suggestions.append(
            f"Common failure patterns for this query type: {', '.join(failure_hints)}. "
            f"Consult failure_catalog.json for root causes and recovery actions."
        )

    # ── Suggestion Type 3: Telemetry-Based Cost Awareness ──────────────────

    cost_signals = _analyze_cost_patterns(query_tokens, telemetry_stats)
    if cost_signals:
        for signal in cost_signals[:2]:  # limit to 2 cost signals
            suggestions.append(signal)

    # ── Suggestion Type 4: Entry Token Hints ───────────────────────────────

    entry_token = context.get("entry_token")
    if entry_token:
        token_stats = _get_token_stats(entry_token, telemetry_stats)
        if token_stats:
            suggestions.append(
                f"Entry token '{entry_token}' has historical count={token_stats['count']}, "
                f"avg_mi={token_stats['avg_mi']:.3f}. "
                f"This is descriptive data — interpret based on your query intent."
            )

    # ── Suggestion Type 5: Cross-Category Pattern Hints ────────────────────

    category_hints = _find_category_patterns(query_tokens, telemetry_stats)
    if category_hints:
        suggestions.append(
            f"Related category patterns: {', '.join(category_hints[:3])}. "
            f"Consider whether these align with your query intent."
        )

    # Ensure we have at least one suggestion
    if not suggestions:
        suggestions.append(
            "No specific patterns detected. Consider using project_panorama() "
            "to understand workspace structure, or verify_symbol_integrity() "
            "to check symbol existence before querying."
        )

    logger.info(f"Generated {len(suggestions)} descriptive suggestions for query")
    return suggestions


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _load_catalog(project_root: Path, filename: str) -> dict[str, Any]:
    """Load AI Knowledge Base catalog."""
    catalog_path = project_root / ".quro_context" / "ai_kb" / filename
    if not catalog_path.exists():
        logger.warning(f"Catalog not found: {catalog_path}")
        return {}

    with catalog_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_report(project_root: Path, filename: str) -> dict[str, Any]:
    """Load telemetry statistics report."""
    report_path = project_root / ".quro_context" / "reports" / filename
    if not report_path.exists():
        logger.warning(f"Report not found: {report_path}")
        return {}

    with report_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_relevant_tools(
    query_tokens: set[str],
    tool_catalog: dict[str, Any]
) -> list[str]:
    """Find tools that match query tokens.

    @intent Help AI identify which tools might be relevant.
            This is hint generation, NOT tool selection.
    """
    if not tool_catalog or "tools" not in tool_catalog:
        return []

    relevant = []
    tools = tool_catalog["tools"]

    for tool in tools:
        tool_name = tool.get("name", "")
        description = tool.get("description", "").lower()

        # Check if query tokens match tool name or description
        if query_tokens & set(tool_name.split("_")):
            relevant.append(tool_name)
        elif query_tokens & set(description.split()):
            relevant.append(tool_name)

    return relevant


def _find_common_failures(
    query_tokens: set[str],
    failure_catalog: dict[str, Any]
) -> list[dict[str, Any]]:
    """Find common failure patterns related to query.

    @intent Warn AI about potential failure modes.
            This is awareness generation, NOT failure avoidance guidance.
    """
    if not failure_catalog or "failures" not in failure_catalog:
        return []

    relevant = []
    failures = failure_catalog["failures"]

    for failure in failures:
        pattern = failure.get("pattern", "").lower()
        root_cause = failure.get("root_cause", "").lower()

        # Check if query tokens match failure pattern or root cause
        if query_tokens & set(pattern.split()):
            relevant.append(failure)
        elif query_tokens & set(root_cause.split()):
            relevant.append(failure)

    return relevant


def _analyze_cost_patterns(
    query_tokens: set[str],
    telemetry_stats: dict[str, Any]
) -> list[str]:
    """Analyze telemetry for cost patterns.

    @intent Provide cost awareness signals.
            This is descriptive statistics, NOT cost optimization guidance.
    """
    if not telemetry_stats or "patterns" not in telemetry_stats:
        return []

    signals = []
    patterns = telemetry_stats["patterns"]

    # Find patterns matching query tokens
    for pattern_key, pattern_data in patterns.items():
        pattern_tokens = set(pattern_key.replace("::", " ").replace("_", " ").split())

        if query_tokens & pattern_tokens:
            count = pattern_data.get("count", 0)
            avg_mi = pattern_data.get("avg_mi", 0.0)

            # Generate DESCRIPTIVE signal (no "recommend", no "should")
            signals.append(
                f"Pattern '{pattern_key}': count={count}, avg_mi={avg_mi:.3f}. "
                f"This indicates historical query frequency and MI score distribution."
            )

    return signals


def _get_token_stats(
    entry_token: str,
    telemetry_stats: dict[str, Any]
) -> dict[str, Any] | None:
    """Get statistics for a specific entry token.

    @intent Provide token-specific historical data.
            This is descriptive data, NOT routing guidance.
    """
    if not telemetry_stats or "patterns" not in telemetry_stats:
        return None

    patterns = telemetry_stats["patterns"]
    return patterns.get(entry_token)


def _find_category_patterns(
    query_tokens: set[str],
    telemetry_stats: dict[str, Any]
) -> list[str]:
    """Find category patterns matching query.

    @intent Identify related category tags.
            This is pattern discovery, NOT category recommendation.
    """
    if not telemetry_stats or "patterns" not in telemetry_stats:
        return []

    categories = []
    patterns = telemetry_stats["patterns"]

    for pattern_key in patterns.keys():
        if pattern_key.startswith("cat::"):
            category_name = pattern_key.replace("cat::", "")
            category_tokens = set(category_name.split("_"))

            if query_tokens & category_tokens:
                categories.append(category_name)

    return categories


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for ai-support suggest-query command."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate descriptive query suggestions for AI"
    )
    parser.add_argument(
        "query",
        help="Natural language query string"
    )
    parser.add_argument(
        "--entry-token",
        help="Entry token context (optional)"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory"
    )
    args = parser.parse_args()

    context = {}
    if args.entry_token:
        context["entry_token"] = args.entry_token

    suggestions = suggest_query_strategy(
        args.query,
        context,
        args.project_root
    )

    print("\n💡 Descriptive Query Suggestions\n")
    print("(For AI interpretation only. NOT execution guidance.)\n")

    for i, suggestion in enumerate(suggestions, 1):
        print(f"{i}. {suggestion}\n")

    print("⚠️  These are DESCRIPTIVE suggestions.")
    print("    AI decides query strategy. CQE never sees this.\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Analyze CQE telemetry logs — Descriptive statistics only.

@intent Generate descriptive statistics from telemetry for AI interpretation.
        CRITICAL: This is strictly descriptive. NO recommendations, NO guidance,
        NO routing strategies. AI reads this and makes its own decisions.

Design constraints (from Final Roadmap):
  - Telemetry is strictly passive recording
  - Offline analysis is strictly descriptive
  - No execution guidance or routing strategies
  - AI interprets the report, CQE never sees it

Output:
    .quro_context/reports/telemetry_stats.json

Usage:
    python scripts/analyze_telemetry.py
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def analyze_telemetry(project_root: Path) -> dict[str, Any]:
    """Compute descriptive statistics from telemetry logs.

    @intent Provide AI with cost/payload statistics per query pattern.
            AI reads this → decides which query strategies to try.

    Method:
      1. Read .quro_context/cqe_telemetry.jsonl
      2. Group by entry_atom (query pattern)
      3. Compute avg_cost, avg_payload, count per pattern
      4. Return descriptive statistics (NO recommendations)

    CRITICAL: This is NOT prescriptive. No "should", no "recommend", no "optimize".
              Statistics describe what happened, not what to do.

    Returns:
        Dict with per-pattern statistics
    """
    telemetry_path = project_root / ".quro_context" / "cqe_telemetry.jsonl"

    if not telemetry_path.exists():
        logger.warning(f"Telemetry log not found: {telemetry_path}")
        return {"error": "telemetry_log_not_found", "total_records": 0}

    # Accumulate statistics per pattern
    pattern_stats: dict[str, dict[str, float]] = {}

    total_records = 0
    with telemetry_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
                total_records += 1

                # Extract fields
                entry_atom = record.get("atom", "")
                if not entry_atom:
                    continue

                # Parse decision to get query context
                decision = record.get("decision", "")
                mi = record.get("mi", 0.0)

                # Use entry_atom as pattern key
                pattern = entry_atom

                if pattern not in pattern_stats:
                    pattern_stats[pattern] = {
                        "total_mi": 0.0,
                        "count": 0,
                        "total_decisions": Counter(),
                    }

                pattern_stats[pattern]["total_mi"] += mi
                pattern_stats[pattern]["count"] += 1
                pattern_stats[pattern]["total_decisions"][decision] += 1

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in telemetry: {line[:100]}")
                continue

    # Compute averages — strictly descriptive
    result = {
        "version": 1,
        "total_records": total_records,
        "pattern_count": len(pattern_stats),
        "patterns": {},
        "_comment": (
            "DESCRIPTIVE STATISTICS ONLY. No recommendations or guidance. "
            "AI interprets this data. CQE never sees this report."
        )
    }

    for pattern, stats in pattern_stats.items():
        count = stats["count"]
        avg_mi = stats["total_mi"] / count if count > 0 else 0.0
        decision_distribution = dict(stats["total_decisions"])

        result["patterns"][pattern] = {
            "count": count,
            "avg_mi": round(avg_mi, 4),
            "decision_distribution": decision_distribution,
            # Note: No "recommendation" field — AI decides what this means
        }

    logger.info(f"Analyzed {total_records} telemetry records, {len(pattern_stats)} patterns")
    return result


def generate_report(project_root: Path) -> Path:
    """Generate telemetry statistics report.

    @intent Write descriptive statistics to file for AI consumption.

    Output:
        .quro_context/reports/telemetry_stats.json
    """
    output_dir = project_root / ".quro_context" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = analyze_telemetry(project_root)

    output_path = output_dir / "telemetry_stats.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    logger.info(f"Telemetry statistics written to {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze CQE telemetry logs (descriptive statistics only)"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory"
    )
    args = parser.parse_args()

    print("\n📊 Analyzing Telemetry Logs...\n")

    output_path = generate_report(args.project_root)

    stats = json.loads(output_path.read_text())

    print("✅ Telemetry Statistics Generated\n")
    print(f"Output:     {output_path}")
    print(f"Records:    {stats['total_records']}")
    print(f"Patterns:   {stats['pattern_count']}\n")

    if stats['pattern_count'] > 0:
        print("Top 5 Patterns by Count:")
        sorted_patterns = sorted(
            stats['patterns'].items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        for i, (pattern, data) in enumerate(sorted_patterns[:5], 1):
            print(f"  {i}. {pattern}")
            print(f"     count={data['count']}, avg_mi={data['avg_mi']:.3f}")

    print("\n⚠️  This report is DESCRIPTIVE ONLY.")
    print("    No recommendations or guidance provided.")
    print("    AI interprets this data. CQE never sees it.\n")


if __name__ == "__main__":
    main()

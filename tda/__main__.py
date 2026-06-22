"""TDA MI Warm-up CLI Command

@module quro.tda.__main__
@intent CLI entry point for TDA MI warm-up operations
"""

import argparse
import logging
import sys
from pathlib import Path

from tda.mi_warmup import (
    generate_tda_mi_scores,
    load_manual_seeds,
    merge_mi_sources,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_warmup_mi(args):
    """Execute TDA MI warm-up command."""
    workspace_root = Path(args.workspace or ".")
    output_path = workspace_root / ".quro_context" / "tda_mi_scores.json"

    logger.info("Starting TDA MI warm-up for workspace: %s", workspace_root)

    # Generate TDA-derived MI scores
    tda_scores = generate_tda_mi_scores(workspace_root, output_path=output_path)

    if not tda_scores:
        logger.error("Failed to generate TDA MI scores")
        return 1

    # Load manual seeds if available
    seeds_path = workspace_root / ".quro_context" / "mi_seeds.json"
    manual_seeds = load_manual_seeds(seeds_path)

    # Merge sources
    final_scores = merge_mi_sources(tda_scores, manual_seeds)

    # Statistics
    high_mi = sum(1 for s in final_scores.values() if s.mi_score >= 0.8)
    medium_mi = sum(1 for s in final_scores.values() if 0.5 <= s.mi_score < 0.8)
    low_mi = sum(1 for s in final_scores.values() if s.mi_score < 0.5)

    print("\n" + "=" * 60)
    print("TDA MI Warm-up Complete")
    print("=" * 60)
    print(f"Total symbols: {len(final_scores)}")
    print(f"  High MI (≥0.8):   {high_mi:4d} ({high_mi/len(final_scores)*100:.1f}%)")
    print(f"  Medium MI (0.5-0.8): {medium_mi:4d} ({medium_mi/len(final_scores)*100:.1f}%)")
    print(f"  Low MI (<0.5):    {low_mi:4d} ({low_mi/len(final_scores)*100:.1f}%)")
    print(f"\nManual seeds: {len(manual_seeds)}")
    print(f"Output: {output_path}")
    print("\nNext steps:")
    print("  1. CQE queries will now use TDA MI scores as floor")
    print("  2. As you make queries, history will refine the scores")
    print("  3. Hybrid weight: ω·MI_tda + (1-ω)·MI_history")
    print("     where ω decreases from 0.9 → 0.1 over 100 queries")
    print("=" * 60)

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Quro TDA MI Warm-up",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # warmup-mi command
    warmup_parser = subparsers.add_parser(
        "warmup-mi",
        help="Generate initial MI scores from TDA Phase 2 analysis",
    )
    warmup_parser.add_argument(
        "--workspace",
        type=str,
        help="Workspace root directory (default: current directory)",
    )

    args = parser.parse_args()

    if args.command == "warmup-mi":
        return cmd_warmup_mi(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

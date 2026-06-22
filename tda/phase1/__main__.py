"""
Phase-1 TDA Offline Batch Processor

Usage:
    python -m quro.tda.phase1 [OPTIONS]

Examples:
    # Full traversal
    python -m quro.tda.phase1

    # Incremental update
    python -m quro.tda.phase1 --incremental

    # Custom parameters
    python -m quro.tda.phase1 --tau 0.1 --max-depth 5
"""

import asyncio
import argparse
from pathlib import Path
import time
import sys

from tda.phase1.batch_processor import Phase1BatchProcessor


def main():
    """CLI entry point for Phase-1 batch processor."""
    parser = argparse.ArgumentParser(
        description="Phase-1 TDA: Offline manifold observation batch processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full traversal
  python -m quro.tda.phase1

  # Incremental update (skip already-processed symbols)
  python -m quro.tda.phase1 --incremental

  # Custom parameters
  python -m quro.tda.phase1 --tau 0.1 --max-depth 5

  # Custom output path
  python -m quro.tda.phase1 --output /tmp/phase1_events.jsonl
        """
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".quro_context/tda/phase1/graph_events.jsonl"),
        help="Output JSONL file path (default: .quro_context/tda/phase1/graph_events.jsonl)"
    )

    parser.add_argument(
        "--registry-db",
        type=Path,
        default=Path(".quro_context/registry.db"),
        help="Symbol registry database path (default: .quro_context/registry.db)"
    )

    parser.add_argument(
        "--tau",
        type=float,
        default=0.05,
        help="MI-gate threshold (default: 0.05)"
    )

    parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="Maximum BFS depth (default: 3)"
    )

    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Skip already-processed symbols (for incremental updates)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.registry_db.exists():
        print(f"[Phase-1] Error: Registry database not found: {args.registry_db}")
        print("[Phase-1] Hint: Run symbol indexing first")
        print("[Phase-1]   python -m quro.build_index")
        return 1

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Print configuration
    print("[Phase-1] Starting offline manifold observation...")
    print(f"[Phase-1] Registry: {args.registry_db}")
    print(f"[Phase-1] Output: {args.output}")
    print(f"[Phase-1] Tau: {args.tau}, Max Depth: {args.max_depth}")
    print(f"[Phase-1] Incremental: {args.incremental}")
    print()

    # Create processor
    processor = Phase1BatchProcessor(
        registry_db=args.registry_db,
        output_path=args.output,
        tau=args.tau,
        max_depth=args.max_depth
    )

    # Run batch processing
    start_time = time.time()

    try:
        asyncio.run(processor.run_full_traversal(incremental=args.incremental))
    except KeyboardInterrupt:
        print("\n[Phase-1] Interrupted by user")
        print(f"[Phase-1] Partial results saved to: {args.output}")
        return 1
    except Exception as e:
        print(f"\n[Phase-1] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Print summary
    duration = time.time() - start_time
    minutes = int(duration // 60)
    seconds = int(duration % 60)

    print(f"\n[Phase-1] Duration: {minutes}m {seconds}s")
    print(f"[Phase-1] Output: {args.output}")
    print("[Phase-1] ✓ Complete")

    return 0


if __name__ == "__main__":
    sys.exit(main())

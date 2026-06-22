"""Scanner Commands

@module quro.cli.commands.scanner
@intent CLI commands for workspace scanning.
"""

import argparse
import sys
import time
from pathlib import Path

from cli.base import BaseCommand
from service import ScannerService


class ScanCommand(BaseCommand):
    """Scan workspace and build index."""

    def get_name(self) -> str:
        return "scan"

    def get_help(self) -> str:
        return "Scan workspace and build symbol index"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--workspace",
            type=Path,
            default=Path.cwd(),
            help="Workspace root directory (default: current directory)",
        )
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="Clear existing index and rebuild from scratch",
        )
        parser.add_argument(
            "--no-progress",
            action="store_true",
            help="Disable progress messages",
        )

    def execute(self, args: argparse.Namespace) -> int:
        workspace = args.workspace.resolve()

        print(f"[Scanner] Workspace: {workspace}")
        print(f"[Scanner] Rebuild: {args.rebuild}")
        print()

        # Initialize service
        service = ScannerService()
        try:
            service.initialize(workspace)
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        # Scan workspace
        print("[Scanner] Scanning workspace and building index...")
        start_time = time.time()

        try:
            result = service.scan_workspace(
                rebuild=args.rebuild,
                progress=not args.no_progress,
            )
        except Exception as e:
            print(f"\n[Error] {e}", file=sys.stderr)
            return 1

        duration = time.time() - start_time

        # Print summary
        print()
        print("=" * 60)
        print("Index Build Complete")
        print("=" * 60)
        print()
        print("Scan Statistics:")
        print(f"  Files discovered: {result['scan']['files_discovered']}")
        print(f"  Files scanned:    {result['scan']['files_scanned']}")
        print(f"  Files skipped:    {result['scan']['files_skipped']}")
        print(f"  Symbols found:    {result['scan']['symbols_found']}")
        print(f"  Symbols kept:     {result['scan']['symbols_kept']}")
        print(f"  Symbols filtered: {result['scan']['symbols_filtered']}")
        print()
        print("Index Statistics:")
        print(f"  Symbols indexed:  {result['index']['symbols_indexed']}")
        print(f"  Nodes created:    {result['index']['nodes_created']}")
        print(f"  Edges created:    {result['index']['edges_created']}")
        print(f"  Categories:       {result['index']['categories_created']}")
        print()
        print(f"Duration: {duration:.2f}s")
        print(f"Output: {result['output']}")
        print()
        print("✓ Index persisted to SQLite database")
        print()
        print("Next steps:")
        print("  1. Run TDA pipeline: quro tda run")
        print("  2. Query CQE: quro cqe query <symbol>")
        print()

        return 0

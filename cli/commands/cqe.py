"""CQE Commands

@module quro.cli.commands.cqe
@intent CLI commands for CQE queries.

Mirrors MCP `quro_lookup` for the human/script surface: the three CQE query
variants (single / multi-tier / with-mode) collapse onto one `cqe query`
command with --mode/--tier selectors, plus the atomic getters
(symbol/category/list/stats).
"""

import argparse
import json
import sys
from pathlib import Path

from cli.base import BaseCommand
from cli.commands._common import (
    add_json_arg,
    add_workspace_arg,
    init_service,
    run_service,
    emit,
)
from service import CQEService


class CQEQueryCommand(BaseCommand):
    """Execute CQE semantic query."""

    def get_name(self) -> str:
        return "cqe query"

    def get_help(self) -> str:
        return "Execute CQE semantic query"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "start",
            help="Starting node ID (e.g., 'sym::LockManager' or 'cat::async')",
        )
        parser.add_argument(
            "--tau",
            type=float,
            default=0.05,
            help="MI-gate threshold [0, 1] (default: 0.05)",
        )
        parser.add_argument(
            "--max-depth",
            type=int,
            default=3,
            help="Maximum traversal depth (default: 3)",
        )
        parser.add_argument(
            "--no-refiner",
            action="store_true",
            help="Disable semantic refiner",
        )
        parser.add_argument(
            "--mode",
            choices=["forward", "reverse", "field_guided", "saddle_escape"],
            help="Force a specific traversal mode (replaces --tier if set)",
        )
        parser.add_argument(
            "--tier",
            choices=["single", "multi"],
            default="single",
            help="single (default) = one tau level; multi = tiered 0.3/0.1/0.05",
        )
        add_workspace_arg(parser)
        add_json_arg(parser)

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(CQEService(), args)
        if code:
            return code

        common = {
            "start": args.start,
            "max_depth": args.max_depth,
            "use_semantic_refiner": not args.no_refiner,
        }

        if args.mode:
            result, code = run_service(
                service,
                "query_with_mode",
                kwargs={**common, "tau": args.tau, "traversal_mode": args.mode},
            )
        elif args.tier == "multi":
            result, code = run_service(service, "query_multi_tier", kwargs=common)
        else:
            result, code = run_service(
                service, "query", kwargs={**common, "tau": args.tau}
            )
        if code:
            return code

        # Output result
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Query: {args.start}")
            print(f"Tau: {args.tau}")
            print(f"Max depth: {args.max_depth}")
            print()
            print(f"Results: {len(result.get('symbols', []))} symbols, "
                  f"{len(result.get('categories', []))} categories")
            print()
            if result.get('symbols'):
                print("Symbols:")
                for sym in result['symbols'][:10]:
                    print(f"  - {sym}")
            if result.get('categories'):
                print("Categories:")
                for cat in result['categories'][:10]:
                    print(f"  - {cat}")

        return 0


class CQESymbolCommand(BaseCommand):
    """Get symbol details."""

    def get_name(self) -> str:
        return "cqe symbol"

    def get_help(self) -> str:
        return "Get symbol details"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "symbol",
            help="Symbol name (without 'sym::' prefix)",
        )
        parser.add_argument(
            "--workspace",
            type=Path,
            default=Path.cwd(),
            help="Workspace root directory (default: current directory)",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output as JSON",
        )

    def execute(self, args: argparse.Namespace) -> int:
        workspace = args.workspace.resolve()

        # Initialize service
        service = CQEService()
        try:
            service.initialize(workspace)
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        # Get symbol
        try:
            result = service.get_symbol(args.symbol)
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        if result is None:
            print(f"[Error] Symbol not found: {args.symbol}", file=sys.stderr)
            return 1

        # Output result
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Symbol: {args.symbol}")
            print(f"File: {result.get('file', 'N/A')}")
            print(f"Line: {result.get('line', 'N/A')}")
            print(f"Kind: {result.get('kind', 'N/A')}")
            if result.get('tags'):
                print(f"Tags: {', '.join(result['tags'])}")

        return 0


class CQEListCommand(BaseCommand):
    """List symbols or categories."""

    def get_name(self) -> str:
        return "cqe list"

    def get_help(self) -> str:
        return "List symbols or categories"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "type",
            choices=["symbols", "categories"],
            help="What to list",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of items (default: 100)",
        )
        parser.add_argument(
            "--workspace",
            type=Path,
            default=Path.cwd(),
            help="Workspace root directory (default: current directory)",
        )

    def execute(self, args: argparse.Namespace) -> int:
        workspace = args.workspace.resolve()

        # Initialize service
        service = CQEService()
        try:
            service.initialize(workspace)
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        # List items
        try:
            if args.type == "symbols":
                items = service.list_symbols(limit=args.limit)
            else:
                items = service.list_categories()
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        print(f"{args.type.capitalize()}: {len(items)}")
        print()
        for item in items:
            print(f"  - {item}")

        return 0


# ---------------------------------------------------------------------------
# quro cqe stats   (mirrors MCP quro_lookup{kind:stats})
# ---------------------------------------------------------------------------

class CQEStatsCommand(BaseCommand):
    """Get scan/index/graph statistics."""

    def get_name(self) -> str:
        return "cqe stats"

    def get_help(self) -> str:
        return "Get scan/index/graph statistics"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        add_workspace_arg(parser)
        add_json_arg(parser)

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(CQEService(), args)
        if code:
            return code

        result, code = run_service(service, "get_stats")
        if code:
            return code

        def human(r):
            print("Statistics:")
            for section, values in (r or {}).items():
                if isinstance(values, dict):
                    print(f"  {section}:")
                    for k, v in values.items():
                        print(f"    {k}: {v}")
                else:
                    print(f"  {section}: {values}")

        return emit(result, args, human=human)

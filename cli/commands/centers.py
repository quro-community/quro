"""Centers Commands — semantic center orientation surface.

@module quro.cli.commands.centers
@intent CLI mirror of MCP quro_landscape: list/show/reach semantic centers.

This is the human-facing counterpart to the MCP `quro_landscape` tool. The
same TDAService methods back both surfaces, so output is identical (modulo
--json formatting).
"""

import argparse
import json
from pathlib import Path

from cli.base import BaseCommand
from cli.commands._common import (
    ServiceCommand,
    add_json_arg,
    add_workspace_arg,
    init_service,
    run_service,
    emit,
)
from service.tda_service import TDAService


# ---------------------------------------------------------------------------
# quro centers list   (mirrors MCP quro_landscape{view:summary})
# ---------------------------------------------------------------------------

class CentersListCommand(BaseCommand):
    """List all semantic centers (the navigation map)."""

    def get_name(self) -> str:
        return "centers list"

    def get_help(self) -> str:
        return "List all semantic centers with archetype, size, and entry points"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        add_workspace_arg(parser)
        add_json_arg(parser)

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(TDAService(), args)
        if code:
            return code

        result, code = run_service(
            service, "get_semantic_centers", error_prefix="Error"
        )
        if code:
            return code

        def human(r):
            print(r["summary"])
            print()
            centers = r.get("centers", [])
            print(f"{'ID':<6}{'Archetype':<12}{'Size':>8}  Entry points")
            print("-" * 70)
            for c in centers:
                topo = c.get("topology", {})
                eps = [ep.get("symbol", "") for ep in topo.get("entry_points", [])[:3]]
                print(
                    f"{c.get('id','?'):<6}"
                    f"{topo.get('pattern','-'):<12}"
                    f"{c.get('size',0):>8}  {', '.join(eps)}"
                )

        return emit(result, args, human=human)


# ---------------------------------------------------------------------------
# quro centers show <Cn>   (mirrors MCP quro_landscape{view:regions})
# ---------------------------------------------------------------------------

class CentersShowCommand(BaseCommand):
    """Show details for one semantic center."""

    def get_name(self) -> str:
        return "centers show"

    def get_help(self) -> str:
        return "Show details for a semantic center (archetype, entry points, reachability hint)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "center_id",
            help="Center ID (e.g., C0, C1)",
        )
        add_workspace_arg(parser)
        add_json_arg(parser)

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(TDAService(), args)
        if code:
            return code

        result, code = run_service(service, "get_semantic_centers")
        if code:
            return code

        centers = {c["id"]: c for c in result.get("centers", [])}
        if args.center_id not in centers:
            print(
                f"[Error] Center not found: {args.center_id}. "
                f"Available: {', '.join(sorted(centers))}",
                file=__import__("sys").stderr,
            )
            return 1

        center = centers[args.center_id]

        def human(r):
            c = r
            topo = c.get("topology", {})
            nav = c.get("navigation", {})
            print(f"Center {c.get('id')}")
            print(f"  Archetype:    {topo.get('pattern','-')}")
            print(f"  Size:         {c.get('size',0)} symbols")
            print(f"  Cluster:      {c.get('structural_cluster_id','-')}")
            eps = topo.get("entry_points", [])
            print(f"  Entry points: {len(eps)}")
            for ep in eps[:5]:
                print(f"    - {ep.get('symbol')} ({ep.get('role','-')})")
            if nav.get("landing_hint"):
                print(f"  Landing hint: {nav['landing_hint']}")

        return emit(center, args, human=human)


# ---------------------------------------------------------------------------
# quro centers reach <Cn>   (mirrors MCP quro_landscape{center_id})
# ---------------------------------------------------------------------------

class CentersReachCommand(BaseCommand):
    """Get reachable symbols from a semantic center's entry points."""

    def get_name(self) -> str:
        return "centers reach"

    def get_help(self) -> str:
        return "Get reachable symbols from a center (BFS from entry points)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "center_id",
            help="Center ID (e.g., C0, C1)",
        )
        parser.add_argument(
            "--max-symbols",
            type=int,
            default=50,
            help="Maximum symbols to return (default: 50)",
        )
        add_workspace_arg(parser)
        add_json_arg(parser)

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(TDAService(), args)
        if code:
            return code

        result, code = run_service(
            service,
            "get_center_reachability",
            kwargs={
                "center_id": args.center_id,
                "max_symbols": args.max_symbols,
            },
            error_prefix="Error",
        )
        if code:
            return code

        def human(r):
            print(f"Center {r.get('center_id')} — {r.get('count',0)} reachable symbols "
                  f"(capped at {r.get('max_symbols')})")
            eps = r.get("entry_points_used", [])
            print(f"Entry points used: {', '.join(eps)}")
            print(f"Computed in {r.get('computation_time_ms',0)} ms")
            print()
            for s in r.get("reachable_symbols", []):
                print(f"  - {s}")

        return emit(result, args, human=human)


__all__ = [
    "CentersListCommand",
    "CentersShowCommand",
    "CentersReachCommand",
]

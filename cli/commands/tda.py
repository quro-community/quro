"""TDA Commands

@module quro.cli.commands.tda
@intent CLI commands for TDA operations.

This module provides the human-facing mirror of MCP `quro_navigate` and
`quro_landscape{view:attractors}`. Each navigation action (next, upstream,
escape, role, field, path) is exposed as a dedicated `quro tda <action>`
command so scripts can pipe them; all support `--json` for parity with MCP.
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
from service import TDAService


class TDAPlanCommand(BaseCommand):
    """Plan trajectory from start to goal."""

    def get_name(self) -> str:
        return "tda plan"

    def get_help(self) -> str:
        return "Plan trajectory from start to goal"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "start",
            help="Starting symbol (e.g., 'sym::main')",
        )
        parser.add_argument(
            "goal",
            help="Goal symbol (e.g., 'sym::EventLogWriter')",
        )
        parser.add_argument(
            "--intent",
            default="navigate to goal",
            help="Intent description (default: 'navigate to goal')",
        )
        parser.add_argument(
            "--max-hops",
            type=int,
            default=20,
            help="Maximum path length (default: 20)",
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
        service = TDAService()
        try:
            service.initialize(workspace)
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        # Plan trajectory
        try:
            result = service.plan_trajectory(
                start=args.start,
                goal=args.goal,
                intent=args.intent,
                max_hops=args.max_hops,
            )
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        if "error" in result:
            print(f"[Error] {result['error']}", file=sys.stderr)
            return 1

        # Output result
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Trajectory Plan:")
            print(f"  Start: {result['start']}")
            print(f"  Goal: {result['goal']}")
            print(f"  Path length: {len(result['path'])}")
            print(f"  Total energy: {result['total_energy']:.2f}")
            print(f"  Risk score: {result['risk_score']:.2f}")
            print(f"  Valid: {result['is_valid']}")
            print()
            print(f"Path: {' → '.join(result['path'])}")

        return 0


class TDAExploreCommand(BaseCommand):
    """Explore codebase using beam search."""

    def get_name(self) -> str:
        return "tda explore"

    def get_help(self) -> str:
        return "Explore codebase using beam search"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "start",
            help="Starting symbol",
        )
        parser.add_argument(
            "--intent",
            default="explore codebase",
            help="Exploration intent (default: 'explore codebase')",
        )
        parser.add_argument(
            "--steps",
            type=int,
            default=5,
            help="Maximum exploration steps (default: 5)",
        )
        parser.add_argument(
            "--beam-width",
            type=int,
            default=5,
            help="Beam width (default: 5)",
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
        service = TDAService()
        try:
            service.initialize(workspace)
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        # Explore
        try:
            result = service.explore(
                start=args.start,
                intent=args.intent,
                steps=args.steps,
                beam_width=args.beam_width,
            )
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        # Output result
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Beam Search Exploration:")
            print(f"  Start: {result['start']}")
            print(f"  Intent: {result['intent']}")
            print(f"  Steps: {result['steps']}")
            print(f"  Final paths: {len(result['final_paths'])}")
            print()
            for i, path in enumerate(result['final_paths'][:3]):
                print(f"Path {i+1} (score={path['score']:.3f}):")
                print(f"  {' → '.join(path['path'])}")
                print()

        return 0


class TDACentersCommand(BaseCommand):
    """Get semantic centers."""

    def get_name(self) -> str:
        return "tda centers"

    def get_help(self) -> str:
        return "Get semantic centers"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
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
        service = TDAService()
        try:
            service.initialize(workspace)
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        # Get centers
        try:
            result = service.get_semantic_centers()
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        # Output result
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(result['summary'])
            print()
            for center in result['centers']:
                print(f"Center {center['id']}:")
                print(f"  Archetype: {center.get('archetype', 'N/A')}")
                print(f"  Size: {center.get('size', 0)} symbols")
                print()

        return 0


# ---------------------------------------------------------------------------
# quro tda next --from S     (mirrors MCP quro_navigate{action:next})
# ---------------------------------------------------------------------------

class TDANextCommand(BaseCommand):
    """Query best next symbols to navigate to from a position."""

    def get_name(self) -> str:
        return "tda next"

    def get_help(self) -> str:
        return "Query best next symbols from current position (type-aware)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--from",
            dest="from_symbol",
            required=True,
            help="Current symbol (e.g., 'sym::main')",
        )
        parser.add_argument(
            "--intent",
            default="",
            help="Optional navigation intent",
        )
        parser.add_argument(
            "--max-candidates",
            type=int,
            default=5,
            help="Maximum candidates to return (default: 5)",
        )
        add_workspace_arg(parser)
        add_json_arg(parser)

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(TDAService(), args)
        if code:
            return code

        result, code = run_service(
            service,
            "query_next_nodes",
            kwargs={
                "from_symbol": args.from_symbol,
                "intent": args.intent,
                "max_candidates": args.max_candidates,
            },
        )
        if code:
            return code

        def human(r):
            print(f"From: {r.get('from_symbol')}  ({r.get('node_type','-')})")
            print(r.get("explanation", ""))
            print()
            for n in r.get("neighbors", []):
                print(
                    f"  - {n.get('symbol')}  "
                    f"[{n.get('kind','-')}/{n.get('relationship','-')}] "
                    f"weight={n.get('weight',0):.3f} energy={n.get('energy',0):.2f}"
                )

        return emit(result, args, human=human)


# ---------------------------------------------------------------------------
# quro tda upstream --symbol S   (mirrors MCP quro_navigate{action:upstream})
# ---------------------------------------------------------------------------

class TDAUpstreamCommand(BaseCommand):
    """Find upstream sources for a symbol."""

    def get_name(self) -> str:
        return "tda upstream"

    def get_help(self) -> str:
        return "Find upstream sources for a symbol (controlled backward nav)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--symbol",
            required=True,
            help="Symbol ID (e.g., 'sym::CQEIndexPipeline')",
        )
        parser.add_argument(
            "--top-k",
            type=int,
            default=5,
            help="Number of top sources to return (default: 5)",
        )
        parser.add_argument(
            "--max-depth",
            type=int,
            default=2,
            help="Maximum traversal depth (default: 2)",
        )
        add_workspace_arg(parser)
        add_json_arg(parser)

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(TDAService(), args)
        if code:
            return code

        result, code = run_service(
            service,
            "find_upstream",
            kwargs={
                "symbol": args.symbol,
                "top_k": args.top_k,
                "max_depth": args.max_depth,
            },
        )
        if code:
            return code

        def human(r):
            sources = r.get("sources") or r.get("upstream") or []
            if isinstance(r, dict) and not sources:
                # Service may return a flat dict; show keys
                print(json.dumps(r, indent=2, default=str))
                return
            print(f"Upstream sources for {args.symbol}: {len(sources)}")
            print()
            for s in sources[:args.top_k]:
                print(
                    f"  - {s.get('symbol','-')}  "
                    f"tension={s.get('tension',0):.3f} "
                    f"distance={s.get('distance','-')} "
                    f"score={s.get('score',0):.3f}"
                )

        return emit(result, args, human=human)


# ---------------------------------------------------------------------------
# quro tda escape --symbol S   (mirrors MCP quro_navigate{action:escape})
# ---------------------------------------------------------------------------

class TDAEscapeCommand(BaseCommand):
    """Escape from a sink node."""

    def get_name(self) -> str:
        return "tda escape"

    def get_help(self) -> str:
        return "Escape from a sink node via smart upstream navigation"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--symbol",
            required=True,
            help="Sink node ID to escape from",
        )
        add_workspace_arg(parser)
        add_json_arg(parser)

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(TDAService(), args)
        if code:
            return code

        result, code = run_service(
            service, "escape_sink", kwargs={"symbol": args.symbol}
        )
        if code:
            return code

        def human(r):
            print(f"Escape target: {r.get('target') or r.get('escape_target','-')}")
            print(f"  Confidence: {r.get('confidence','-')}")
            print(f"  Reason:     {r.get('reason','-')}")

        return emit(result, args, human=human)


# ---------------------------------------------------------------------------
# quro tda role --symbol S   (mirrors MCP quro_navigate{action:role})
# ---------------------------------------------------------------------------

class TDARoleCommand(BaseCommand):
    """Classify a node's energy role."""

    def get_name(self) -> str:
        return "tda role"

    def get_help(self) -> str:
        return "Classify node role (CORE_ATTRACTOR/EMITTER/SINK/TRANSIENT)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--symbol",
            required=True,
            help="Symbol ID to classify",
        )
        add_workspace_arg(parser)
        add_json_arg(parser)

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(TDAService(), args)
        if code:
            return code

        result, code = run_service(
            service, "classify_role", kwargs={"symbol": args.symbol}
        )
        if code:
            return code

        def human(r):
            role = r.get("role") or r.get("classification") or "-"
            print(f"{args.symbol}: {role}")
            if r.get("evidence"):
                print(f"  Evidence: {r['evidence']}")

        return emit(result, args, human=human)


# ---------------------------------------------------------------------------
# quro tda field --symbol S   (mirrors MCP quro_navigate{action:field})
# ---------------------------------------------------------------------------

class TDAFieldCommand(BaseCommand):
    """Get the anisotropic field vector at a symbol."""

    def get_name(self) -> str:
        return "tda field"

    def get_help(self) -> str:
        return "Get anisotropic field vector (energy/gradient) at a symbol"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--symbol",
            required=True,
            help="Symbol ID (e.g., 'sym::main')",
        )
        add_workspace_arg(parser)
        add_json_arg(parser)

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(TDAService(), args)
        if code:
            return code

        result, code = run_service(
            service, "get_field_vector", kwargs={"symbol": args.symbol}
        )
        if code:
            return code

        def human(r):
            print(f"{args.symbol}:")
            for k, v in (r or {}).items():
                if isinstance(v, (int, float)):
                    print(f"  {k}: {v:.4f}")
                else:
                    print(f"  {k}: {v}")

        return emit(result, args, human=human)


# ---------------------------------------------------------------------------
# quro tda attractors [--region R]   (mirrors MCP quro_landscape{view:attractors})
# ---------------------------------------------------------------------------

class TDAAttractorsCommand(BaseCommand):
    """Detect attractors, repellers, and saddle points."""

    def get_name(self) -> str:
        return "tda attractors"

    def get_help(self) -> str:
        return "Detect attractors, repellers, and saddle points in energy landscape"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--region",
            default="",
            help="Optional region filter (substring match on symbol id)",
        )
        add_workspace_arg(parser)
        add_json_arg(parser)

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(TDAService(), args)
        if code:
            return code

        result, code = run_service(
            service, "detect_attractors", kwargs={"region": args.region}
        )
        if code:
            return code

        def human(r):
            print(
                f"Attractors: {r.get('total_attractors',0)}  "
                f"Repellers: {r.get('total_repellers',0)}  "
                f"Saddles: {r.get('total_saddle_points',0)}"
            )
            print()
            print("Top attractors:")
            for a in r.get("attractors", [])[:10]:
                print(f"  - {a['symbol']}  gravity={a['gravity']:.3f} energy={a['energy']:.2f}")

        return emit(result, args, human=human)

"""Quro CLI Main Entry Point

@module quro.cli.main
@intent Main entry point for quro command.

Command surface (grouped form):
  - `quro cqe query`, `quro tda next`, `quro centers list`, `quro docs path`

Build/mutate operations (scan, pipeline, populate, visualize) are CLI-only;
navigation/inspection ops (next, upstream, landscape, lookup) are mirrored on
MCP as the compressed 3-tool surface.
"""

import argparse
import sys

from cli.registry import CommandRegistry
from cli.commands import (
    ScanCommand,
    CQEQueryCommand,
    CQESymbolCommand,
    CQEListCommand,
    CQEStatsCommand,
    TDAPlanCommand,
    TDAExploreCommand,
    TDACentersCommand,
    TDAPipelineCommand,
    TDAPopulateFieldsCommand,
    TDANextCommand,
    TDAUpstreamCommand,
    TDAEscapeCommand,
    TDARoleCommand,
    TDAFieldCommand,
    TDAAttractorsCommand,
    CentersListCommand,
    CentersShowCommand,
    CentersReachCommand,
    DocsPathCommand,
    DocsBuildIndexCommand,
    DocsCheckCoverageCommand,
    VisualizeCommand,
)


def register_commands():
    """Register all commands.

    Each command's get_name() is the canonical (grouped) spelling.
    """
    commands = [
        ScanCommand(),
        # cqe group
        CQEQueryCommand(),
        CQESymbolCommand(),
        CQEListCommand(),
        CQEStatsCommand(),
        # tda group
        TDAPlanCommand(),
        TDAExploreCommand(),
        TDACentersCommand(),
        TDAPipelineCommand(),
        TDAPopulateFieldsCommand(),
        TDANextCommand(),
        TDAUpstreamCommand(),
        TDAEscapeCommand(),
        TDARoleCommand(),
        TDAFieldCommand(),
        TDAAttractorsCommand(),
        # centers group
        CentersListCommand(),
        CentersShowCommand(),
        CentersReachCommand(),
        # docs group
        DocsPathCommand(),
        DocsBuildIndexCommand(),
        DocsCheckCoverageCommand(),
        # visualize
        VisualizeCommand(),
    ]
    for cmd in commands:
        CommandRegistry.register(cmd)


def main(argv=None):
    """Main CLI entry point.

    Supports grouped form: `quro cqe query ...`, `quro centers list`.
    The first two argv tokens are collapsed into a single canonical command key
    when the first token is a known group.
    """
    register_commands()

    raw_argv = list(sys.argv[1:] if argv is None else argv)

    # --- Phase 1: resolve the command key from argv -------------------------
    groups = {"cqe", "tda", "centers", "docs"}
    canonical_names = set(CommandRegistry.list_commands())

    command_key = None
    rest_argv = raw_argv

    if raw_argv:
        first = raw_argv[0]
        if first in groups and len(raw_argv) >= 2:
            # Grouped form: "cqe query" -> canonical key "cqe query"
            candidate = f"{first} {raw_argv[1]}"
            if candidate in canonical_names:
                command_key = candidate
                rest_argv = raw_argv[2:]
        if command_key is None and first in canonical_names:
            # Single-word command (scan, visualize)
            command_key = first
            rest_argv = raw_argv[1:]

    # --- Phase 2: build a parser scoped to the resolved command -------------
    parser = _build_top_parser()

    if command_key is None:
        # No (recognized) command: print top-level help.
        if raw_argv:
            parser.parse_args(raw_argv)  # let argparse emit the choice error
        parser.print_help()
        return 0

    command = CommandRegistry.get(command_key)

    # Build a parser whose prog reflects the canonical invocation.
    sub = argparse.ArgumentParser(
        prog=f"quro {command_key}",
        description=command.get_help(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    command.configure_parser(sub)

    # Honour --help for the subcommand.
    if rest_argv and rest_argv[0] in ("-h", "--help"):
        sub.print_help()
        return 0

    args = sub.parse_args(rest_argv)
    # Stash the command key in case handlers need it.
    args.command = command_key

    try:
        return command.execute(args)
    except KeyboardInterrupt:
        print("\n[Interrupted]", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"[Error] Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def _build_top_parser() -> argparse.ArgumentParser:
    """Build the top-level help/error parser (lists all commands)."""
    parser = argparse.ArgumentParser(
        prog="quro",
        description="Quro v3 - Semantic code navigation and analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  scan                        Scan workspace and build symbol index

  cqe query <start>           CQE semantic query (--mode/--tier)
  cqe symbol <name>           Get symbol details
  cqe list <symbols|categories>  List symbols or categories
  cqe stats                   Scan/index/graph statistics

  tda plan <s> <g>            Plan trajectory start->goal
  tda explore <s>             Beam-search exploration
  tda pipeline <phase>        Run TDA data pipeline phases
  tda populate-fields         Populate energy fields in registry
  tda next --from S           Best next symbols (type-aware)
  tda upstream --symbol S     Find upstream sources
  tda escape --symbol S       Escape a sink node
  tda role --symbol S         Classify energy role
  tda field --symbol S        Anisotropic field vector
  tda attractors [--region R] Detect attractors/repellers/saddles
  tda centers                 Get semantic centers

  centers list                List semantic centers (the map)
  centers show <Cn>           Show one center's detail
  centers reach <Cn>          Reachable symbols from a center

  docs path [--center Cn]     Print installed docs index path
  docs build-index            Regenerate centers/index.md
  docs check-coverage         Report core-symbol coverage per center

  visualize <type>            Generate TDA visualizations

Examples:
  quro scan
  quro tda pipeline all
  quro cqe query sym::main --tau 0.1
  quro tda plan sym::main sym::EventLogWriter --intent "find logging"
  quro centers list
  quro docs path

For command-specific help: quro <command> --help
        """,
    )
    subparsers = parser.add_subparsers(dest="command")

    seen = set()
    for name in CommandRegistry.list_commands():
        cmd = CommandRegistry.get(name)
        sp = subparsers.add_parser(name, help=cmd.get_help())
        cmd.configure_parser(sp)
        seen.add(name)

    return parser


if __name__ == "__main__":
    sys.exit(main())

"""Shared helpers for CLI command implementations.

@module quro.cli.commands._common
@intent Reduce boilerplate for service init, argument wiring, and JSON output.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from cli.base import BaseCommand


def add_workspace_arg(parser: argparse.ArgumentParser) -> None:
    """Register the standard --workspace argument."""
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace root directory (default: current directory)",
    )


def add_json_arg(parser: argparse.ArgumentParser) -> None:
    """Register the standard --json output flag."""
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )


def init_service(service, args: argparse.Namespace):
    """Initialize a service instance from a parsed Namespace's --workspace.

    Accepts either a service class (instantiated here) or an already-built
    instance. Returns (service, error_code). On error, error_code is non-zero
    and service is None; a message has already been printed to stderr.
    """
    workspace = args.workspace.resolve()
    if isinstance(service, type):
        service = service()
    try:
        service.initialize(workspace)
    except Exception as e:
        print(f"[Error] {e}", file=sys.stderr)
        return None, 1
    return service, 0


def run_service(
    service,
    method_name: str,
    *,
    kwargs: Optional[Dict[str, Any]] = None,
    error_prefix: str = "Error",
) -> Tuple[Optional[Any], int]:
    """Call a service method and wrap exceptions.

    Returns (result, exit_code). On error, exit_code is non-zero and
    result is None; a message has already been printed to stderr.
    """
    kwargs = kwargs or {}
    try:
        method = getattr(service, method_name)
        return method(**kwargs), 0
    except Exception as e:
        print(f"[{error_prefix}] {e}", file=sys.stderr)
        return None, 1


def emit(result: Any, args: argparse.Namespace, *, human: Callable[[Any], None]) -> int:
    """Emit a result either as JSON or via the provided human formatter."""
    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, default=str))
    else:
        human(result)
    return 0


class ServiceCommand(BaseCommand):
    """Convenience base: wires --workspace/--json and an `execute_service` hook.

    Subclasses implement execute_service(service, args) -> (result, human_fn).
    """

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        add_workspace_arg(parser)
        add_json_arg(parser)
        self.configure_extra(parser)

    def configure_extra(self, parser: argparse.ArgumentParser) -> None:
        """Override to add command-specific arguments."""
        pass

    def execute_service(self, service, args: argparse.Namespace):
        """Override: return (result, human_formatter). Raise to signal error."""
        raise NotImplementedError

    def execute(self, args: argparse.Namespace) -> int:
        service, code = init_service(self.service_cls(), args)
        if code:
            return code
        try:
            result, human = self.execute_service(service, args)
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1
        return emit(result, args, human=human)

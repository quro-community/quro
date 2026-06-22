"""Visualization Commands

@module quro.cli.commands.visualize
@intent CLI commands for visualization generation.
"""

import argparse
import sys
from pathlib import Path

from cli.base import BaseCommand
from service import VisualizationService


class VisualizeCommand(BaseCommand):
    """Generate visualizations."""

    def get_name(self) -> str:
        return "visualize"

    def get_help(self) -> str:
        return "Generate TDA visualizations"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "type",
            nargs="?",
            choices=["all", "energy", "gradient", "basins", "dashboard", "report"],
            default="all",
            help="Visualization type (default: all)",
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
        service = VisualizationService()
        try:
            service.initialize(workspace)
        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        # Generate visualizations
        print(f"[Visualization] Generating {args.type}...")

        try:
            if args.type == "all":
                result = service.generate_all()
                print()
                print(f"Generated {result['count']} visualizations:")
                for file in result['files']:
                    print(f"  - {file}")
                print()
                print(f"Output directory: {result['output_dir']}")

            elif args.type == "energy":
                path = service.generate_energy_heatmap()
                print(f"Generated: {path}")

            elif args.type == "gradient":
                path = service.generate_gradient_field()
                print(f"Generated: {path}")

            elif args.type == "basins":
                path = service.generate_attractor_basins()
                print(f"Generated: {path}")

            elif args.type == "dashboard":
                path = service.generate_dashboard()
                print(f"Generated: {path}")

            elif args.type == "report":
                path = service.generate_html_report()
                print(f"Generated HTML report: {path}")

        except Exception as e:
            print(f"[Error] {e}", file=sys.stderr)
            return 1

        return 0

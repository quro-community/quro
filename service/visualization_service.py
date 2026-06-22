"""Visualization Service

@module quro.service.visualization_service
@intent Visualization generation and reporting service.
"""

from pathlib import Path
from typing import Any, Dict, List

from service.base import BaseService


class VisualizationService(BaseService):
    """Visualization generation and reporting service.

    Generates field visualizations, reports, and dashboards from TDA data.
    """

    def __init__(self):
        """Initialize visualization service."""
        super().__init__()
        self._output_dir: Path | None = None

    def get_name(self) -> str:
        """Return service name."""
        return "visualization"

    def get_description(self) -> str:
        """Return service description."""
        return "TDA visualization generation and reporting"

    def initialize(self, workspace_root: Path) -> None:
        """Initialize service with workspace.

        Args:
            workspace_root: Path to workspace root directory

        Raises:
            ValueError: If workspace is invalid
            RuntimeError: If initialization fails
        """
        if not workspace_root.exists():
            raise ValueError(f"Workspace not found: {workspace_root}")

        if not workspace_root.is_dir():
            raise ValueError(f"Workspace is not a directory: {workspace_root}")

        # Check for TDA data
        tda_path = workspace_root / ".quro_context" / "tda"
        if not tda_path.exists():
            raise RuntimeError(
                f"TDA data not found at {tda_path}. "
                f"Run TDA pipeline first."
            )

        # Create output directory
        self._output_dir = workspace_root / ".quro_context" / "tda" / "visualizations"
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._workspace_root = workspace_root
        self._initialized = True

    def get_capabilities(self) -> Dict[str, Any]:
        """Return service capabilities."""
        return {
            "name": self.get_name(),
            "description": self.get_description(),
            "methods": [
                "generate_all",
                "generate_energy_heatmap",
                "generate_gradient_field",
                "generate_attractor_basins",
                "generate_dashboard",
                "generate_html_report",
                "list_visualizations",
            ],
            "initialized": self._initialized,
            "output_dir": str(self._output_dir) if self._output_dir else None,
        }

    def generate_all(self) -> Dict[str, Any]:
        """Generate all visualizations.

        Returns:
            Dictionary with paths to generated files

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        from tda.visualization.generate_plots import generate_all_plots

        generate_all_plots(self._workspace_root)

        files = list(self._output_dir.glob("*.png"))

        return {
            "output_dir": str(self._output_dir),
            "files": [f.name for f in sorted(files)],
            "count": len(files),
        }

    def generate_energy_heatmap(self) -> Path:
        """Generate energy heatmap.

        Returns:
            Path to generated file

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        from tda.visualization.generate_plots import load_tda_data
        from tda.visualization import FieldPlotter

        positions, energies, _, _, _ = load_tda_data(self._workspace_root)

        plotter = FieldPlotter(output_dir=self._output_dir)
        plotter.plot_energy_heatmap(
            positions=positions,
            energies=energies,
            title="Energy Landscape (Physics-Based Model)",
            output_filename="energy_heatmap.png",
        )

        return self._output_dir / "energy_heatmap.png"

    def generate_gradient_field(self) -> Path:
        """Generate gradient field visualization.

        Returns:
            Path to generated file

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        from tda.visualization.generate_plots import load_tda_data
        from tda.visualization import FieldPlotter

        positions, energies, _, field_directions, field_magnitudes = load_tda_data(
            self._workspace_root
        )

        plotter = FieldPlotter(output_dir=self._output_dir)
        plotter.plot_gradient_field(
            positions=positions,
            energies=energies,
            field_directions=field_directions,
            field_magnitudes=field_magnitudes,
            title="Gradient Vector Field",
            output_filename="gradient_field.png",
        )

        return self._output_dir / "gradient_field.png"

    def generate_attractor_basins(self) -> Path:
        """Generate attractor basins visualization.

        Returns:
            Path to generated file

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        from tda.visualization.generate_plots import load_tda_data
        from tda.visualization import FieldPlotter

        positions, energies, roles, _, _ = load_tda_data(self._workspace_root)

        plotter = FieldPlotter(output_dir=self._output_dir)
        plotter.plot_attractor_basins(
            positions=positions,
            energies=energies,
            roles=roles,
            title="Attractor Basins (Voronoi Diagram)",
            output_filename="attractor_basins.png",
        )

        return self._output_dir / "attractor_basins.png"

    def generate_dashboard(self) -> Path:
        """Generate summary dashboard.

        Returns:
            Path to generated file

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        from tda.visualization.generate_plots import load_tda_data
        from tda.visualization import FieldPlotter

        (
            positions,
            energies,
            roles,
            field_directions,
            field_magnitudes,
        ) = load_tda_data(self._workspace_root)

        plotter = FieldPlotter(output_dir=self._output_dir)
        plotter.create_summary_dashboard(
            positions=positions,
            energies=energies,
            roles=roles,
            field_directions=field_directions,
            field_magnitudes=field_magnitudes,
            output_filename="field_dashboard.png",
        )

        return self._output_dir / "field_dashboard.png"

    def generate_html_report(self) -> Path:
        """Generate HTML report with all visualizations.

        Returns:
            Path to generated HTML file

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        # Generate all visualizations first
        self.generate_all()

        # Create HTML report
        html_path = self._output_dir / "report.html"

        html_content = self._create_html_report()

        with open(html_path, "w") as f:
            f.write(html_content)

        return html_path

    def list_visualizations(self) -> List[str]:
        """List all generated visualizations.

        Returns:
            List of visualization filenames

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()

        files = list(self._output_dir.glob("*.png"))
        return [f.name for f in sorted(files)]

    def _create_html_report(self) -> str:
        """Create HTML report content.

        Returns:
            HTML content as string
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quro TDA Visualization Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 40px;
        }}
        .visualization {{
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .visualization img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .info {{
            background: #e7f3ff;
            padding: 15px;
            border-left: 4px solid #007bff;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <h1>Quro TDA Visualization Report</h1>

    <div class="info">
        <strong>Workspace:</strong> {self._workspace_root}<br>
        <strong>Output Directory:</strong> {self._output_dir}<br>
        <strong>Generated:</strong> {self._get_timestamp()}
    </div>

    <h2>Energy Landscape</h2>
    <div class="visualization">
        <p>Physics-based energy model showing potential wells and barriers in the semantic field.</p>
        <img src="energy_heatmap.png" alt="Energy Heatmap">
    </div>

    <h2>Gradient Vector Field</h2>
    <div class="visualization">
        <p>Vector field showing the direction and magnitude of semantic gradients.</p>
        <img src="gradient_field.png" alt="Gradient Field">
    </div>

    <h2>Attractor Basins</h2>
    <div class="visualization">
        <p>Voronoi diagram showing basins of attraction in the semantic topology.</p>
        <img src="attractor_basins.png" alt="Attractor Basins">
    </div>

    <h2>Summary Dashboard</h2>
    <div class="visualization">
        <p>Comprehensive dashboard combining all visualizations.</p>
        <img src="field_dashboard.png" alt="Field Dashboard">
    </div>

    <div class="footer">
        Generated by Quro v3 Visualization Service
    </div>
</body>
</html>
"""

    def _get_timestamp(self) -> str:
        """Get current timestamp.

        Returns:
            Formatted timestamp string
        """
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

"""Generate Field Visualizations from TDA Data

@module quro.tda.visualization.generate_plots
@intent Load TDA Phase 2.5 data and generate comprehensive field visualizations.
"""

import json
import logging
from pathlib import Path

import numpy as np
from sklearn.decomposition import PCA

from tda.visualization import FieldPlotter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_tda_data(workspace_root: Path):
    """Load TDA Phase 2.5 data.

    Args:
        workspace_root: Workspace root directory

    Returns:
        Tuple of (positions, energies, roles, field_directions, field_magnitudes)
    """
    tda_dir = workspace_root / ".quro_context" / "tda" / "phase2_5"

    # Load offline energy
    with open(tda_dir / "offline_energy.json") as f:
        energy_data = json.load(f)

    # Load manifold states for positions
    manifold_path = workspace_root / ".quro_context" / "tda" / "phase2" / "manifold_states.jsonl"
    manifold_data = {}
    with open(manifold_path) as f:
        for line in f:
            if line.strip():
                state = json.loads(line)
                symbol = state["symbol"]
                pos_data = state["manifold_position"]

                # Extract embedding
                if isinstance(pos_data, dict) and "embedding" in pos_data:
                    embedding = pos_data["embedding"]
                else:
                    embedding = pos_data

                manifold_data[symbol] = embedding

    # Extract data
    positions_3d = {}
    energies = {}
    roles = {}
    field_directions_3d = {}
    field_magnitudes = {}

    for symbol, state in energy_data["states"].items():
        if symbol not in manifold_data:
            continue

        # Get 3D position
        embedding = manifold_data[symbol]
        positions_3d[symbol] = embedding[:3] if len(embedding) >= 3 else [0, 0, 0]

        # Get energy and role
        energies[symbol] = state["total"]
        roles[symbol] = state["field_role"]

        # Get field direction (3D)
        field_directions_3d[symbol] = state["field_direction"]
        field_magnitudes[symbol] = state["field_magnitude"]

    logger.info("Loaded data for %d symbols", len(positions_3d))

    # Project to 2D using PCA
    symbols = list(positions_3d.keys())
    positions_array = np.array([positions_3d[s] for s in symbols])

    pca = PCA(n_components=2)
    positions_2d_array = pca.fit_transform(positions_array)

    positions_2d = {
        symbol: tuple(positions_2d_array[i])
        for i, symbol in enumerate(symbols)
    }

    # Project field directions to 2D
    directions_array = np.array([field_directions_3d[s] for s in symbols])
    directions_2d_array = pca.transform(directions_array)

    field_directions_2d = {
        symbol: tuple(directions_2d_array[i])
        for i, symbol in enumerate(symbols)
    }

    logger.info("Projected to 2D using PCA (explained variance: %.2f%%)",
                sum(pca.explained_variance_ratio_) * 100)

    return positions_2d, energies, roles, field_directions_2d, field_magnitudes


def generate_all_plots(workspace_root: Path):
    """Generate all field visualizations.

    Args:
        workspace_root: Workspace root directory
    """
    logger.info("Loading TDA data...")
    positions, energies, roles, field_directions, field_magnitudes = load_tda_data(workspace_root)

    # Create output directory
    output_dir = workspace_root / ".quro_context" / "tda" / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize plotter
    plotter = FieldPlotter(output_dir=output_dir)

    logger.info("Generating visualizations...")

    # 1. Energy heatmap
    logger.info("Generating energy heatmap...")
    plotter.plot_energy_heatmap(
        positions=positions,
        energies=energies,
        title="Energy Landscape (Physics-Based Model)",
        output_filename="energy_heatmap.png",
    )

    # 2. Gradient field
    logger.info("Generating gradient field...")
    plotter.plot_gradient_field(
        positions=positions,
        energies=energies,
        field_directions=field_directions,
        field_magnitudes=field_magnitudes,
        title="Gradient Vector Field",
        output_filename="gradient_field.png",
    )

    # 3. Attractor basins
    logger.info("Generating attractor basins...")
    plotter.plot_attractor_basins(
        positions=positions,
        energies=energies,
        roles=roles,
        title="Attractor Basins (Voronoi Diagram)",
        output_filename="attractor_basins.png",
    )

    # 4. Summary dashboard
    logger.info("Generating summary dashboard...")
    plotter.create_summary_dashboard(
        positions=positions,
        energies=energies,
        roles=roles,
        field_directions=field_directions,
        field_magnitudes=field_magnitudes,
        output_filename="field_dashboard.png",
    )

    logger.info("All visualizations generated in %s", output_dir)
    logger.info("Files:")
    for file in sorted(output_dir.glob("*.png")):
        logger.info("  - %s", file.name)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        workspace_root = Path(sys.argv[1])
    else:
        workspace_root = Path.cwd()

    generate_all_plots(workspace_root)

"""Field Plotter — Energy Landscape Visualization

@module quro.tda.visualization.field_plotter
@intent Visualize energy landscape, gradient fields, attractor basins, and trajectories.
        Implements Phase 4 of Design 85 - Field Recalibration.

        Visualization types:
        1. Energy heatmap (2D projection via PCA/t-SNE)
        2. Gradient vector field
        3. Attractor basins (Voronoi diagram)
        4. Trajectory overlay
        5. Coherence visualization

        Output: PNG/SVG files in .quro_context/tda/visualizations/
"""

import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch
from matplotlib.collections import LineCollection
from scipy.spatial import Voronoi, voronoi_plot_2d

logger = logging.getLogger(__name__)


class FieldPlotter:
    """Visualize energy landscape and field dynamics.

    Provides multiple visualization modes for understanding the physics-based
    navigation system.
    """

    def __init__(
        self,
        output_dir: Path,
        figsize: Tuple[int, int] = (12, 10),
        dpi: int = 150,
    ):
        """Initialize field plotter.

        Args:
            output_dir: Output directory for visualizations
            figsize: Figure size in inches (width, height)
            dpi: Resolution in dots per inch
        """
        self.output_dir = output_dir
        self.figsize = figsize
        self.dpi = dpi

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "FieldPlotter initialized with output_dir=%s",
            self.output_dir,
        )

    def plot_energy_heatmap(
        self,
        positions: Dict[str, Tuple[float, float]],
        energies: Dict[str, float],
        title: str = "Energy Landscape",
        output_filename: str = "energy_heatmap.png",
    ) -> Path:
        """Plot energy heatmap using 2D positions.

        Args:
            positions: Dict mapping symbol → (x, y) position
            energies: Dict mapping symbol → energy value
            title: Plot title
            output_filename: Output filename

        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        # Extract data
        symbols = list(positions.keys())
        x = [positions[s][0] for s in symbols]
        y = [positions[s][1] for s in symbols]
        energy_values = [energies.get(s, 0.0) for s in symbols]

        # Create scatter plot with energy as color
        scatter = ax.scatter(
            x, y,
            c=energy_values,
            cmap='RdYlGn_r',  # Red (low) → Yellow → Green (high)
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidth=0.5,
        )

        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Energy', rotation=270, labelpad=20)

        # Labels and title
        ax.set_xlabel('Position X')
        ax.set_ylabel('Position Y')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)

        # Save
        output_path = self.output_dir / output_filename
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        logger.info("Saved energy heatmap to %s", output_path)
        return output_path

    def plot_gradient_field(
        self,
        positions: Dict[str, Tuple[float, float]],
        energies: Dict[str, float],
        field_directions: Dict[str, Tuple[float, float]],
        field_magnitudes: Dict[str, float],
        title: str = "Gradient Vector Field",
        output_filename: str = "gradient_field.png",
    ) -> Path:
        """Plot gradient vector field.

        Args:
            positions: Dict mapping symbol → (x, y) position
            energies: Dict mapping symbol → energy value
            field_directions: Dict mapping symbol → (dx, dy) direction
            field_magnitudes: Dict mapping symbol → magnitude
            title: Plot title
            output_filename: Output filename

        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        # Extract data
        symbols = list(positions.keys())
        x = [positions[s][0] for s in symbols]
        y = [positions[s][1] for s in symbols]
        energy_values = [energies.get(s, 0.0) for s in symbols]

        # Plot energy as background
        scatter = ax.scatter(
            x, y,
            c=energy_values,
            cmap='RdYlGn_r',
            s=50,
            alpha=0.5,
            edgecolors='none',
        )

        # Plot gradient vectors
        for symbol in symbols:
            if symbol not in field_directions or symbol not in field_magnitudes:
                continue

            pos = positions[symbol]
            direction = field_directions[symbol]
            magnitude = field_magnitudes[symbol]

            # Scale arrow by magnitude
            scale = min(1.0, magnitude / 5.0)  # Normalize to [0, 1]
            dx = direction[0] * scale * 0.5
            dy = direction[1] * scale * 0.5

            # Draw arrow
            ax.arrow(
                pos[0], pos[1],
                dx, dy,
                head_width=0.1,
                head_length=0.1,
                fc='blue',
                ec='blue',
                alpha=0.6,
                linewidth=1.5,
            )

        # Colorbar
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Energy', rotation=270, labelpad=20)

        # Labels and title
        ax.set_xlabel('Position X')
        ax.set_ylabel('Position Y')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)

        # Save
        output_path = self.output_dir / output_filename
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        logger.info("Saved gradient field to %s", output_path)
        return output_path

    def plot_attractor_basins(
        self,
        positions: Dict[str, Tuple[float, float]],
        energies: Dict[str, float],
        roles: Dict[str, str],
        title: str = "Attractor Basins",
        output_filename: str = "attractor_basins.png",
    ) -> Path:
        """Plot attractor basins using Voronoi diagram.

        Args:
            positions: Dict mapping symbol → (x, y) position
            energies: Dict mapping symbol → energy value
            roles: Dict mapping symbol → role (attractor, repeller, etc.)
            title: Plot title
            output_filename: Output filename

        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        # Extract attractors
        attractors = [s for s, r in roles.items() if r == "attractor"]
        if not attractors:
            logger.warning("No attractors found, skipping basin plot")
            return None

        attractor_positions = np.array([positions[s] for s in attractors])

        # Create Voronoi diagram
        vor = Voronoi(attractor_positions)

        # Plot Voronoi regions
        voronoi_plot_2d(
            vor,
            ax=ax,
            show_vertices=False,
            line_colors='blue',
            line_width=2,
            line_alpha=0.6,
            point_size=0,
        )

        # Plot all nodes with energy coloring
        symbols = list(positions.keys())
        x = [positions[s][0] for s in symbols]
        y = [positions[s][1] for s in symbols]
        energy_values = [energies.get(s, 0.0) for s in symbols]

        scatter = ax.scatter(
            x, y,
            c=energy_values,
            cmap='RdYlGn_r',
            s=50,
            alpha=0.7,
            edgecolors='black',
            linewidth=0.5,
        )

        # Highlight attractors
        attractor_x = [positions[s][0] for s in attractors]
        attractor_y = [positions[s][1] for s in attractors]
        ax.scatter(
            attractor_x, attractor_y,
            c='red',
            s=200,
            marker='*',
            edgecolors='black',
            linewidth=2,
            label='Attractors',
            zorder=10,
        )

        # Colorbar
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Energy', rotation=270, labelpad=20)

        # Labels and title
        ax.set_xlabel('Position X')
        ax.set_ylabel('Position Y')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Save
        output_path = self.output_dir / output_filename
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        logger.info("Saved attractor basins to %s", output_path)
        return output_path

    def plot_trajectory(
        self,
        positions: Dict[str, Tuple[float, float]],
        energies: Dict[str, float],
        trajectory_path: List[str],
        trajectory_energies: List[float],
        title: str = "Trajectory Visualization",
        output_filename: str = "trajectory.png",
    ) -> Path:
        """Plot trajectory overlay on energy landscape.

        Args:
            positions: Dict mapping symbol → (x, y) position
            energies: Dict mapping symbol → energy value
            trajectory_path: List of symbol IDs forming trajectory
            trajectory_energies: List of energy values along trajectory
            title: Plot title
            output_filename: Output filename

        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        # Plot energy landscape
        symbols = list(positions.keys())
        x = [positions[s][0] for s in symbols]
        y = [positions[s][1] for s in symbols]
        energy_values = [energies.get(s, 0.0) for s in symbols]

        scatter = ax.scatter(
            x, y,
            c=energy_values,
            cmap='RdYlGn_r',
            s=50,
            alpha=0.3,
            edgecolors='none',
        )

        # Plot trajectory
        traj_x = [positions[s][0] for s in trajectory_path if s in positions]
        traj_y = [positions[s][1] for s in trajectory_path if s in positions]

        # Color trajectory by energy
        points = np.array([traj_x, traj_y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)

        lc = LineCollection(
            segments,
            cmap='viridis',
            linewidth=3,
            alpha=0.8,
        )
        lc.set_array(np.array(trajectory_energies))
        ax.add_collection(lc)

        # Mark start and end
        if traj_x and traj_y:
            ax.scatter(
                traj_x[0], traj_y[0],
                c='green',
                s=300,
                marker='o',
                edgecolors='black',
                linewidth=2,
                label='Start',
                zorder=10,
            )
            ax.scatter(
                traj_x[-1], traj_y[-1],
                c='red',
                s=300,
                marker='X',
                edgecolors='black',
                linewidth=2,
                label='End',
                zorder=10,
            )

        # Colorbar for background
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Energy', rotation=270, labelpad=20)

        # Labels and title
        ax.set_xlabel('Position X')
        ax.set_ylabel('Position Y')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Save
        output_path = self.output_dir / output_filename
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        logger.info("Saved trajectory to %s", output_path)
        return output_path

    def plot_coherence_analysis(
        self,
        trajectory_path: List[str],
        direction_vectors: List[List[float]],
        coherence_scores: List[float],
        title: str = "Trajectory Coherence Analysis",
        output_filename: str = "coherence_analysis.png",
    ) -> Path:
        """Plot trajectory coherence analysis.

        Args:
            trajectory_path: List of symbol IDs
            direction_vectors: List of direction vectors (2D projections)
            coherence_scores: List of coherence scores at each step
            title: Plot title
            output_filename: Output filename

        Returns:
            Path to saved plot
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), dpi=self.dpi)

        # Plot 1: Direction vectors
        steps = list(range(len(direction_vectors)))
        dx = [v[0] for v in direction_vectors]
        dy = [v[1] for v in direction_vectors]

        ax1.plot(steps, dx, 'b-o', label='X direction', linewidth=2)
        ax1.plot(steps, dy, 'r-o', label='Y direction', linewidth=2)
        ax1.set_xlabel('Step')
        ax1.set_ylabel('Direction Component')
        ax1.set_title('Direction Vectors Along Trajectory')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Coherence scores
        ax2.plot(steps, coherence_scores, 'g-o', linewidth=2)
        ax2.axhline(y=0.5, color='r', linestyle='--', label='Threshold')
        ax2.set_xlabel('Step')
        ax2.set_ylabel('Coherence Score')
        ax2.set_title('Coherence Score Along Trajectory')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Save
        output_path = self.output_dir / output_filename
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        logger.info("Saved coherence analysis to %s", output_path)
        return output_path

    def create_summary_dashboard(
        self,
        positions: Dict[str, Tuple[float, float]],
        energies: Dict[str, float],
        roles: Dict[str, str],
        field_directions: Dict[str, Tuple[float, float]],
        field_magnitudes: Dict[str, float],
        output_filename: str = "field_dashboard.png",
    ) -> Path:
        """Create comprehensive dashboard with multiple views.

        Args:
            positions: Dict mapping symbol → (x, y) position
            energies: Dict mapping symbol → energy value
            roles: Dict mapping symbol → role
            field_directions: Dict mapping symbol → (dx, dy) direction
            field_magnitudes: Dict mapping symbol → magnitude
            output_filename: Output filename

        Returns:
            Path to saved dashboard
        """
        fig = plt.figure(figsize=(20, 15), dpi=self.dpi)

        # Create 2x2 grid
        gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

        # 1. Energy heatmap
        ax1 = fig.add_subplot(gs[0, 0])
        symbols = list(positions.keys())
        x = [positions[s][0] for s in symbols]
        y = [positions[s][1] for s in symbols]
        energy_values = [energies.get(s, 0.0) for s in symbols]
        scatter1 = ax1.scatter(x, y, c=energy_values, cmap='RdYlGn_r', s=100, alpha=0.7)
        ax1.set_title('Energy Landscape')
        ax1.set_xlabel('Position X')
        ax1.set_ylabel('Position Y')
        ax1.grid(True, alpha=0.3)
        plt.colorbar(scatter1, ax=ax1, label='Energy')

        # 2. Gradient field
        ax2 = fig.add_subplot(gs[0, 1])
        scatter2 = ax2.scatter(x, y, c=energy_values, cmap='RdYlGn_r', s=50, alpha=0.5)
        for symbol in symbols[:50]:  # Limit arrows for clarity
            if symbol not in field_directions:
                continue
            pos = positions[symbol]
            direction = field_directions[symbol]
            magnitude = field_magnitudes.get(symbol, 0.0)
            scale = min(1.0, magnitude / 5.0) * 0.5
            ax2.arrow(pos[0], pos[1], direction[0]*scale, direction[1]*scale,
                     head_width=0.1, fc='blue', ec='blue', alpha=0.6)
        ax2.set_title('Gradient Vector Field')
        ax2.set_xlabel('Position X')
        ax2.set_ylabel('Position Y')
        ax2.grid(True, alpha=0.3)

        # 3. Role distribution
        ax3 = fig.add_subplot(gs[1, 0])
        role_counts = {}
        for role in roles.values():
            role_counts[role] = role_counts.get(role, 0) + 1
        ax3.bar(role_counts.keys(), role_counts.values(), color=['red', 'blue', 'green', 'gray'])
        ax3.set_title('Node Role Distribution')
        ax3.set_xlabel('Role')
        ax3.set_ylabel('Count')
        ax3.grid(True, alpha=0.3, axis='y')

        # 4. Energy distribution histogram
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.hist(energy_values, bins=30, color='skyblue', edgecolor='black', alpha=0.7)
        ax4.axvline(np.mean(energy_values), color='red', linestyle='--', label=f'Mean: {np.mean(energy_values):.2f}')
        ax4.set_title('Energy Distribution')
        ax4.set_xlabel('Energy')
        ax4.set_ylabel('Frequency')
        ax4.legend()
        ax4.grid(True, alpha=0.3, axis='y')

        # Save
        output_path = self.output_dir / output_filename
        plt.savefig(output_path)
        plt.close()

        logger.info("Saved field dashboard to %s", output_path)
        return output_path

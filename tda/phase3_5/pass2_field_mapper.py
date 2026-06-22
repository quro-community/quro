"""
Pass 2: Manifold Density & Field Mapper

Computes semantic density, curvature, and stress fields across codebase.
"""

from typing import Dict
from .pass1_field_aggregator import GridCell


class ManifoldFieldMapper:
    """Computes semantic fields across codebase."""

    def __init__(self):
        self.density_field: Dict[str, float] = {}
        self.curvature_field: Dict[str, float] = {}
        self.stress_field: Dict[str, float] = {}

    def compute_fields(self, grid: Dict[str, GridCell]) -> None:
        """Compute all semantic fields.

        Args:
            grid: Dictionary of grid cells from Pass 1
        """
        print("[Phase-3.5 Pass-2] Computing semantic fields...")

        for path, cell in grid.items():
            metrics = cell.get_metrics()

            # Compute density
            self.density_field[path] = self._compute_density(metrics)

            # Compute curvature
            self.curvature_field[path] = self._compute_curvature(cell)

            # Compute stress
            self.stress_field[path] = self._compute_stress(cell)

        # Normalize fields to [0,1]
        self._normalize_field(self.density_field)
        self._normalize_field(self.curvature_field)
        self._normalize_field(self.stress_field)

        print(f"[Phase-3.5 Pass-2] Computed fields for {len(grid)} regions")

    def _compute_density(self, metrics: Dict) -> float:
        """Compute semantic density.

        density = (avg_centrality × total_frequency) / symbol_count
        """
        if metrics["symbol_count"] == 0:
            return 0.0

        avg_centrality = metrics["avg_centrality"]
        total_frequency = metrics["total_frequency"]
        symbol_count = metrics["symbol_count"]

        # Density: weighted centrality per symbol
        return (avg_centrality * total_frequency) / max(1, symbol_count)

    def _compute_curvature(self, cell: GridCell) -> float:
        """Compute semantic curvature.

        curvature = variance(betweenness) × avg(clustering_coeff)
        """
        if not cell.symbols:
            return 0.0

        betweenness_values = [s.topology.betweenness for s in cell.symbols]
        clustering_values = [s.topology.clustering_coeff for s in cell.symbols]

        # Variance of betweenness
        mean_betweenness = sum(betweenness_values) / len(betweenness_values)
        variance = sum((b - mean_betweenness) ** 2 for b in betweenness_values) / len(betweenness_values)

        # Average clustering
        avg_clustering = sum(clustering_values) / len(clustering_values)

        return variance * avg_clustering

    def _compute_stress(self, cell: GridCell) -> float:
        """Compute manifold stress.

        stress = (coupling_pressure × entry_variance) / tau_persistence
        """
        if not cell.symbols:
            return 0.0

        total_stress = 0.0
        for s in cell.symbols:
            # Coupling pressure: number of category couplings
            coupling_pressure = len(s.category_coupling)

            # Entry variance
            entry_variance = s.stability.entry_variance

            # Tau persistence
            tau_persistence = max(0.01, s.stability.tau_persistence)  # Avoid division by zero

            # Stress formula
            stress = (coupling_pressure * entry_variance) / tau_persistence
            total_stress += stress

        return total_stress / len(cell.symbols)

    def _normalize_field(self, field: Dict[str, float]) -> None:
        """Normalize field values to [0,1]."""
        if not field:
            return

        max_value = max(field.values())
        if max_value > 0:
            for key in field:
                field[key] = field[key] / max_value

    def get_field_maps(self) -> Dict[str, Dict[str, float]]:
        """Get all field maps."""
        return {
            "density": self.density_field,
            "curvature": self.curvature_field,
            "stress": self.stress_field,
        }

    def get_statistics(self) -> Dict:
        """Get field statistics."""
        return {
            "avg_density": sum(self.density_field.values()) / len(self.density_field) if self.density_field else 0,
            "avg_curvature": sum(self.curvature_field.values()) / len(self.curvature_field) if self.curvature_field else 0,
            "avg_stress": sum(self.stress_field.values()) / len(self.stress_field) if self.stress_field else 0,
            "max_density_region": max(self.density_field.items(), key=lambda x: x[1])[0] if self.density_field else None,
            "max_stress_region": max(self.stress_field.items(), key=lambda x: x[1])[0] if self.stress_field else None,
        }

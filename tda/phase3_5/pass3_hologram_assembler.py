"""
Pass 3: Void Detector & Hologram Assembler

Detects semantic voids and assembles the complete holographic view.
"""

from typing import List, Dict
from pathlib import Path

from ..phase2.schema import SymbolManifoldState
from . import (
    CodebaseHologram,
    GlobalMetrics,
    SemanticFoldingRegion,
    VoidRegion,
    ArchitectureState,
    NavigationGuidance,
    FieldStatistics,
    MajorAttractor,
)
from .pass1_field_aggregator import GridCell
from .pass2_field_mapper import ManifoldFieldMapper


class HologramAssembler:
    """Assembles the complete codebase holographic view."""

    def __init__(self):
        pass

    def assemble(
        self,
        grid: Dict[str, GridCell],
        field_mapper: ManifoldFieldMapper,
        manifold_states: List[SymbolManifoldState],
    ) -> CodebaseHologram:
        """Assemble complete holographic view.

        Args:
            grid: Grid cells from Pass 1
            field_mapper: Field mapper from Pass 2
            manifold_states: Original manifold states

        Returns:
            Complete CodebaseHologram
        """
        print("[Phase-3.5 Pass-3] Assembling holographic view...")

        # Compute global metrics
        global_metrics = self._compute_global_metrics(grid, field_mapper)

        # Get field maps
        field_maps = field_mapper.get_field_maps()

        # Detect semantic folding regions
        folding_regions = self._detect_folding_regions(grid, field_mapper)

        # Detect void regions
        void_regions = self._detect_void_regions(grid, field_mapper)

        # Compute architecture state
        architecture_state = self._compute_architecture_state(grid, field_mapper)

        # Generate navigation guidance
        navigation_guidance = self._generate_navigation_guidance(
            manifold_states, grid, field_mapper
        )

        # Compute field statistics
        field_statistics = self._compute_field_statistics(manifold_states)

        # Get major attractors
        major_attractors = self._get_major_attractors(manifold_states)

        hologram = CodebaseHologram(
            global_metrics=global_metrics,
            field_maps=field_maps,
            semantic_folding_regions=folding_regions,
            void_regions=void_regions,
            architecture_state=architecture_state,
            navigation_guidance=navigation_guidance,
            field_statistics=field_statistics,
            major_attractors=major_attractors,
        )

        print("[Phase-3.5 Pass-3] Hologram assembled")
        return hologram

    def _compute_field_statistics(
        self, manifold_states: List[SymbolManifoldState]
    ) -> FieldStatistics:
        """Compute global field statistics from manifold states."""
        import numpy as np

        # Extract energies
        energies = [
            sms.energy["total"]
            for sms in manifold_states
            if sms.energy is not None
        ]

        if not energies:
            return FieldStatistics(
                energy_distribution={"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0},
                attractor_count=0,
                repeller_count=0,
                saddle_count=0,
            )

        # Count field roles
        attractor_count = sum(
            1 for sms in manifold_states if sms.field_role == "stable_attractor"
        )
        repeller_count = sum(
            1 for sms in manifold_states if sms.field_role == "unstable_repeller"
        )
        saddle_count = sum(
            1 for sms in manifold_states if sms.field_role == "saddle_point"
        )

        return FieldStatistics(
            energy_distribution={
                "mean": float(np.mean(energies)),
                "std": float(np.std(energies)),
                "min": float(np.min(energies)),
                "max": float(np.max(energies)),
            },
            attractor_count=attractor_count,
            repeller_count=repeller_count,
            saddle_count=saddle_count,
        )

    def _get_major_attractors(
        self, manifold_states: List[SymbolManifoldState]
    ) -> List[MajorAttractor]:
        """Get top 5 major attractors."""
        # Filter attractors
        attractors = [
            sms
            for sms in manifold_states
            if sms.field_role == "stable_attractor" and sms.energy is not None
        ]

        # Sort by energy (ascending - lower energy = deeper basin)
        attractors.sort(key=lambda sms: sms.energy["total"])

        # Take top 5
        major_attractors = []
        for sms in attractors[:5]:
            # Count neighbors (simplified: use category coupling size as proxy)
            basin_size = len(sms.category_coupling) if sms.category_coupling else 0

            major_attractors.append(
                MajorAttractor(
                    symbol=sms.symbol,
                    energy=sms.energy["total"],
                    basin_depth=1.0 - sms.energy["total"],
                    basin_size=basin_size,
                )
            )

        return major_attractors

    def _compute_global_metrics(
        self, grid: Dict[str, GridCell], field_mapper: ManifoldFieldMapper
    ) -> GlobalMetrics:
        """Compute global codebase metrics."""
        # Center of mass: region with highest density
        density_field = field_mapper.density_field
        center_of_mass = max(density_field.items(), key=lambda x: x[1])[0] if density_field else "unknown"

        # Dominant axis: most common category coupling
        # For now, use a placeholder
        dominant_axis = "async ↔ database"

        # Coherence: inverse of fragmentation
        coherence = self._compute_coherence(grid)

        # Fragmentation: variance in density
        fragmentation = self._compute_fragmentation(field_mapper.density_field)

        # Coupling pressure: average stress
        coupling_pressure = sum(field_mapper.stress_field.values()) / len(field_mapper.stress_field) if field_mapper.stress_field else 0

        return GlobalMetrics(
            center_of_mass=center_of_mass,
            dominant_axis=dominant_axis,
            coherence=coherence,
            fragmentation=fragmentation,
            coupling_pressure=coupling_pressure,
        )

    def _compute_coherence(self, grid: Dict[str, GridCell]) -> float:
        """Compute overall coherence [0,1]."""
        if not grid:
            return 0.0

        # Coherence: average stability across all symbols
        total_stability = 0.0
        total_symbols = 0

        for cell in grid.values():
            for symbol in cell.symbols:
                total_stability += symbol.stability.tau_persistence
                total_symbols += 1

        return total_stability / total_symbols if total_symbols > 0 else 0.0

    def _compute_fragmentation(self, density_field: Dict[str, float]) -> float:
        """Compute fragmentation [0,1]."""
        if not density_field:
            return 0.0

        # Fragmentation: coefficient of variation in density
        values = list(density_field.values())
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = variance ** 0.5

        # Coefficient of variation (normalized)
        return min(1.0, std_dev / mean if mean > 0 else 0.0)

    def _detect_folding_regions(
        self, grid: Dict[str, GridCell], field_mapper: ManifoldFieldMapper
    ) -> List[SemanticFoldingRegion]:
        """Detect semantic folding regions (high complexity)."""
        folding_regions = []

        # High folding: high curvature + high density
        for path, curvature in field_mapper.curvature_field.items():
            density = field_mapper.density_field.get(path, 0.0)

            if curvature > 0.7 and density > 0.7:
                complexity_score = (curvature + density) / 2.0

                folding_regions.append(
                    SemanticFoldingRegion(
                        region=path,
                        fold_type="high-compression",
                        meaning="Multiple concepts collapsed into single manifold region",
                        complexity_score=complexity_score,
                    )
                )

        return folding_regions

    def _detect_void_regions(
        self, grid: Dict[str, GridCell], field_mapper: ManifoldFieldMapper
    ) -> List[VoidRegion]:
        """Detect semantic void regions (low activity)."""
        void_regions = []

        # Void: low density + low frequency
        for path, density in field_mapper.density_field.items():
            cell = grid[path]
            metrics = cell.get_metrics()

            if density < 0.3 and metrics["total_frequency"] < 100:
                # Estimate code lines (rough heuristic)
                code_lines = metrics["symbol_count"] * 20  # Assume 20 lines per symbol

                void_score = 1.0 - density

                recommendation = "candidate_for_removal" if void_score > 0.9 else "review_needed"

                void_regions.append(
                    VoidRegion(
                        path=path,
                        void_score=void_score,
                        code_lines=code_lines,
                        visit_count=metrics["total_frequency"],
                        recommendation=recommendation,
                    )
                )

        return void_regions

    def _compute_architecture_state(
        self, grid: Dict[str, GridCell], field_mapper: ManifoldFieldMapper
    ) -> ArchitectureState:
        """Compute overall architecture health state."""
        coherence = self._compute_coherence(grid)
        fragmentation = self._compute_fragmentation(field_mapper.density_field)
        coupling_pressure = sum(field_mapper.stress_field.values()) / len(field_mapper.stress_field) if field_mapper.stress_field else 0

        # Overall health assessment
        health_score = coherence - fragmentation - coupling_pressure
        if health_score > 0.5:
            overall_health = "excellent"
        elif health_score > 0.2:
            overall_health = "good"
        elif health_score > -0.2:
            overall_health = "fair"
        else:
            overall_health = "poor"

        return ArchitectureState(
            coherence=coherence,
            fragmentation=fragmentation,
            coupling_pressure=coupling_pressure,
            overall_health=overall_health,
        )

    def _generate_navigation_guidance(
        self,
        manifold_states: List[SymbolManifoldState],
        grid: Dict[str, GridCell],
        field_mapper: ManifoldFieldMapper,
    ) -> NavigationGuidance:
        """Generate navigation guidance for LLM agents."""
        # Recommended entry points: high centrality + high stability
        entry_points = []
        for sms in manifold_states:
            if sms.topology.centrality > 0.7 and sms.stability.tau_persistence > 0.7:
                entry_points.append(sms.symbol)

        # High risk zones: high stress regions
        high_risk_zones = [
            path for path, stress in field_mapper.stress_field.items() if stress > 0.8
        ]

        # Safe refactor zones: low stress + low density
        safe_refactor_zones = [
            path
            for path in grid.keys()
            if field_mapper.stress_field.get(path, 0) < 0.3
            and field_mapper.density_field.get(path, 0) < 0.5
        ]

        return NavigationGuidance(
            recommended_entry_points=entry_points[:10],  # Top 10
            high_risk_zones=high_risk_zones,
            safe_refactor_zones=safe_refactor_zones,
        )

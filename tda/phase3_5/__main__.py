"""
Phase-3.5 Main Orchestrator

Coordinates the three-pass holographic field construction pipeline,
followed by Phase 3.6 semantic center detection.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

from ..phase2.schema import SymbolManifoldState
from .pass1_field_aggregator import SymbolFieldAggregator
from .pass2_field_mapper import ManifoldFieldMapper
from .pass3_hologram_assembler import HologramAssembler
from .pass4_center_detection import CenterDetector
from .pass5_inter_center_graph import InterCenterGraphBuilder
from . import CenterGraph, StructuralCouplingReport, get_git_hash
from typing import Optional


class Phase35Orchestrator:
    """Orchestrates the three-pass Phase-3.5 holographic field pipeline + Phase 3.6 centers."""

    def __init__(self, manifold_states_path: Path, output_path: Path, centers_output_path: Optional[Path] = None):
        self.manifold_states_path = manifold_states_path
        self.output_path = output_path
        self.centers_output_path = centers_output_path
        self.workspace_root = Path.cwd()

    def run(self) -> None:
        """Run the complete Phase-3.5 pipeline."""
        start_time = datetime.now()
        print(f"[Phase-3.5] Starting holographic field construction pipeline...")
        print(f"[Phase-3.5] Input: {self.manifold_states_path}")
        print(f"[Phase-3.5] Output: {self.output_path}")
        print()

        # Load manifold states
        manifold_states = self._load_manifold_states()
        print(f"[Phase-3.5] Loaded {len(manifold_states)} manifold states")
        print()

        # Pass 1: Symbol Field Aggregation
        print("=" * 60)
        print("PASS 1: SYMBOL FIELD AGGREGATION")
        print("=" * 60)
        aggregator = SymbolFieldAggregator(self.workspace_root)
        grid = aggregator.aggregate(manifold_states)
        print()
        print("Pass 1 Statistics:")
        for key, value in aggregator.get_statistics().items():
            print(f"  {key}: {value}")
        print()

        # Pass 2: Manifold Field Mapping
        print("=" * 60)
        print("PASS 2: MANIFOLD FIELD MAPPING")
        print("=" * 60)
        field_mapper = ManifoldFieldMapper()
        field_mapper.compute_fields(grid)
        print()
        print("Pass 2 Statistics:")
        for key, value in field_mapper.get_statistics().items():
            print(f"  {key}: {value}")
        print()

        # Pass 3: Hologram Assembly
        print("=" * 60)
        print("PASS 3: HOLOGRAM ASSEMBLY")
        print("=" * 60)
        assembler = HologramAssembler()
        hologram = assembler.assemble(grid, field_mapper, manifold_states)
        print()

        # Write output
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, 'w') as f:
            f.write(hologram.model_dump_json(indent=2))

        print(f"[Phase-3.5] Wrote hologram to {self.output_path}")
        print()

        # Print hologram summary
        self._print_hologram_summary(hologram)

        # =====================================================================
        # Phase 3.6: Semantic Center Detection
        # =====================================================================

        print("=" * 60)
        print("PHASE 3.6: SEMANTIC CENTER DETECTION")
        print("=" * 60)
        print()

        # Pass 4: Center Detection
        print("=" * 60)
        print("PASS 4: CENTER DETECTION (BASIN PARTITIONING)")
        print("=" * 60)
        field_data_path = self.manifold_states_path.parent.parent
        center_detector = CenterDetector(self.workspace_root)
        centers = center_detector.detect_centers(manifold_states, field_data_path)
        basin_map = center_detector.get_basin_map()
        print(f"[Pass 4] Detected {len(centers)} semantic centers")
        print()

        # Pass 5: Inter-Center Graph
        print("=" * 60)
        print("PASS 5: INTER-CENTER GRAPH")
        print("=" * 60)
        graph_builder = InterCenterGraphBuilder(self.workspace_root)
        centers = graph_builder.build(centers, basin_map, field_data_path)
        print(f"[Pass 5] Built inter-center graph")
        for c in centers:
            print(f"  Center {c.id}: size={c.size}, archetype={c.topology.pattern}, connected={len(c.topology.connected_centers)}")
        print()

        # Build Structural Coupling Report
        structural_clusters = center_detector.get_structural_clusters()
        coupled_centers_list = center_detector.get_coupled_centers()
        cross_module_count = sum(1 for cluster in structural_clusters if cluster.is_cross_module)

        structural_coupling_report = StructuralCouplingReport(
            clusters=structural_clusters,
            coupled_centers=coupled_centers_list,
            total_symbols=len(manifold_states),
            cross_module_clusters=cross_module_count,
        )

        # Build CenterGraph output
        total_symbols = len(manifold_states)
        assigned_symbols = len(basin_map)
        git_hash = get_git_hash(self.workspace_root)
        center_graph = CenterGraph(
            centers=centers,
            total_symbols=total_symbols,
            unassigned_symbols=total_symbols - assigned_symbols,
            partition_coverage=round(assigned_symbols / total_symbols, 3) if total_symbols > 0 else 0.0,
            structural_coupling=structural_coupling_report,
            git_hash=git_hash,
        )

        # Write centers output
        if self.centers_output_path:
            self.centers_output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.centers_output_path, 'w') as f:
                f.write(center_graph.model_dump_json(indent=2))
            print(f"[Phase-3.6] Wrote semantic centers to {self.centers_output_path}")
            print()

        # Summary
        duration = (datetime.now() - start_time).total_seconds()
        print("=" * 60)
        print("PHASE-3.5 + PHASE-3.6 COMPLETE")
        print("=" * 60)
        print(f"Duration: {duration:.2f} seconds")
        print(f"Hologram Output: {self.output_path}")
        if self.centers_output_path:
            print(f"Centers Output: {self.centers_output_path}")
        print()

    def _load_manifold_states(self) -> list:
        """Load manifold states from Phase-2 output."""
        manifold_states = []
        with open(self.manifold_states_path) as f:
            for line in f:
                data = json.loads(line)
                sms = SymbolManifoldState(**data)
                manifold_states.append(sms)
        return manifold_states

    def _print_hologram_summary(self, hologram) -> None:
        """Print hologram summary."""
        print("=" * 60)
        print("HOLOGRAM SUMMARY")
        print("=" * 60)

        print("Global Metrics:")
        print(f"  Center of Mass: {hologram.global_metrics.center_of_mass}")
        print(f"  Dominant Axis: {hologram.global_metrics.dominant_axis}")
        print(f"  Coherence: {hologram.global_metrics.coherence:.3f}")
        print(f"  Fragmentation: {hologram.global_metrics.fragmentation:.3f}")
        print(f"  Coupling Pressure: {hologram.global_metrics.coupling_pressure:.3f}")
        print()

        print("Architecture State:")
        print(f"  Overall Health: {hologram.architecture_state.overall_health}")
        print(f"  Coherence: {hologram.architecture_state.coherence:.3f}")
        print(f"  Fragmentation: {hologram.architecture_state.fragmentation:.3f}")
        print(f"  Coupling Pressure: {hologram.architecture_state.coupling_pressure:.3f}")
        print()

        print(f"Semantic Folding Regions: {len(hologram.semantic_folding_regions)}")
        for region in hologram.semantic_folding_regions[:5]:
            print(f"  {region.region} (complexity: {region.complexity_score:.3f})")
        print()

        print(f"Void Regions: {len(hologram.void_regions)}")
        for void in hologram.void_regions[:5]:
            print(f"  {void.path} (void score: {void.void_score:.3f})")
        print()

        print("Navigation Guidance:")
        print(f"  Recommended Entry Points: {len(hologram.navigation_guidance.recommended_entry_points)}")
        for entry in hologram.navigation_guidance.recommended_entry_points[:5]:
            print(f"    {entry}")
        print(f"  High Risk Zones: {len(hologram.navigation_guidance.high_risk_zones)}")
        print(f"  Safe Refactor Zones: {len(hologram.navigation_guidance.safe_refactor_zones)}")
        print()


def main():
    """CLI entry point."""
    # Default paths
    workspace_root = Path.cwd()
    manifold_states_path = workspace_root / ".quro_context" / "tda" / "phase2" / "manifold_states.jsonl"
    output_path = workspace_root / ".quro_context" / "tda" / "phase3_5" / "codebase_hologram.json"
    centers_output_path = workspace_root / ".quro_context" / "tda" / "phase3_5" / "semantic_centers.json"

    # Check if manifold states exist
    if not manifold_states_path.exists():
        print(f"[Phase-3.5] Error: Phase-2 manifold states not found: {manifold_states_path}", file=sys.stderr)
        print(f"[Phase-3.5] Run Phase-2 first: python -m quro.tda.phase2", file=sys.stderr)
        sys.exit(1)

    # Run pipeline
    orchestrator = Phase35Orchestrator(manifold_states_path, output_path, centers_output_path)
    orchestrator.run()


if __name__ == "__main__":
    main()

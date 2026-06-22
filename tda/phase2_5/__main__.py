"""Phase 2.5 Main Entry Point

@module quro.tda.phase2_5.__main__
@intent Execute all Phase 2.5 passes to inject offline physics into the manifold.
"""

import argparse
import logging
import sys
from pathlib import Path

from .pass1_git_heat import extract_git_heat
from .pass2_structural_analysis import analyze_structure
from .pass3_edge_weighting import compute_asymmetric_weights
from .pass4_field_initialization import initialize_field
from .pass5_backward_tension import compute_anisotropic_fields
from .pass6_attractor_bias import apply_attractor_bias

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_phase2_5(workspace_root: Path):
    """Execute Phase 2.5: Static Physics Enrichment.

    Args:
        workspace_root: Workspace root directory
    """
    logger.info("=" * 60)
    logger.info("TDA Phase 2.5: Static Physics Enrichment")
    logger.info("=" * 60)

    quro_context = workspace_root / ".quro_context"
    tda_dir = quro_context / "tda"
    phase2_5_dir = tda_dir / "phase2_5"
    phase2_5_dir.mkdir(parents=True, exist_ok=True)

    registry_db = quro_context / "registry.db"
    manifold_states = tda_dir / "phase2" / "manifold_states.jsonl"

    # Check prerequisites
    if not registry_db.exists():
        logger.error("Registry database not found: %s", registry_db)
        logger.error("Please run index builder first")
        return 1

    if not manifold_states.exists():
        logger.error("Manifold states not found: %s", manifold_states)
        logger.error("Please run TDA Phase 2 first")
        return 1

    # Pass 1: Git Heat Extraction
    logger.info("\n" + "=" * 60)
    logger.info("Pass 1: Git Heat Extraction")
    logger.info("=" * 60)
    git_heat_path = phase2_5_dir / "symbol_heat.json"
    extract_git_heat(workspace_root, registry_db, git_heat_path)

    # Pass 2: Structural Analysis
    logger.info("\n" + "=" * 60)
    logger.info("Pass 2: Structural Analysis")
    logger.info("=" * 60)
    structural_metrics_path = phase2_5_dir / "structural_metrics.json"
    analyze_structure(registry_db, structural_metrics_path)

    # Pass 3: Asymmetric Edge Weighting
    logger.info("\n" + "=" * 60)
    logger.info("Pass 3: Asymmetric Edge Weighting")
    logger.info("=" * 60)
    edge_weights_path = phase2_5_dir / "edge_weights.json"
    compute_asymmetric_weights(registry_db, edge_weights_path)

    # Pass 4: Field Initialization
    logger.info("\n" + "=" * 60)
    logger.info("Pass 4: Field Initialization")
    logger.info("=" * 60)
    offline_energy_path = phase2_5_dir / "offline_energy.json"
    initialize_field(
        workspace_root,
        git_heat_path,
        structural_metrics_path,
        edge_weights_path,
        manifold_states,
        offline_energy_path,
    )

    # Pass 5: Backward Tension Computation
    logger.info("\n" + "=" * 60)
    logger.info("Pass 5: Backward Tension Computation")
    logger.info("=" * 60)
    anisotropic_fields_path = phase2_5_dir / "anisotropic_fields.jsonl"
    fields_count = compute_anisotropic_fields(
        registry_db,
        structural_metrics_path,
        offline_energy_path,
        anisotropic_fields_path,
    )
    logger.info("Computed %d anisotropic fields", fields_count)

    # Pass 6: Attractor Bias Injection (Design 90 + Design 95 Basin Annotations)
    logger.info("\n" + "=" * 60)
    logger.info("Pass 6: Attractor Bias Injection")
    logger.info("=" * 60)
    attractor_biased_energy_path = phase2_5_dir / "attractor_biased_energy.json"
    bias_count = apply_attractor_bias(
        registry_db,
        offline_energy_path,
        attractor_biased_energy_path,
    )
    logger.info("Applied attractor bias to %d symbols", bias_count)

    logger.info("\n" + "=" * 60)
    logger.info("Phase 2.5 Complete")
    logger.info("=" * 60)
    logger.info("Output directory: %s", phase2_5_dir)
    logger.info("Files generated:")
    logger.info("  - symbol_heat.json (git heat metrics)")
    logger.info("  - structural_metrics.json (gravity, mass, friction)")
    logger.info("  - edge_weights.json (asymmetric edge weights)")
    logger.info("  - offline_energy.json (energy states + field vectors)")
    logger.info("  - anisotropic_fields.jsonl (forward + backward fields)")
    logger.info("  - attractor_biased_energy.json (attractor bias + basin annotations)")
    logger.info("\nNext: Run TDA Phase 3 to assemble hologram with offline physics")
    logger.info("=" * 60)

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TDA Phase 2.5: Static Physics Enrichment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--workspace",
        type=str,
        default=".",
        help="Workspace root directory (default: current directory)",
    )

    args = parser.parse_args()
    workspace_root = Path(args.workspace).resolve()

    return run_phase2_5(workspace_root)


if __name__ == "__main__":
    sys.exit(main())

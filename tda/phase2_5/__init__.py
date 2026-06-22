"""TDA Phase 2.5: Static Physics Enrichment

@module quro.tda.phase2_5
@intent Inject offline physical quantities (gravity, heat, friction) into the
       semantic manifold to create a non-flat energy landscape before any queries run.

       This phase bridges Phase 2 (topology) and Phase 3 (hologram) by adding:
       - Git heat (modification frequency → kinetic energy)
       - Structural gravity (in-degree → potential wells)
       - Complexity friction (cyclomatic complexity → traversal resistance)
       - Asymmetric edge weights (composition vs dependency)
       - Natural attractor emergence (no manual labeling)
"""

from .pass1_git_heat import extract_git_heat
from .pass2_structural_analysis import analyze_structure
from .pass3_edge_weighting import compute_asymmetric_weights
from .pass4_field_initialization import initialize_field
from .pass5_backward_tension import compute_anisotropic_fields

__all__ = [
    "extract_git_heat",
    "analyze_structure",
    "compute_asymmetric_weights",
    "initialize_field",
    "compute_anisotropic_fields",
]

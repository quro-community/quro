"""
Tensor Debugger for Phase 0 Calibration

Outputs cognitive mass, Ricci curvature, and friction values
for validation without affecting production paths.
"""

import math
from typing import Dict, List, Optional
from dataclasses import dataclass

from ..phase2.schema import SymbolManifoldState


@dataclass(frozen=True)
class TensorDebugInfo:
    """Debug information for tensor calculations."""

    symbol: str

    # Mass components
    in_degree: int
    out_degree: int
    mass_tf: float
    mass_idf: float
    mass_hub_correction: float
    mass_cognitive: float

    # Local statistics for MI-gate
    mean_out_weight: float
    stddev_out_weight: float
    tau_local: float

    # Edge-level info (if available)
    edge_debug: Optional[List['EdgeDebugInfo']] = None


@dataclass(frozen=True)
class EdgeDebugInfo:
    """Debug information for edge tensor calculations."""

    source: str
    target: str

    # Curvature components
    deg_source: int
    deg_target: int
    triangle_count: int
    ricci_raw: float
    ricci_norm: float

    # Friction
    friction: float
    is_boundary: bool


class TensorDebugger:
    """Generates debug output for tensor calculations."""

    def __init__(
        self,
        tau_base: float = 0.05,
        kappa: float = 1.0,
        friction_alpha: float = 0.5,
        friction_beta_cap: float = 5.0,
        boundary_threshold: float = -0.5,
    ):
        """Initialize debugger with config parameters.

        Args:
            tau_base: Base MI-gate threshold
            kappa: Noise separation factor for Otsu gate
            friction_alpha: Curvature sensitivity for friction
            friction_beta_cap: Exponential cap to prevent overflow
            boundary_threshold: Ricci threshold for boundary detection
        """
        self.tau_base = tau_base
        self.kappa = kappa
        self.friction_alpha = friction_alpha
        self.friction_beta_cap = friction_beta_cap
        self.boundary_threshold = boundary_threshold

    def compute_debug_info(
        self,
        sms: SymbolManifoldState,
        in_degree: int,
        out_degree: int,
        calling_modules: set,
        total_modules: int,
        outgoing_weights: List[float],
    ) -> TensorDebugInfo:
        """Compute debug info for a symbol.

        Args:
            sms: Symbol Manifold State from Phase 2
            in_degree: Total incoming edges
            out_degree: Total outgoing edges
            calling_modules: Set of modules that call this symbol
            total_modules: Total number of modules in system
            outgoing_weights: List of outgoing edge weights

        Returns:
            TensorDebugInfo with all computed values
        """
        # Compute TF-IDF mass with hub correction
        mass_tf = math.log(1 + in_degree)

        # IDF with smoothing to prevent negative values
        # When |M(i)| ≈ |M_total|, IDF → 0 (not negative)
        idf_ratio = total_modules / (len(calling_modules) + 1)
        mass_idf = math.log(1 + idf_ratio)  # Add 1 to prevent log(x) where x < 1

        mass_hub_correction = 1 + math.log(1 + out_degree)
        mass_cognitive = mass_tf * mass_idf * mass_hub_correction

        # Compute local statistics for Otsu gate
        if outgoing_weights:
            mean_out_weight = sum(outgoing_weights) / len(outgoing_weights)
            if len(outgoing_weights) > 1:
                variance = sum((w - mean_out_weight) ** 2 for w in outgoing_weights) / len(outgoing_weights)
                stddev_out_weight = math.sqrt(variance)
            else:
                stddev_out_weight = 0.0

            tau_local = max(self.tau_base, mean_out_weight - self.kappa * stddev_out_weight)
        else:
            mean_out_weight = 0.0
            stddev_out_weight = 0.0
            tau_local = self.tau_base

        return TensorDebugInfo(
            symbol=sms.symbol,
            in_degree=in_degree,
            out_degree=out_degree,
            mass_tf=mass_tf,
            mass_idf=mass_idf,
            mass_hub_correction=mass_hub_correction,
            mass_cognitive=mass_cognitive,
            mean_out_weight=mean_out_weight,
            stddev_out_weight=stddev_out_weight,
            tau_local=tau_local,
        )

    def compute_edge_debug_info(
        self,
        source: str,
        target: str,
        deg_source: int,
        deg_target: int,
        triangle_count: int,
    ) -> EdgeDebugInfo:
        """Compute debug info for an edge.

        Args:
            source: Source symbol ID
            target: Target symbol ID
            deg_source: Total degree (in + out) of source
            deg_target: Total degree (in + out) of target
            triangle_count: Number of directed triangles

        Returns:
            EdgeDebugInfo with curvature and friction values
        """
        # Compute Forman-Ricci curvature (raw)
        ricci_raw = 4 - deg_source - deg_target + 3 * triangle_count

        # Normalize to prevent overflow
        deg_max = max(deg_source, deg_target)
        ricci_norm = ricci_raw / (1 + deg_max)

        # Compute friction with overflow protection
        exponent = min(self.friction_beta_cap, -self.friction_alpha * ricci_norm)
        friction = math.exp(exponent)

        # Boundary detection
        is_boundary = ricci_norm < self.boundary_threshold

        return EdgeDebugInfo(
            source=source,
            target=target,
            deg_source=deg_source,
            deg_target=deg_target,
            triangle_count=triangle_count,
            ricci_raw=ricci_raw,
            ricci_norm=ricci_norm,
            friction=friction,
            is_boundary=is_boundary,
        )

    def format_debug_output(self, debug_info: TensorDebugInfo) -> str:
        """Format debug info as human-readable string.

        Args:
            debug_info: TensorDebugInfo to format

        Returns:
            Formatted debug string
        """
        symbol_name = debug_info.symbol.replace("sym::", "")

        lines = [
            f"[DEBUG] Node {symbol_name}:",
            f"  Mass_cognitive={debug_info.mass_cognitive:.2f} "
            f"(TF={debug_info.mass_tf:.2f}, IDF={debug_info.mass_idf:.2f}, Hub={debug_info.mass_hub_correction:.2f})",
            f"  Degrees: in={debug_info.in_degree}, out={debug_info.out_degree}",
            f"  MI-Gate: μ={debug_info.mean_out_weight:.3f}, σ={debug_info.stddev_out_weight:.3f}, τ_local={debug_info.tau_local:.3f}",
        ]

        return "\n".join(lines)

    def format_edge_debug_output(self, edge_info: EdgeDebugInfo) -> str:
        """Format edge debug info as human-readable string.

        Args:
            edge_info: EdgeDebugInfo to format

        Returns:
            Formatted debug string
        """
        source_name = edge_info.source.replace("sym::", "")
        target_name = edge_info.target.replace("sym::", "")

        boundary_marker = " [BOUNDARY]" if edge_info.is_boundary else ""

        return (
            f"[DEBUG] Edge {source_name}→{target_name}: "
            f"Ric_norm={edge_info.ricci_norm:.2f} "
            f"(raw={edge_info.ricci_raw:.1f}, Δ={edge_info.triangle_count}), "
            f"Friction={edge_info.friction:.2f}{boundary_marker}"
        )

"""
Pass 1: Symbol Field Aggregator

Aggregates discrete SMS points into spatial grid based on directory structure.
"""

from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from ..phase2.schema import SymbolManifoldState


class GridCell(object):
    """Represents a spatial grid cell (directory)."""

    def __init__(self, path: str):
        self.path = path
        self.symbols: List[SymbolManifoldState] = []

    def add_symbol(self, sms: SymbolManifoldState):
        """Add symbol to this grid cell."""
        self.symbols.append(sms)

    def get_metrics(self) -> Dict:
        """Compute aggregated metrics for this cell."""
        if not self.symbols:
            return {
                "symbol_count": 0,
                "avg_centrality": 0.0,
                "avg_stability": 0.0,
                "total_frequency": 0,
                "dominant_role": "unknown",
                "role_distribution": {},
            }

        # Aggregate metrics
        total_centrality = sum(s.topology.centrality for s in self.symbols)
        total_stability = sum(s.stability.tau_persistence for s in self.symbols)
        total_frequency = sum(s.temporal_signature.frequency for s in self.symbols)

        # Role distribution
        role_counts = defaultdict(int)
        for s in self.symbols:
            role_counts[s.role.type] += 1

        dominant_role = max(role_counts.items(), key=lambda x: x[1])[0] if role_counts else "unknown"

        return {
            "symbol_count": len(self.symbols),
            "avg_centrality": total_centrality / len(self.symbols),
            "avg_stability": total_stability / len(self.symbols),
            "total_frequency": total_frequency,
            "dominant_role": dominant_role,
            "role_distribution": dict(role_counts),
        }


class SymbolFieldAggregator:
    """Aggregates symbols into spatial grid based on directory structure."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.grid: Dict[str, GridCell] = {}

    def aggregate(self, manifold_states: List[SymbolManifoldState]) -> Dict[str, GridCell]:
        """Aggregate symbols into grid cells.

        Args:
            manifold_states: List of Symbol Manifold States from Phase-2

        Returns:
            Dictionary of grid cells keyed by directory path
        """
        print("[Phase-3.5 Pass-1] Aggregating symbols into spatial grid...")

        for sms in manifold_states:
            # Extract directory from symbol metadata (if available)
            # For now, use a simple heuristic based on symbol name patterns
            grid_path = self._infer_grid_path(sms)

            # Create grid cell if not exists
            if grid_path not in self.grid:
                self.grid[grid_path] = GridCell(grid_path)

            # Add symbol to grid cell
            self.grid[grid_path].add_symbol(sms)

        print(f"[Phase-3.5 Pass-1] Created {len(self.grid)} grid cells")
        return self.grid

    def _infer_grid_path(self, sms: SymbolManifoldState) -> str:
        """Infer grid path from symbol.

        Since we don't have file path in SMS, we use a simple heuristic:
        - Group by role type as a proxy for functional area
        - In production, this should use actual file paths from registry
        """
        # Simple heuristic: group by role type
        role = sms.role.type
        return f"functional_area/{role}"

    def get_statistics(self) -> Dict:
        """Get aggregation statistics."""
        total_symbols = sum(len(cell.symbols) for cell in self.grid.values())
        avg_symbols_per_cell = total_symbols / len(self.grid) if self.grid else 0

        return {
            "total_grid_cells": len(self.grid),
            "total_symbols": total_symbols,
            "avg_symbols_per_cell": avg_symbols_per_cell,
        }

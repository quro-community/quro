"""
Cognitive Mass Calculator

Implements TF-IDF mass calculation with hub correction
for Phase 1 of the Riemannian Manifold upgrade.
"""

import math
import sqlite3
from typing import Dict, Optional
from dataclasses import dataclass

from .module_extractor import ModuleExtractor


@dataclass(frozen=True)
class CognitiveMassComponents:
    """Components of cognitive mass calculation."""

    symbol_id: str
    in_degree: int
    out_degree: int
    calling_modules: int  # Number of modules calling this symbol
    total_modules: int  # Total modules in system

    mass_tf: float  # Term frequency component
    mass_idf: float  # Inverse document frequency component
    mass_hub_correction: float  # Hub kinematic correction
    mass_cognitive: float  # Final cognitive mass


class CognitiveMassCalculator:
    """Calculates cognitive mass using TF-IDF with hub correction."""

    def __init__(self, registry_db_path: str, use_cat_tags: bool = True):
        """Initialize calculator.

        Args:
            registry_db_path: Path to registry.db
            use_cat_tags: If True, use cat::* tags for module extraction
        """
        self.registry_db_path = registry_db_path
        self.use_cat_tags = use_cat_tags
        self._conn: Optional[sqlite3.Connection] = None
        self._module_extractor: Optional[ModuleExtractor] = None
        self._total_modules: Optional[int] = None

    def __enter__(self):
        """Context manager entry."""
        self._conn = sqlite3.connect(self.registry_db_path)
        self._conn.row_factory = sqlite3.Row
        self._module_extractor = ModuleExtractor(
            self.registry_db_path,
            use_cat_tags=self.use_cat_tags
        ).__enter__()

        # Cache total modules count
        self._total_modules = len(self._module_extractor.get_all_modules())

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._module_extractor:
            self._module_extractor.__exit__(exc_type, exc_val, exc_tb)
            self._module_extractor = None

        if self._conn:
            self._conn.close()
            self._conn = None

    def compute_mass(self, symbol_id: str) -> CognitiveMassComponents:
        """Compute cognitive mass for a symbol.

        Args:
            symbol_id: Symbol ID (e.g., "sym::run_mvp_flow")

        Returns:
            CognitiveMassComponents with all computed values
        """
        if not self._conn or not self._module_extractor:
            raise RuntimeError("CognitiveMassCalculator must be used as context manager")

        # Get degree information
        in_degree = self._get_in_degree(symbol_id)
        out_degree = self._get_out_degree(symbol_id)

        # Get calling modules
        calling_modules_set = self._module_extractor.get_calling_modules(symbol_id)
        calling_modules_count = len(calling_modules_set)

        # Compute TF-IDF components
        mass_tf = self._compute_tf(in_degree)
        mass_idf = self._compute_idf(calling_modules_count, self._total_modules)
        mass_hub_correction = self._compute_hub_correction(out_degree)

        # Final cognitive mass
        mass_cognitive = mass_tf * mass_idf * mass_hub_correction

        return CognitiveMassComponents(
            symbol_id=symbol_id,
            in_degree=in_degree,
            out_degree=out_degree,
            calling_modules=calling_modules_count,
            total_modules=self._total_modules,
            mass_tf=mass_tf,
            mass_idf=mass_idf,
            mass_hub_correction=mass_hub_correction,
            mass_cognitive=mass_cognitive,
        )

    def compute_mass_for_all_symbols(self) -> Dict[str, CognitiveMassComponents]:
        """Compute cognitive mass for all symbols in registry.

        Returns:
            Dict mapping symbol_id to CognitiveMassComponents
        """
        if not self._conn:
            raise RuntimeError("CognitiveMassCalculator must be used as context manager")

        result = {}

        cursor = self._conn.execute(
            "SELECT id FROM nodes WHERE type = 'symbol'"
        )

        for row in cursor:
            symbol_id = row["id"]
            result[symbol_id] = self.compute_mass(symbol_id)

        return result

    def _get_in_degree(self, symbol_id: str) -> int:
        """Get in-degree (number of incoming edges) for a symbol.

        Args:
            symbol_id: Symbol ID

        Returns:
            In-degree count
        """
        cursor = self._conn.execute(
            "SELECT COUNT(*) as count FROM edges WHERE dst = ?",
            (symbol_id,)
        )
        return cursor.fetchone()["count"]

    def _get_out_degree(self, symbol_id: str) -> int:
        """Get out-degree (number of outgoing edges) for a symbol.

        Args:
            symbol_id: Symbol ID

        Returns:
            Out-degree count
        """
        cursor = self._conn.execute(
            "SELECT COUNT(*) as count FROM edges WHERE src = ?",
            (symbol_id,)
        )
        return cursor.fetchone()["count"]

    def _compute_tf(self, in_degree: int) -> float:
        """Compute term frequency component.

        Args:
            in_degree: Number of incoming edges

        Returns:
            TF = log(1 + in_degree)
        """
        return math.log(1 + in_degree)

    def _compute_idf(self, calling_modules: int, total_modules: int) -> float:
        """Compute inverse document frequency component with smoothing.

        Args:
            calling_modules: Number of modules calling this symbol
            total_modules: Total number of modules in system

        Returns:
            IDF = log(1 + total_modules / (calling_modules + 1))

        Note: The +1 smoothing prevents negative values when
        calling_modules ≈ total_modules.
        """
        idf_ratio = total_modules / (calling_modules + 1)
        return math.log(1 + idf_ratio)

    def _compute_hub_correction(self, out_degree: int) -> float:
        """Compute hub kinematic correction.

        Args:
            out_degree: Number of outgoing edges

        Returns:
            Hub correction = 1 + log(1 + out_degree)

        Note: This distinguishes hubs (high out-degree) from
        pure sinks (zero out-degree).
        """
        return 1 + math.log(1 + out_degree)

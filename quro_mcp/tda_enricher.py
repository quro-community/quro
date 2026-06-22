"""
TDA Field Enricher for CQE Results

Enriches CQE query results with TDA field metrics (energy, field_role, etc.)
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional


class TDAFieldEnricher:
    """Enriches CQE results with TDA field metrics."""

    def __init__(self, workspace_root: Path):
        """Initialize enricher.

        Args:
            workspace_root: Workspace root directory
        """
        self.workspace_root = workspace_root
        self.manifold_states_path = workspace_root / ".quro_context" / "tda" / "phase2" / "manifold_states.jsonl"
        self.tda_cache: Dict[str, Dict[str, Any]] = {}
        self._load_tda_data()

    def _load_tda_data(self):
        """Load TDA manifold states into cache."""
        if not self.manifold_states_path.exists():
            return

        with open(self.manifold_states_path) as f:
            for line in f:
                data = json.loads(line)
                symbol = data.get("symbol")
                if symbol:
                    # Extract TDA field metrics
                    self.tda_cache[symbol] = {
                        "energy": data.get("energy"),
                        "field_role": data.get("field_role"),
                        "field_magnitude": data.get("field_magnitude"),
                        "mass": data.get("mass"),
                        "friction": data.get("friction"),
                    }

    def enrich_symbol(self, symbol_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a single symbol with TDA field metrics.

        Args:
            symbol_data: Symbol data from CQE query

        Returns:
            Enriched symbol data
        """
        symbol_id = symbol_data.get("id")
        if not symbol_id:
            return symbol_data

        # Get TDA data
        tda_data = self.tda_cache.get(symbol_id)
        if tda_data:
            # Add TDA fields (only if they exist and are not None)
            if tda_data.get("energy") is not None:
                symbol_data["tda_energy"] = tda_data["energy"]
            if tda_data.get("field_role"):
                symbol_data["tda_field_role"] = tda_data["field_role"]
            if tda_data.get("field_magnitude") is not None:
                symbol_data["tda_field_magnitude"] = tda_data["field_magnitude"]
            if tda_data.get("mass") is not None:
                symbol_data["tda_mass"] = tda_data["mass"]
            if tda_data.get("friction") is not None:
                symbol_data["tda_friction"] = tda_data["friction"]

        return symbol_data

    def enrich_results(self, cqe_results: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich CQE query results with TDA field metrics.

        Args:
            cqe_results: CQE query results

        Returns:
            Enriched results
        """
        if not self.tda_cache:
            # No TDA data available
            return cqe_results

        # Enrich refined results
        if "refined" in cqe_results:
            refined = cqe_results["refined"]

            # Enrich primary_structural
            if "primary_structural" in refined:
                refined["primary_structural"] = [
                    self.enrich_symbol(sym) for sym in refined["primary_structural"]
                ]

            # Enrich secondary_structural
            if "secondary_structural" in refined:
                refined["secondary_structural"] = [
                    self.enrich_symbol(sym) for sym in refined["secondary_structural"]
                ]

            # Enrich semantic_neighbors
            if "semantic_neighbors" in refined:
                refined["semantic_neighbors"] = [
                    self.enrich_symbol(sym) for sym in refined["semantic_neighbors"]
                ]

        # Enrich path (for non-refined results)
        if "path" in cqe_results:
            cqe_results["path"] = [
                self.enrich_symbol(sym) if isinstance(sym, dict) else sym
                for sym in cqe_results["path"]
            ]

        # Add metadata
        cqe_results["tda_enriched"] = True
        cqe_results["tda_symbols_available"] = len(self.tda_cache)

        return cqe_results

    def enrich_multi_tier_results(self, multi_tier_results: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich multi-tier CQE results with TDA field metrics.

        Args:
            multi_tier_results: Multi-tier CQE results

        Returns:
            Enriched results
        """
        if not self.tda_cache:
            return multi_tier_results

        # Enrich each tier
        if "tiers" in multi_tier_results:
            for tier_name, tier_data in multi_tier_results["tiers"].items():
                if "refined" in tier_data:
                    # Enrich refined results in this tier
                    tier_data = self.enrich_results(tier_data)
                    multi_tier_results["tiers"][tier_name] = tier_data

        # Add metadata
        multi_tier_results["tda_enriched"] = True
        multi_tier_results["tda_symbols_available"] = len(self.tda_cache)

        return multi_tier_results

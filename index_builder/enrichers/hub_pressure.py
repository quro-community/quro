"""Hub Pressure Enricher

@module quro.index_builder.enrichers.hub_pressure
@intent Detect high-fanout nodes that create graph noise
@constraint Requires full graph topology (two-pass enrichment)

This enricher marks symbols with high out-degree (>50 edges) as "high_fanout" hubs.
These hubs receive stronger penalties in CQE transforms (HubNormalizer).

Mathematical Justification:
- High-fanout nodes create exponential path explosion in BFS traversal
- Marking hubs allows CQE to apply log-scale entropy suppression
- Expected outcome: Query results drop from 1,554 to <100 nodes
"""

from typing import Dict
from index_builder.types import EnrichedSymbol
from index_builder.adapters.protocol import RegistryAdapter


class HubPressureEnricher:
    """Detect high-fanout nodes that create graph noise.

    Marks symbols with high out-degree as hubs to enable stronger
    CQE pruning penalties.

    This is a topology-aware enricher that requires full graph structure.
    Must run in Pass 2 of two-pass enrichment.
    """

    def __init__(
        self,
        registry: RegistryAdapter,
        fanout_threshold: int = 50,
    ):
        """Initialize hub pressure enricher.

        Args:
            registry: Registry adapter to query graph topology
            fanout_threshold: Out-degree threshold for hub detection (default: 50)
        """
        self.registry = registry
        self.fanout_threshold = fanout_threshold
        self._degree_cache: Dict[str, int] = {}

    def enrich(self, symbol: EnrichedSymbol) -> EnrichedSymbol:
        """Enrich symbol with hub pressure detection.

        Args:
            symbol: Symbol to enrich

        Returns:
            Enriched symbol with "high_fanout" tag if hub detected
        """
        # Compute symbol ID
        symbol_id = f"sym::{symbol.base.symbol.name}"

        # Get out-degree from registry (with caching)
        if symbol_id not in self._degree_cache:
            edges = self.registry.get_edges_from(symbol_id)
            self._degree_cache[symbol_id] = len(edges)

        out_degree = self._degree_cache[symbol_id]

        # Check hub threshold
        new_tags = symbol.semantic_tags
        if out_degree > self.fanout_threshold:
            # Add high_fanout tag if not already present
            if "high_fanout" not in new_tags:
                # Convert to set, add tag, convert back to tuple
                new_tags = tuple(set(new_tags) | {"high_fanout"})

        return EnrichedSymbol(
            base=symbol.base,
            semantic_tags=new_tags,
            intent=symbol.intent,
            confidence_score=symbol.confidence_score,
            is_noisy=symbol.is_noisy,
            filtered_refs=symbol.filtered_refs,
        )

    def clear_cache(self):
        """Clear degree cache (for testing)."""
        self._degree_cache.clear()

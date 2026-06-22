"""Default providers for Index Builder V3 Semantic Enrichment Layer.

This module contains built-in heuristics and noise suppression strategies.
These can be optionally injected into the IndexBuilder or replaced by LLM-backed options.
"""

from index_builder.types import EnrichedSymbol, FilteredRefs, SymbolEnricherProtocol

class DefaultHeuristicEnricher:
    """Isolates LLM heuristics and noise suppression strategies from Graph Builder."""

    NOISY_ATTRIBUTES = {
        "logger", "log", "config", "debug", "info", "warn", "error",
        "__dict__", "self", "assert", "print", "exit"
    }

    def enrich(self, symbol: EnrichedSymbol) -> EnrichedSymbol:
        """Enriches raw AST representations with inferred semantics & noise reduction."""

        # 1. Intent Extraction (Heuristic for now, could be LLM-driven)
        intent = "Core"
        name = symbol.base.symbol.name.lower()
        if "test" in name:
            intent = "Test"
        elif "util" in name or "helper" in name:
            intent = "Util"
        elif "config" in name or "setting" in name:
            intent = "Config"

        # 2. Tag Normalization
        semantic_tags = list(symbol.semantic_tags)
        if intent not in semantic_tags:
            semantic_tags.append(intent)

        # 3. Noise Filter (Strip out unhelpful attributes to prevent semantic flooding)
        raw_attrs = symbol.filtered_refs.attributes
        filtered_attrs = tuple(a for a in raw_attrs if a not in self.NOISY_ATTRIBUTES)

        # Build structurally updated refs
        filtered_refs = FilteredRefs(
            calls=symbol.filtered_refs.calls,
            imports=symbol.filtered_refs.imports,
            inherits=symbol.filtered_refs.inherits,
            attributes=filtered_attrs
        )

        return EnrichedSymbol(
            base=symbol.base,
            semantic_tags=tuple(semantic_tags),
            intent=intent,
            confidence_score=1.0,
            is_noisy=(intent == "Test"),
            filtered_refs=filtered_refs
        )

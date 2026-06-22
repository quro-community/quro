"""Semantic Enrichment Layer

@module quro.index_builder.core.enricher
@intent Applies semantic tags, intent extraction, and noise filtering to SymbolInfo.
@constraint Acts as a pure barrier before graph conversion. Mistakes here do not crash the underlying graph pure kernel.
"""

from scanner.types import SymbolInfo
from index_builder.types import EnrichedSymbol, FilteredRefs

class SemanticEnricher:
    """Isolates LLM heuristics and noise suppression strategies from Graph Builder."""

    NOISY_ATTRIBUTES = {
        "logger", "log", "config", "debug", "info", "warn", "error", 
        "__dict__", "self", "assert", "print", "exit"
    }

    @staticmethod
    def enrich(symbol_info: SymbolInfo) -> EnrichedSymbol:
        """Enriches raw AST representations with inferred semantics & noise reduction."""
        
        # 1. Intent Extraction (Heuristic for now, could be LLM-driven)
        intent = "Core"
        name = symbol_info.symbol.name.lower()
        if "test" in name:
            intent = "Test"
        elif "util" in name or "helper" in name:
            intent = "Util"
        elif "config" in name or "setting" in name:
            intent = "Config"
        
        # 2. Tag Normalization
        semantic_tags = list(symbol_info.features.behavioral_tags)
        if intent not in semantic_tags:
            semantic_tags.append(intent)

        # 3. Noise Filter (Strip out unhelpful attributes to prevent semantic flooding)
        raw_attrs = getattr(symbol_info.symbol, "attr_accesses", ())
        filtered_attrs = tuple(a for a in raw_attrs if a not in SemanticEnricher.NOISY_ATTRIBUTES)

        # Build structural refs
        filtered_refs = FilteredRefs(
            calls=tuple(symbol_info.symbol.calls),
            imports=tuple(symbol_info.symbol.imports),
            inherits=tuple(getattr(symbol_info.symbol, "inherits", ())),
            attributes=filtered_attrs
        )

        return EnrichedSymbol(
            base=symbol_info,
            semantic_tags=tuple(semantic_tags),
            intent=intent,
            confidence_score=1.0,  # Could be derived from LLM confidence
            is_noisy=(intent == "Test"), # Mark test symbols as noisy potentially
            filtered_refs=filtered_refs
        )

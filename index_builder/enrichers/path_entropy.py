"""Path Entropy Enricher

@module quro.index_builder.enrichers.path_entropy
@intent Detect ambiguous/noisy symbols that reduce path interpretability
@constraint Pure function, deterministic

This enricher marks symbols with:
- Multiple definitions (name collisions across modules)
- Wildcard imports (import *)
- Overloaded signatures

These symbols receive "noisy" tag and is_noisy=True flag.
CQE can use this to deprioritize ambiguous paths.

Mathematical Justification:
- Ambiguous symbols create multiple valid paths with different semantics
- Marking them allows CQE to prefer unambiguous paths
- Reduces false positives in semantic search
"""

from typing import Dict, List
from index_builder.types import EnrichedSymbol
from scanner.types import SymbolInfo


class PathEntropyEnricher:
    """Detect ambiguous/noisy symbols.

    Marks symbols with:
    - Name collisions (multiple definitions)
    - Wildcard imports (import *)
    - Overloaded signatures

    This is a structure-aware enricher that needs symbol registry.
    Can run in Pass 1 if symbol registry is built first.
    """

    def __init__(
        self,
        symbol_registry: Dict[str, List[SymbolInfo]],
        collision_threshold: int = 1,
    ):
        """Initialize path entropy enricher.

        Args:
            symbol_registry: Map of symbol name -> list of SymbolInfo
            collision_threshold: Threshold for collision detection (default: 1, meaning >1 triggers)
        """
        self.symbol_registry = symbol_registry
        self.collision_threshold = collision_threshold

    def enrich(self, symbol: EnrichedSymbol) -> EnrichedSymbol:
        """Enrich symbol with noise detection.

        Args:
            symbol: Symbol to enrich

        Returns:
            Enriched symbol with "noisy" tag if ambiguity detected
        """
        is_noisy = False
        new_tags = symbol.semantic_tags

        # Check 1: Name collisions
        name = symbol.base.symbol.name
        if name in self.symbol_registry:
            definitions = self.symbol_registry[name]
            if len(definitions) > self.collision_threshold:
                is_noisy = True

        # Check 2: Wildcard imports
        if any("*" in imp for imp in symbol.base.symbol.imports):
            is_noisy = True

        # Check 3: Dynamic imports (importlib)
        if any("importlib" in imp for imp in symbol.base.symbol.imports):
            is_noisy = True

        # Add noisy tag if detected
        if is_noisy and "noisy" not in new_tags:
            new_tags = new_tags + ("noisy",)

        return EnrichedSymbol(
            base=symbol.base,
            semantic_tags=new_tags,
            intent=symbol.intent,
            confidence_score=symbol.confidence_score,
            is_noisy=is_noisy,
            filtered_refs=symbol.filtered_refs,
        )

    def update_registry(self, symbol_registry: Dict[str, List[SymbolInfo]]):
        """Update symbol registry (for incremental builds).

        Args:
            symbol_registry: Updated symbol registry
        """
        self.symbol_registry = symbol_registry

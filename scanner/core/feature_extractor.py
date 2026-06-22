"""Scanner v3 - Feature Extractor

@module quro.scanner.core.feature_extractor
@intent Extract behavioral tags from symbols
@constraint Pure function, no I/O
"""

from typing import Set, Tuple
from scanner.types import ParsedSymbol, SymbolFeatures


class FeatureExtractor:
    """Extract behavioral features from symbols.

    Pure feature extraction based on:
    - Symbol kind (async, sync)
    - Decorators
    - Calls
    - Imports
    - Naming patterns
    """

    # Behavioral tag mappings
    ASYNC_INDICATORS = {"async", "await", "asyncio", "aiohttp", "aiofiles"}
    LOCK_INDICATORS = {"lock", "mutex", "semaphore", "rlock", "condition"}
    NETWORK_INDICATORS = {"http", "socket", "requests", "urllib", "aiohttp"}
    FILESYSTEM_INDICATORS = {"file", "path", "open", "read", "write", "pathlib"}
    DATABASE_INDICATORS = {"db", "sql", "query", "postgres", "mysql", "sqlite", "asyncpg", "psycopg"}
    MEMORY_INDICATORS = {"cache", "pool", "buffer", "memory", "mmap"}

    @staticmethod
    def extract(symbol: ParsedSymbol, source: str = "") -> SymbolFeatures:
        """Extract features from symbol.

        Args:
            symbol: Parsed symbol
            source: Optional source code (for advanced analysis)

        Returns:
            SymbolFeatures with behavioral/structural tags
        """
        behavioral_tags: Set[str] = set()
        structural_tags: Set[str] = set()
        risk_anchors: Set[str] = set()

        # 1. Extract from symbol kind
        if "async" in symbol.kind:
            behavioral_tags.add("async")

        # 2. Extract from decorators
        for dec in symbol.decorators:
            if "staticmethod" in dec:
                structural_tags.add("static")
            elif "classmethod" in dec:
                structural_tags.add("classmethod")
            elif "property" in dec:
                structural_tags.add("property")
            elif "dataclass" in dec:
                structural_tags.add("dataclass")

        # 3. Extract from imports
        for imp in symbol.imports:
            imp_lower = imp.lower()

            if any(ind in imp_lower for ind in FeatureExtractor.ASYNC_INDICATORS):
                behavioral_tags.add("async")

            if any(ind in imp_lower for ind in FeatureExtractor.LOCK_INDICATORS):
                behavioral_tags.add("lock")

            if any(ind in imp_lower for ind in FeatureExtractor.NETWORK_INDICATORS):
                behavioral_tags.add("network")

            if any(ind in imp_lower for ind in FeatureExtractor.FILESYSTEM_INDICATORS):
                behavioral_tags.add("filesystem")

            if any(ind in imp_lower for ind in FeatureExtractor.DATABASE_INDICATORS):
                behavioral_tags.add("database")

            if any(ind in imp_lower for ind in FeatureExtractor.MEMORY_INDICATORS):
                behavioral_tags.add("memory")

        # 4. Extract from calls
        for call in symbol.calls:
            call_lower = call.lower()

            if "lock" in call_lower or "acquire" in call_lower:
                behavioral_tags.add("lock")

            if "release" in call_lower:
                behavioral_tags.add("lock")
                # Check for RAII pattern
                if "__enter__" in symbol.calls or "__exit__" in symbol.calls:
                    behavioral_tags.add("raii")

            if "await" in call_lower:
                behavioral_tags.add("async")

        # 5. Extract from symbol name
        name_lower = symbol.name.lower()

        if "lock" in name_lower or "mutex" in name_lower:
            behavioral_tags.add("lock")

        if "pool" in name_lower:
            behavioral_tags.add("pool")

        if "manager" in name_lower:
            structural_tags.add("manager")

        if "factory" in name_lower:
            structural_tags.add("factory")

        if "singleton" in name_lower:
            structural_tags.add("singleton")

        if name_lower in {"main", "__main__"}:
            structural_tags.add("entry_point")

        # 6. Detect RAII pattern
        if "__enter__" in symbol.calls and "__exit__" in symbol.calls:
            behavioral_tags.add("raii")

        # 7. Detect risk patterns
        if "async" in behavioral_tags and "lock" in behavioral_tags:
            # Async + lock = potential deadlock risk
            risk_anchors.add("async_lock_pattern")

        return SymbolFeatures(
            behavioral_tags=tuple(sorted(behavioral_tags)),
            structural_tags=tuple(sorted(structural_tags)),
            risk_anchors=tuple(sorted(risk_anchors)),
            lsh_signature=None,  # TODO: Implement LSH
        )

    @staticmethod
    def merge_tags(
        base_features: SymbolFeatures,
        additional_tags: Tuple[str, ...],
    ) -> SymbolFeatures:
        """Merge additional tags into features.

        Used to combine static analysis tags with LLM-generated tags.

        Args:
            base_features: Base features
            additional_tags: Additional tags to merge

        Returns:
            New SymbolFeatures with merged tags
        """
        merged_behavioral = set(base_features.behavioral_tags)
        merged_behavioral.update(additional_tags)

        return SymbolFeatures(
            behavioral_tags=tuple(sorted(merged_behavioral)),
            structural_tags=base_features.structural_tags,
            risk_anchors=base_features.risk_anchors,
            lsh_signature=base_features.lsh_signature,
        )

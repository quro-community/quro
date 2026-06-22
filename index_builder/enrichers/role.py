"""Role Enricher

@module quro.index_builder.enrichers.role
@intent Detect architectural roles from AST patterns
@constraint Pure function, deterministic, AST-based

This enricher detects architectural roles:
- controller: Request handlers, dispatchers
- worker: Background tasks, threads, processes
- adapter: Protocol implementations, interfaces
- factory: Object creation patterns
- service: Business logic services
- repository: Data access patterns

Uses AST patterns (base classes, method names, naming conventions).
"""

from typing import Set
from index_builder.types import EnrichedSymbol


class RoleEnricher:
    """Detect architectural roles from AST patterns.

    Analyzes class definitions to identify common architectural patterns.
    Only applies to class symbols.
    """

    # Role detection patterns
    ROLE_PATTERNS = {
        "controller": {
            "base_classes": {"BaseController", "Controller", "APIController"},
            "methods": {"handle", "dispatch", "handle_request", "process_request"},
            "naming": {"Controller", "Handler"},
        },
        "worker": {
            "base_classes": {"Worker", "Thread", "Process", "Task"},
            "methods": {"run", "execute", "process", "work"},
            "naming": {"Worker", "Task", "Job"},
            "imports": {"threading", "multiprocessing", "asyncio"},
        },
        "adapter": {
            "base_classes": {"Protocol", "ABC", "Interface", "Adapter"},
            "methods": {"adapt", "convert", "transform"},
            "naming": {"Adapter", "Interface", "Bridge"},
        },
        "factory": {
            "base_classes": {"Factory", "Builder"},
            "methods": {"create", "build", "make", "construct"},
            "naming": {"Factory", "Builder", "Creator"},
        },
        "service": {
            "base_classes": {"Service", "BaseService"},
            "methods": {"execute", "process", "handle"},
            "naming": {"Service", "Manager", "Orchestrator"},
        },
        "repository": {
            "base_classes": {"Repository", "DAO", "Store"},
            "methods": {"find", "save", "delete", "update", "get", "query"},
            "naming": {"Repository", "Store", "DAO"},
        },
    }

    def __init__(self, confidence_threshold: float = 0.5):
        """Initialize role enricher.

        Args:
            confidence_threshold: Minimum confidence to assign role (default: 0.5)
        """
        self.confidence_threshold = confidence_threshold

    def enrich(self, symbol: EnrichedSymbol) -> EnrichedSymbol:
        """Enrich symbol with role detection.

        Args:
            symbol: Symbol to enrich

        Returns:
            Enriched symbol with role tag if detected
        """
        # Only apply to classes
        if symbol.base.symbol.kind != "class":
            return symbol

        # Detect role
        role, confidence = self._detect_role(symbol)

        # Add role tag if confidence meets threshold
        new_tags = symbol.semantic_tags
        new_intent = symbol.intent

        if role and confidence >= self.confidence_threshold:
            if role not in new_tags:
                new_tags = new_tags + (role,)
            # Update intent if more specific than current
            if symbol.intent in ("Unknown", "function", "class"):
                new_intent = role

        return EnrichedSymbol(
            base=symbol.base,
            semantic_tags=new_tags,
            intent=new_intent,
            confidence_score=min(symbol.confidence_score, confidence),
            is_noisy=symbol.is_noisy,
            filtered_refs=symbol.filtered_refs,
        )

    def _detect_role(self, symbol: EnrichedSymbol) -> tuple[str | None, float]:
        """Detect architectural role from symbol patterns.

        Args:
            symbol: Symbol to analyze

        Returns:
            Tuple of (role_name, confidence) or (None, 0.0)
        """
        scores = {}

        for role, patterns in self.ROLE_PATTERNS.items():
            score = 0.0
            matches = 0
            total_checks = 0

            # Check base classes (not available in current ParsedSymbol)
            # TODO: Add base_classes to ParsedSymbol
            # For now, check naming patterns

            # Check naming patterns
            if "naming" in patterns:
                total_checks += 1
                for pattern in patterns["naming"]:
                    if pattern.lower() in symbol.base.symbol.name.lower():
                        matches += 1
                        score += 0.4
                        break

            # Check method names (for classes, check calls as proxy)
            if "methods" in patterns:
                total_checks += 1
                for method in patterns["methods"]:
                    if method in symbol.base.symbol.calls:
                        matches += 1
                        score += 0.3
                        break

            # Check imports
            if "imports" in patterns:
                total_checks += 1
                for imp in patterns["imports"]:
                    if any(imp in import_path for import_path in symbol.base.symbol.imports):
                        matches += 1
                        score += 0.3
                        break

            # Normalize score
            if total_checks > 0:
                scores[role] = min(score, 1.0)

        # Return role with highest score
        if scores:
            best_role = max(scores.items(), key=lambda x: x[1])
            if best_role[1] > 0:
                return best_role

        return None, 0.0

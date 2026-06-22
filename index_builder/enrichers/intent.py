"""Intent Enricher

@module quro.index_builder.enrichers.intent
@intent Detect semantic intent from AST patterns
@constraint Pure function, deterministic, AST-based

This enricher detects semantic intent:
- io: File operations, I/O
- network: HTTP, sockets, requests
- database: SQL, queries, ORM
- util: Simple utility functions
- test: Test functions
- config: Configuration loading
- logging: Logging operations

Uses AST patterns (calls, imports, file paths).
"""

from typing import Set
from index_builder.types import EnrichedSymbol


class IntentEnricher:
    """Detect semantic intent from AST patterns.

    Analyzes function/method calls and imports to identify semantic categories.
    """

    # Intent detection patterns
    INTENT_PATTERNS = {
        "io": {
            "calls": {"open", "read", "write", "close", "readlines", "writelines"},
            "imports": {"io", "pathlib", "os.path", "shutil"},
        },
        "network": {
            "calls": {"get", "post", "put", "delete", "request", "connect", "send", "recv"},
            "imports": {"requests", "urllib", "http", "socket", "aiohttp", "httpx"},
        },
        "database": {
            "calls": {"execute", "query", "commit", "rollback", "fetchall", "fetchone"},
            "imports": {"sqlite3", "psycopg2", "sqlalchemy", "pymongo", "redis"},
        },
        "test": {
            "calls": {"assert", "assertEqual", "assertTrue", "assertFalse", "mock"},
            "imports": {"pytest", "unittest", "mock"},
            "file_path": {"test_", "tests/"},
        },
        "config": {
            "calls": {"load", "parse", "get_config", "read_config"},
            "imports": {"configparser", "yaml", "toml", "json", "dotenv"},
            "naming": {"config", "settings", "env"},
        },
        "logging": {
            "calls": {"log", "debug", "info", "warning", "error", "critical"},
            "imports": {"logging", "loguru"},
        },
        "async": {
            "calls": {"await", "async"},
            "imports": {"asyncio", "aiofiles"},
            "ast_kind": {"AsyncFunctionDef"},
        },
        "cli": {
            "calls": {"parse_args", "add_argument"},
            "imports": {"argparse", "click", "typer"},
        },
    }

    def __init__(self, confidence_threshold: float = 0.3):
        """Initialize intent enricher.

        Args:
            confidence_threshold: Minimum confidence to assign intent (default: 0.3)
        """
        self.confidence_threshold = confidence_threshold

    def enrich(self, symbol: EnrichedSymbol) -> EnrichedSymbol:
        """Enrich symbol with intent detection.

        Args:
            symbol: Symbol to enrich

        Returns:
            Enriched symbol with intent
        """
        # Detect intent
        intent, confidence = self._detect_intent(symbol)

        # Update intent if detected and confidence meets threshold
        new_intent = symbol.intent
        if intent and confidence >= self.confidence_threshold:
            # Only update if current intent is generic
            if symbol.intent in ("Unknown", "function", "class", "method"):
                new_intent = intent

        return EnrichedSymbol(
            base=symbol.base,
            semantic_tags=symbol.semantic_tags,
            intent=new_intent,
            confidence_score=min(symbol.confidence_score, confidence),
            is_noisy=symbol.is_noisy,
            filtered_refs=symbol.filtered_refs,
        )

    def _detect_intent(self, symbol: EnrichedSymbol) -> tuple[str | None, float]:
        """Detect semantic intent from symbol patterns.

        Args:
            symbol: Symbol to analyze

        Returns:
            Tuple of (intent_name, confidence) or (None, 0.0)
        """
        scores = {}

        for intent, patterns in self.INTENT_PATTERNS.items():
            score = 0.0
            matches = 0

            # Check calls
            if "calls" in patterns:
                for call in patterns["calls"]:
                    if call in symbol.base.symbol.calls:
                        matches += 1
                        score += 0.4

            # Check imports
            if "imports" in patterns:
                for imp in patterns["imports"]:
                    if any(imp in import_path for import_path in symbol.base.symbol.imports):
                        matches += 1
                        score += 0.3

            # Check file path
            if "file_path" in patterns:
                for pattern in patterns["file_path"]:
                    if pattern in symbol.base.symbol.file_path:
                        matches += 1
                        score += 0.5

            # Check naming
            if "naming" in patterns:
                for pattern in patterns["naming"]:
                    if pattern.lower() in symbol.base.symbol.name.lower():
                        matches += 1
                        score += 0.3

            # Check AST kind
            if "ast_kind" in patterns:
                if symbol.base.symbol.ast_kind in patterns["ast_kind"]:
                    matches += 1
                    score += 0.5

            # Normalize score
            if matches > 0:
                scores[intent] = min(score, 1.0)

        # Return intent with highest score
        if scores:
            best_intent = max(scores.items(), key=lambda x: x[1])
            if best_intent[1] > 0:
                return best_intent

        # Fallback: detect util (simple functions)
        if symbol.base.symbol.kind in ("function", "method"):
            if self._is_util(symbol):
                return "util", 0.5

        return None, 0.0

    def _is_util(self, symbol: EnrichedSymbol) -> bool:
        """Detect if symbol is a utility function.

        Heuristic: Few calls, no complex imports, short name.

        Args:
            symbol: Symbol to check

        Returns:
            True if likely a utility function
        """
        # Simple heuristic: <3 calls, no external imports
        if len(symbol.base.symbol.calls) < 3:
            # Check for simple imports (no external packages)
            external_imports = [
                imp for imp in symbol.base.symbol.imports
                if not imp.startswith((".", "typing", "dataclasses"))
            ]
            if len(external_imports) == 0:
                return True

        return False

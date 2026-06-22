"""Scanner v3 - Symbol Filter Gate

@module quro.scanner.gates.symbol_filter
@intent Stateless symbol filtering (blacklist, noise, naming patterns)
@constraint Pure function, no mutations
"""

from scanner.types import ParsedSymbol
from scanner.gates.types import GateResult


class SymbolFilterGate:
    """Stateless symbol filtering gate.

    Filters symbols based on:
    - Blacklist (high-frequency noise symbols)
    - Naming patterns (too short, private, test)
    - Symbol kind (skip certain kinds)

    Invariant: Pure function - same symbol → same result
    """

    # High-frequency symbol names that match thousands of DB rows.
    # Processing these causes massive CALLS edge lookups and memory blowups.
    # They are never useful as semantic symbols — skip entirely.
    SKIP_SYMBOL_NAMES = frozenset(
        {
            # Generic data/flow variable names
            "task_id",
            "path",
            "symbol",
            "error",
            "ok",
            "status",
            "result",
            "data",
            "value",
            "key",
            "name",
            "type",
            "content",
            "text",
            "item",
            "items",
            "entry",
            "record",
            "row",
            "field",
            "col",
            "msg",
            "message",
            "args",
            "kwargs",
            "self",
            "cls",
            "config",
            "options",
            "params",
            "headers",
            "payload",
            "request",
            "response",
            # Common loop variables
            "i",
            "j",
            "k",
            "x",
            "y",
            "z",
            "n",
            "m",
            "idx",
            "index",
            # Common boolean flags
            "flag",
            "enabled",
            "disabled",
            "active",
            "inactive",
            # Common generic names
            "obj",
            "val",
            "tmp",
            "temp",
            "buf",
            "buffer",
            "str",
            "num",
            "count",
            "total",
            "sum",
        }
    )

    # Minimum symbol name length
    MIN_NAME_LENGTH = 2

    @staticmethod
    def validate(symbol: ParsedSymbol) -> GateResult:
        """Validate symbol against filter rules.

        Pure function: symbol → GateResult

        Args:
            symbol: Parsed symbol to validate

        Returns:
            GateResult with passed=True if symbol should be indexed
        """
        # Sub-gate 1: Blacklist check
        if symbol.name in SymbolFilterGate.SKIP_SYMBOL_NAMES:
            return GateResult(passed=False, reason="blacklisted_symbol")

        # Sub-gate 2: Name length check
        if len(symbol.name) < SymbolFilterGate.MIN_NAME_LENGTH:
            return GateResult(passed=False, reason="symbol_too_short")

        # Sub-gate 3: Private symbols (single underscore prefix)
        # Note: Keep dunder methods (__init__, __enter__, etc.) - they're important
        if symbol.name.startswith("_") and not symbol.name.startswith("__"):
            return GateResult(passed=False, reason="private_symbol")

        # Sub-gate 4: Test symbols (skip test_ prefix)
        if symbol.name.startswith("test_"):
            return GateResult(passed=False, reason="test_symbol")

        # Sub-gate 5: Lambda functions (not useful for indexing)
        if symbol.name == "<lambda>":
            return GateResult(passed=False, reason="lambda_function")

        # All gates passed
        return GateResult(passed=True)

    @staticmethod
    def is_noise_symbol(symbol: ParsedSymbol) -> bool:
        """Check if symbol is noise (convenience method).

        Args:
            symbol: Parsed symbol

        Returns:
            True if symbol is noise and should be filtered
        """
        result = SymbolFilterGate.validate(symbol)
        return not result.passed

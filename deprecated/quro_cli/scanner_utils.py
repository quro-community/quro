"""
Scanner utilities — pure functions for fingerprint and contract checking.

@module quro_cli.scanner_utils
@intent Deterministic, side-effect-free computation for scan metrics

All functions are pure — no DB access, no I/O, no mutable state.
Designed for import by any scanner implementation.
"""

import hashlib
import re
from typing import Any, List, Optional
from enum import Enum


# Contract status enumeration
class ContractStatus(str, Enum):
    """Contract completion status for file scans.

    SATISFIED: AST parse succeeded and extraction completed
    INCOMPLETE: Scan was interrupted or incomplete
    ERROR: AST parse failed or extraction error
    """
    SATISFIED = "SATISFIED"
    INCOMPLETE = "INCOMPLETE"
    ERROR = "ERROR"


# Contract type enumeration (closed set)
class ContractType(str, Enum):
    """Extraction contract type.

    AST_PUBLIC_METHODS: Class functions + methods, no private (_prefix)
    AST_FULL: All definitions including _private
    TS_EXPORTS: TypeScript exported symbols only
    """
    AST_PUBLIC_METHODS = "ast_public_methods"
    AST_FULL = "ast_full"
    TS_EXPORTS = "ts_exports"


# DB symbol_type constraint: only these values are allowed
VALID_SYMBOL_TYPES = frozenset([
    'class', 'function', 'interface', 'type', 'variable', 'method', 'property',
])


def normalize_symbol_kind(kind: str) -> str:
    """Normalize AST analyzer kind to DB constraint values.

    Maps async_function -> function, async_method -> method.
    Falls back to 'function' for unknown kinds.
    """
    if kind in VALID_SYMBOL_TYPES:
        return kind
    if kind.startswith('async_'):
        stripped = kind[6:]
        if stripped in VALID_SYMBOL_TYPES:
            return stripped
    return 'function'


def compute_fingerprint(source: str, imports_normalized: str) -> str:
    """Compute semantic fingerprint = SHA256(source + normalized_imports).

    Captures both implementation AND dependency context changes.
    Language-agnostic: the scanner doesn't interpret *why* imports matter,
    just that they changed.

    Args:
        source: Full file source text
        imports_normalized: Deterministic string from normalize_imports()

    Returns:
        64-char hex SHA256 digest
    """
    combined = f"{source}\n__IMPORTS__\n{imports_normalized}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def normalize_imports(imports: List[Any]) -> str:
    """Normalize imports to a deterministic string for fingerprinting.

    Accepts both PythonImport dataclass objects and plain dicts (duck-typing).
    Sorts by (source, line) for deterministic output.

    Args:
        imports: List of import objects (PythonImport, dict, or duck-typed)

    Returns:
        Deterministic newline-separated string
    """
    parts = []
    for imp in sorted(imports, key=lambda x: (_imp_source(x), _imp_line(x))):
        source = _imp_source(imp)
        names = _imp_names(imp)
        if isinstance(names, list):
            names = sorted(str(n) for n in names)
        parts.append(f"{source}:{','.join(names)}")
    return "\n".join(parts)


def _imp_source(imp: Any) -> str:
    """Get source module from PythonImport or dict."""
    if hasattr(imp, 'module'):
        return imp.module
    return imp.get("source", "") if isinstance(imp, dict) else ""


def _imp_line(imp: Any) -> int:
    """Get line number from PythonImport or dict."""
    if hasattr(imp, 'line'):
        return imp.line
    return imp.get("line", 0) if isinstance(imp, dict) else 0


def _imp_names(imp: Any) -> list:
    """Get imported names from PythonImport or dict."""
    if hasattr(imp, 'names'):
        return imp.names
    return imp.get("names", []) if isinstance(imp, dict) else []


def check_contract(
    source: str,
    symbols_extracted: int,
    parse_error: Optional[str] = None,
    interrupted: bool = False,
) -> ContractStatus:
    """Check if scan contract was satisfied.

    Args:
        source: File source text (empty means no content)
        symbols_extracted: Number of symbols successfully extracted
        parse_error: Error message if AST parse failed
        interrupted: True if scan was interrupted mid-file

    Returns:
        ContractStatus enum value

    Contract rules:
        - If parse_error → ERROR
        - If interrupted → INCOMPLETE
        - If source exists and symbols_extracted >= 0 → SATISFIED
        - Empty source with no symbols → SATISFIED (valid empty file)
    """
    if parse_error:
        return ContractStatus.ERROR

    if interrupted:
        return ContractStatus.INCOMPLETE

    # Parse succeeded, extraction completed
    return ContractStatus.SATISFIED


def compute_fidelity(source: str, symbol_bodies: List[str], file_ext: str) -> float:
    """[DEPRECATED] Use check_contract() instead.

    Kept for backward compatibility during migration.
    """
    if not source:
        return 1.0

    lang = "typescript" if file_ext in (".ts", ".tsx", ".js", ".jsx") else "python"

    if lang == "python":
        pattern = r"\b(?:async )?def \w+"
    else:
        pattern = r"(?:async )?(?:function|\w+)\s*\("

    total = len(re.findall(pattern, source))
    if total == 0:
        return 1.0

    found = sum(len(re.findall(pattern, body)) for body in symbol_bodies)
    return min(found / total, 1.0)


def detect_language(suffix: str) -> Optional[str]:
    """Map file extension to language string."""
    mapping = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
    }
    return mapping.get(suffix)

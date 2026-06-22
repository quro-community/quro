"""
Audit rules — diagnostic rule functions for DeepScanner.

@module quro_cli.scanner_deep.audit_rules
@intent Stateless diagnostic functions that produce UNBOUND_ATTRIBUTE_REFERENCE,
STRUCTURAL_MISMATCH, DEPRECATED_SYMBOL_STILL_REFERENCED, and DUAL_WRITE_PATTERN diagnostics.

All functions are pure — they take data in, return diagnostics out. No side effects.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from quro_cli.scanner_deep.class_signature import ClassSignature

logger = logging.getLogger(__name__)


def check_unbound_attributes(
    file_path: str,
    source: str,
    class_signatures: List[ClassSignature],
) -> List[Dict[str, Any]]:
    """Check for attribute references not observed in AST ClassSignatures.

    Scans source for obj.attr patterns and checks against known classes.
    Reports UNBOUND_ATTRIBUTE_REFERENCE for unobserved attributes.

    Args:
        file_path: File being audited
        source: Source text to scan for attribute references
        class_signatures: ClassSignatures for this file

    Returns:
        List of diagnostic dicts
    """
    import re

    # Build class_name -> ClassSignature lookup
    sigs_by_name: Dict[str, ClassSignature] = {}
    for sig in class_signatures:
        sigs_by_name[sig.class_name] = sig

    # Strip comments before scanning to avoid false positives
    source_code = _strip_comments(source)

    diagnostics = []

    # Find obj.attr patterns
    # Matches: self.xxx, ClassName.xxx, obj.xxx (where ClassName is known)
    pattern = r'\b([A-Z]\w*)\.(\w+)\b'

    seen: Set[tuple[str, str]] = set()

    for match in re.finditer(pattern, source_code):
        class_ref = match.group(1)
        attr_name = match.group(2)

        # Skip common false positives
        if _attr_ref_is_builtin(attr_name):
            continue
        if class_ref in ("os", "sys", "json", "Path", "Optional", "List", "Dict", "Set", "Tuple", "Any", "logging"):
            continue
        if class_ref.startswith("_"):
            continue

        pair = (class_ref, attr_name)
        if pair in seen:
            continue
        seen.add(pair)

        sig = sigs_by_name.get(class_ref)
        if sig is not None:
            attr_source = sig.lookup(attr_name)
            if attr_source is None:
                diagnostics.append({
                    "type": "UNBOUND_ATTRIBUTE_REFERENCE",
                    "file_path": file_path,
                    "class_name": class_ref,
                    "attribute": attr_name,
                    "evidence": f"not observed in ClassSignature({class_ref})",
                    "observation_scope": "AST_ONLY",
                })

    return diagnostics


def check_structural_mismatch(
    registry_symbols: List[Dict[str, Any]],
    git_ast_symbols: Set[str],
) -> List[Dict[str, Any]]:
    """Check for Registry symbols not present in GitTree AST.

    Args:
        registry_symbols: Symbols from Registry (PG) — dicts with at least 'symbol_name', 'file_path'
        git_ast_symbols: Set of "file_path::symbol_name" strings found in Git AST

    Returns:
        List of diagnostic dicts
    """
    diagnostics = []

    for sym in registry_symbols:
        key = f"{sym['file_path']}::{sym['symbol_name']}"
        if key not in git_ast_symbols:
            diagnostics.append({
                "type": "STRUCTURAL_MISMATCH",
                "symbol": sym["symbol_name"],
                "file_path": sym["file_path"],
                "registry_has": True,
                "git_has": False,
                "evidence": "symbol in Registry but not in GitTree AST",
            })

    return diagnostics


def check_deprecated_references(
    deprecated_symbols: List[Dict[str, Any]],
    file_sources: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Check for references to deprecated symbols in active files.

    Args:
        deprecated_symbols: Deprecated symbols with 'symbol_name', 'deprecated_at'
        file_sources: {file_path: source_text} — active files to scan

    Returns:
        List of diagnostic dicts
    """
    import re

    diagnostics = []

    for sym in deprecated_symbols:
        sym_name = sym.get("symbol_name", "")
        if not sym_name:
            continue

        pattern = re.compile(rf'\b{re.escape(sym_name)}\b')

        for file_path, source in file_sources.items():
            matches = list(pattern.finditer(source))
            if matches:
                diagnostics.append({
                    "type": "DEPRECATED_SYMBOL_STILL_REFERENCED",
                    "symbol": sym_name,
                    "deprecated_at": sym.get("deprecated_at"),
                    "referenced_in": file_path,
                    "reference_count": len(matches),
                })

    return diagnostics


def check_dual_write_patterns(
    source: str,
    file_path: str,
    allowed_patterns: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Detect potential dual-write patterns in source code.

    Looks for patterns like writing to multiple tables for the same entity.

    Args:
        source: Source text to scan
        file_path: File path for diagnostic context
        allowed_patterns: Whitelist of known dual-write patterns

    Returns:
        List of diagnostic dicts
    """
    import re

    if allowed_patterns is None:
        allowed_patterns = [
            "shadow_write",
            "migration_bridge",
            "fallback_write",
            "canonical_uid_upsert",
        ]

    diagnostics = []

    # Pattern: INSERT INTO table1 ... INSERT INTO table2 (same scope)
    insert_pattern = re.compile(
        r'INSERT\s+INTO\s+(\w+)',
        re.IGNORECASE,
    )

    inserts_in_scope: List[str] = []
    for line in source.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue

        match = insert_pattern.search(stripped)
        if match:
            table = match.group(1)
            inserts_in_scope.append(table)

    if len(inserts_in_scope) >= 2:
        tables_str = ", ".join(inserts_in_scope)
        # Check if any allowed pattern appears near the tables
        allowed = any(pat in source for pat in allowed_patterns)

        if not allowed:
            diagnostics.append({
                "type": "DUAL_WRITE_PATTERN",
                "file_path": file_path,
                "tables": inserts_in_scope,
                "evidence": f"multiple INSERT INTO in same scope: {tables_str}",
            })

    return diagnostics


def _attr_ref_is_builtin(attr_name: str) -> bool:
    """Check if attribute name is a Python builtin or common module attr."""
    builtins = {
        "format", "join", "split", "strip", "lower", "upper", "replace",
        "startswith", "endswith", "encode", "decode", "find", "count",
        "index", "isalpha", "isdigit", "isalnum", "isinstance", "issubclass",
        "keys", "values", "items", "update", "get", "pop", "append",
        "extend", "remove", "clear", "copy", "deepcopy", "hasattr",
        "getattr", "setattr", "len", "range", "type", "super", "repr",
        "str", "int", "float", "bool", "list", "dict", "set", "tuple",
        "open", "print", "input", "hash", "id", "dir", "vars", "help",
        "next", "iter", "enumerate", "zip", "map", "filter", "sorted",
        "reversed", "sum", "min", "max", "abs", "round", "pow",
        "divmod", "hex", "oct", "bin", "chr", "ord",
        "staticmethod", "classmethod", "property",
    }
    return attr_name in builtins


def _strip_comments(source: str) -> str:
    """Strip Python comments (single-line # and multi-line docstrings) from source.

    Keeps docstrings inside function/class bodies — only strips top-level
    comment noise that causes false positives in attribute pattern matching.
    """
    import re
    # Remove single-line comments
    source = re.sub(r'#[^\n]*', '', source)
    # Remove multi-line strings (docstrings at module level)
    source = re.sub(r'"""[\s\S]*?"""', '', source)
    source = re.sub(r"'''[\s\S]*?'''", '', source)
    return source

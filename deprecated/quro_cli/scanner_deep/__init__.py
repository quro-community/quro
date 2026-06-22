"""
scanner_deep — DeepScanner structural uncertainty annotation modules.

@module quro_cli.scanner_deep
@intent Read-only AST-based structural diagnostics. No DB writes, no semantic classification.

Package structure:
    class_signature.py  — AttributeSource enum, ClassSignature dataclass, extract_class_signature()
    deep_index.py        — SQLite Deep Index (class_signatures table), full rebuild
    audit_rules.py       — Diagnostic rule functions (UNBOUND_ATTRIBUTE_REFERENCE, etc.)
"""

# Package-level import for type hints
from quro_cli.scanner_deep.class_signature import AttributeSource, ClassSignature, extract_class_signature
from quro_cli.scanner_deep.deep_index import DeepIndex

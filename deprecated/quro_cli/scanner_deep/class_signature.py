"""
ClassSignature extraction — AST-based structural annotation.

@module quro_cli.scanner_deep.class_signature
@intent Extract class attributes and methods from Python AST. No semantic judgment.

Reports what was OBSERVED in AST, not what EXISTS at runtime.
"""

import ast
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class AttributeSource(str, Enum):
    """Source of an attribute observation.

    EXPLICIT_AST: self.x = ..., def method(self):
    PROPERTY_DECORATOR: @property, @staticmethod, @classmethod
    UNKNOWN_RUNTIME: everything else (not in signature)
    """
    EXPLICIT_AST = "explicit_ast"
    PROPERTY_DECORATOR = "property_decorator"
    UNKNOWN_RUNTIME = "unknown_runtime"


@dataclass(frozen=True)
class ClassSignature:
    """Immutable class signature extracted from AST.

    All fields are sets — lookup is O(1).
    observation_scope is always AST_ONLY — this is not a truth claim.
    """
    class_name: str
    file_path: str
    explicit_attrs: Tuple[str, ...] = ()
    property_attrs: Tuple[str, ...] = ()
    method_names: Tuple[str, ...] = ()
    observation_scope: str = "AST_ONLY"

    @property
    def all_observed(self) -> Set[str]:
        """Union of all observed names (for quick membership check)."""
        return set(self.explicit_attrs) | set(self.property_attrs) | set(self.method_names)

    def lookup(self, attr: str) -> Optional[AttributeSource]:
        """Check if attr was observed in AST. Returns source or None."""
        if attr in self.explicit_attrs:
            return AttributeSource.EXPLICIT_AST
        if attr in self.property_attrs:
            return AttributeSource.PROPERTY_DECORATOR
        if attr in self.method_names:
            return AttributeSource.EXPLICIT_AST
        return None


def extract_class_signature(
    source: str,
    file_path: str,
    class_name: Optional[str] = None,
) -> List[ClassSignature]:
    """Extract ClassSignature for all classes in a Python source file.

    Args:
        source: Python source text
        file_path: Relative file path (for provenance)
        class_name: If set, only extract this class (None = all classes)

    Returns:
        List of ClassSignature (empty if parse fails or class not found)

    Observation scope: AST_ONLY. Does not detect:
        - ORM dynamic fields (SQLAlchemy Column, Django model fields)
        - Monkey-patched attributes
        - __slots__ attributes (ambiguous — may not be in AST body)
        - getattr-based dynamic access
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        logger.debug("AST parse failed for %s: %s", file_path, e)
        return []

    classes: List[ast.ClassDef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if class_name is None or node.name == class_name:
                classes.append(node)

    if class_name is not None and not classes:
        return []

    signatures: List[ClassSignature] = []
    for cls_node in classes:
        sig = _extract_single_class(cls_node, file_path)
        if sig:
            signatures.append(sig)

    return signatures


def _extract_single_class(
    cls_node: ast.ClassDef,
    file_path: str,
) -> Optional[ClassSignature]:
    """Extract ClassSignature from a single ClassDef AST node."""
    explicit_attrs: List[str] = []
    property_attrs: List[str] = []
    method_names: List[str] = []

    for node in cls_node.body:
        # self.xxx = value in class body and __init__
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = _extract_self_attr(target)
                if name:
                    explicit_attrs.append(name)

        # self.xxx: Optional[T] annotations in __init__
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            name = _extract_self_attr(target)
            if name:
                explicit_attrs.append(name)

        # Method definitions (both sync and async)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check for @property / @staticmethod / @classmethod
            source = AttributeSource.PROPERTY_DECORATOR if _has_property_decorator(node) else AttributeSource.EXPLICIT_AST
            method_names.append(node.name)
            if source == AttributeSource.PROPERTY_DECORATOR and node.name not in property_attrs:
                property_attrs.append(node.name)

            # Walk into __init__ body for self.xxx assignments
            if node.name == "__init__":
                for stmt in node.body:
                    _collect_self_attrs(stmt, explicit_attrs)

    # Deduplicate (keep insertion order)
    explicit_attrs = list(dict.fromkeys(explicit_attrs).keys())
    property_attrs = list(dict.fromkeys(property_attrs).keys())
    method_names = list(dict.fromkeys(method_names).keys())

    return ClassSignature(
        class_name=cls_node.name,
        file_path=file_path,
        explicit_attrs=tuple(explicit_attrs),
        property_attrs=tuple(property_attrs),
        method_names=tuple(method_names),
    )


def _collect_self_attrs(stmt: ast.stmt, attrs: List[str]) -> None:
    """Recursively collect self.xxx = ... assignments from a statement."""
    if isinstance(stmt, ast.Assign):
        for target in stmt.targets:
            name = _extract_self_attr(target)
            if name:
                attrs.append(name)
    elif isinstance(stmt, ast.AnnAssign):
        name = _extract_self_attr(stmt.target)
        if name:
            attrs.append(name)
    elif isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try)):
        for child in stmt.body:
            _collect_self_attrs(child, attrs)
        orelse = getattr(stmt, 'orelse', [])
        for child in orelse:
            _collect_self_attrs(child, attrs)
        finalbody = getattr(stmt, 'finalbody', None)
        if finalbody:
            for child in finalbody:
                _collect_self_attrs(child, attrs)
    elif isinstance(stmt, ast.With):
        for child in stmt.body:
            _collect_self_attrs(child, attrs)


def _extract_self_attr(target: ast.expr) -> Optional[str]:
    """Extract attribute name from self.xxx pattern. Returns None if not self.xxx."""
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
        if target.value.id == "self":
            return target.attr
    return None


def _has_property_decorator(func_node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> bool:
    """Check if function has @property, @staticmethod, or @classmethod."""
    for decorator in func_node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id in ("property", "staticmethod", "classmethod"):
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr in ("property", "staticmethod", "classmethod"):
            return True
    return False

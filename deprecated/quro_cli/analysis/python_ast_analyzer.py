"""
Python AST Analyzer

Provides Python code analysis using the built-in ast module.
Extracts symbols, imports, exports, and type hints.
"""
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PythonSymbol:
    """Python symbol information"""
    name: str
    kind: str  # function, class, variable, method
    line: int
    col: int
    docstring: Optional[str] = None
    decorators: Optional[List[str]] = None
    type_hint: Optional[str] = None


@dataclass
class PythonImport:
    """Python import information"""
    module: str
    names: List[str]
    line: int
    alias: Optional[str] = None


class PythonASTAnalyzer:
    """Python AST analyzer for symbol extraction"""

    def __init__(self):
        """Initialize Python AST analyzer"""
        pass

    def parse_file(self, file_path: str) -> Optional[ast.AST]:
        """
        Parse Python file to AST

        Args:
            file_path: Path to Python file

        Returns:
            AST tree or None if parsing fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            return ast.parse(source, filename=file_path)
        except Exception as e:
            return None

    def extract_symbols(self, tree: ast.AST) -> List[PythonSymbol]:
        """
        Extract symbols from AST

        Args:
            tree: AST tree

        Returns:
            List of Python symbols
        """
        symbols = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Extract function
                docstring = ast.get_docstring(node)
                decorators = [self._get_decorator_name(d) for d in node.decorator_list]

                # Extract return type hint
                type_hint = None
                if node.returns:
                    type_hint = ast.unparse(node.returns)

                symbols.append(PythonSymbol(
                    name=node.name,
                    kind="function",
                    line=node.lineno,
                    col=node.col_offset,
                    docstring=docstring,
                    decorators=decorators,
                    type_hint=type_hint
                ))

            elif isinstance(node, ast.AsyncFunctionDef):
                # Extract async function
                docstring = ast.get_docstring(node)
                decorators = [self._get_decorator_name(d) for d in node.decorator_list]

                type_hint = None
                if node.returns:
                    type_hint = ast.unparse(node.returns)

                symbols.append(PythonSymbol(
                    name=node.name,
                    kind="async_function",
                    line=node.lineno,
                    col=node.col_offset,
                    docstring=docstring,
                    decorators=decorators,
                    type_hint=type_hint
                ))

            elif isinstance(node, ast.ClassDef):
                # Extract class
                docstring = ast.get_docstring(node)
                decorators = [self._get_decorator_name(d) for d in node.decorator_list]

                symbols.append(PythonSymbol(
                    name=node.name,
                    kind="class",
                    line=node.lineno,
                    col=node.col_offset,
                    docstring=docstring,
                    decorators=decorators
                ))

        return symbols

    def extract_imports(self, tree: ast.AST) -> List[PythonImport]:
        """
        Extract imports from AST

        Args:
            tree: AST tree

        Returns:
            List of Python imports
        """
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                # import foo, bar
                for alias in node.names:
                    imports.append(PythonImport(
                        module=alias.name,
                        names=[alias.name],
                        alias=alias.asname,
                        line=node.lineno
                    ))

            elif isinstance(node, ast.ImportFrom):
                # from foo import bar, baz
                if node.module:
                    names = [alias.name for alias in node.names]
                    imports.append(PythonImport(
                        module=node.module,
                        names=names,
                        alias=None,
                        line=node.lineno
                    ))

        return imports

    def extract_exports(self, tree: ast.AST) -> List[str]:
        """
        Extract exports from AST

        In Python, exports are typically defined via __all__

        Args:
            tree: AST tree

        Returns:
            List of exported symbol names
        """
        exports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Look for __all__ = [...]
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant):
                                    exports.append(elt.value)

        # If no __all__, consider top-level functions and classes as exports
        if not exports:
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not node.name.startswith('_'):
                        exports.append(node.name)

        return exports

    def get_file_symbols(self, file_path: str) -> List[PythonSymbol]:
        """
        Get all symbols from a Python file

        Args:
            file_path: Path to Python file

        Returns:
            List of Python symbols
        """
        tree = self.parse_file(file_path)
        if not tree:
            return []
        return self.extract_symbols(tree)

    def get_file_imports(self, file_path: str) -> List[PythonImport]:
        """
        Get all imports from a Python file

        Args:
            file_path: Path to Python file

        Returns:
            List of Python imports
        """
        tree = self.parse_file(file_path)
        if not tree:
            return []
        return self.extract_imports(tree)

    def get_file_exports(self, file_path: str) -> List[str]:
        """
        Get all exports from a Python file

        Args:
            file_path: Path to Python file

        Returns:
            List of exported symbol names
        """
        tree = self.parse_file(file_path)
        if not tree:
            return []
        return self.extract_exports(tree)

    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """
        Get decorator name from AST node

        Args:
            decorator: Decorator AST node

        Returns:
            Decorator name as string
        """
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return ast.unparse(decorator.func)
        return ast.unparse(decorator)

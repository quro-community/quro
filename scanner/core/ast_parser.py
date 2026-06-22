"""Scanner v3 - Python AST Parser

@module quro.scanner.core.ast_parser
@intent Pure Python AST parsing - extract symbols from source code
@constraint No I/O, no logging, deterministic
"""

import ast
from typing import List, Set
from scanner.types import ParsedSymbol


# Built-in exceptions and types that should not be indexed as symbols
PYTHON_BUILTINS = {
    # Exceptions
    'BaseException', 'Exception', 'StopIteration', 'StopAsyncIteration',
    'ArithmeticError', 'AssertionError', 'AttributeError', 'BufferError',
    'EOFError', 'FloatingPointError', 'GeneratorExit', 'ImportError',
    'ModuleNotFoundError', 'IndexError', 'KeyError', 'KeyboardInterrupt',
    'LookupError', 'MemoryError', 'NameError', 'NotImplementedError',
    'OSError', 'OverflowError', 'RecursionError', 'ReferenceError',
    'RuntimeError', 'SyntaxError', 'IndentationError', 'TabError',
    'SystemError', 'SystemExit', 'TypeError', 'UnboundLocalError',
    'UnicodeError', 'UnicodeDecodeError', 'UnicodeEncodeError',
    'UnicodeTranslateError', 'ValueError', 'ZeroDivisionError',
    'EnvironmentError', 'IOError', 'WindowsError',
    # Common built-in types
    'int', 'float', 'str', 'bool', 'list', 'dict', 'set', 'tuple',
    'frozenset', 'bytes', 'bytearray', 'memoryview', 'range',
    'object', 'type', 'super', 'property', 'staticmethod', 'classmethod',
    # Common built-in functions
    'print', 'len', 'range', 'enumerate', 'zip', 'map', 'filter',
    'sorted', 'reversed', 'sum', 'min', 'max', 'abs', 'round',
    'isinstance', 'issubclass', 'hasattr', 'getattr', 'setattr', 'delattr',
    'open', 'input', 'iter', 'next', 'callable', 'compile', 'eval', 'exec',
}


class PythonASTParser:
    """Pure Python AST parser.

    Extracts symbols (functions, classes, methods, variables) from Python source.

    Invariant: Pure function - same source → same symbols
    NO I/O, NO logging, NO mutations
    """

    @staticmethod
    def parse(source: str, file_path: str) -> List[ParsedSymbol]:
        """Parse Python source code and extract symbols.

        Args:
            source: Python source code
            file_path: File path (for error reporting)

        Returns:
            List of ParsedSymbol objects

        Raises:
            SyntaxError: If source code is invalid Python
        """
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            # Re-raise with file context
            raise SyntaxError(f"Failed to parse {file_path}: {e}") from e

        visitor = _SymbolVisitor(file_path)
        visitor.visit(tree)
        return visitor.symbols


class _SymbolVisitor(ast.NodeVisitor):
    """AST visitor to extract symbols.

    Visits AST nodes and collects function/class/method definitions.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.symbols: List[ParsedSymbol] = []
        self.current_class: str | None = None
        self.call_stack: List[str] = []  # Track nested scopes

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition."""
        self._extract_function(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definition."""
        self._extract_function(node, is_async=True)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition."""
        # Extract class symbol
        symbol = ParsedSymbol(
            name=node.name,
            kind="class",
            file_path=self.file_path,
            line=node.lineno,
            char=node.col_offset,
            decorators=tuple(self._extract_decorator_names(node)),
            docstring=ast.get_docstring(node),
            ast_kind="ClassDef",
        )
        self.symbols.append(symbol)

        # Visit methods inside class
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def _extract_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool):
        """Extract function or method symbol."""
        # Determine kind
        if self.current_class:
            kind = "async_method" if is_async else "method"
        else:
            kind = "async_function" if is_async else "function"

        # Extract signature
        signature = self._build_signature(node)

        # Extract calls
        calls = self._extract_calls(node)

        # Extract imports (from function body)
        imports = self._extract_imports(node)

        symbol = ParsedSymbol(
            name=node.name,
            kind=kind,
            file_path=self.file_path,
            line=node.lineno,
            char=node.col_offset,
            signature=signature,
            calls=tuple(calls),
            imports=tuple(imports),
            decorators=tuple(self._extract_decorator_names(node)),
            docstring=ast.get_docstring(node),
            ast_kind="AsyncFunctionDef" if is_async else "FunctionDef",
        )
        self.symbols.append(symbol)

    def _build_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Build function signature string."""
        # Extract argument names
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)

        # Extract return type
        returns = ""
        if node.returns:
            returns = f" -> {ast.unparse(node.returns)}"

        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({', '.join(args)}){returns}"

    def _extract_calls(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
        """Extract function/method calls from function body.

        Filters out Python built-ins (exceptions, types, functions) to prevent
        phantom nodes in the graph. Only user-defined symbols should be indexed.
        """
        calls: Set[str] = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                # Extract function name from call
                call_name = None
                if isinstance(child.func, ast.Name):
                    # Direct function call: foo()
                    call_name = child.func.id
                elif isinstance(child.func, ast.Attribute):
                    # Method call: obj.method() or self.method()
                    # Extract just the method name (not the object)
                    call_name = child.func.attr

                # Filter out Python built-ins
                if call_name and call_name not in PYTHON_BUILTINS:
                    calls.add(call_name)

        return sorted(calls)

    def _extract_imports(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
        """Extract import statements from function body."""
        imports: Set[str] = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    imports.add(alias.name)
            elif isinstance(child, ast.ImportFrom):
                if child.module:
                    imports.add(child.module)

        return sorted(imports)

    def _extract_decorator_names(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> List[str]:
        """Extract decorator names."""
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(f"@{dec.id}")
            elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                decorators.append(f"@{dec.func.id}")
            elif isinstance(dec, ast.Attribute):
                decorators.append(f"@{dec.attr}")
        return decorators

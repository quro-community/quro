"""
Call Graph Extractor - Extract function call relationships from Python AST

@module quro_cli.analysis.call_graph_extractor
@intent Extract caller-callee relationships for morphism edge creation
"""

import ast
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CallRelationship:
    """Represents a function call relationship"""
    caller: str  # Function name that makes the call
    callee: str  # Function/method name being called
    line: int    # Line number of the call
    is_method: bool = False  # True if calling a method (obj.method())


class CallGraphExtractor(ast.NodeVisitor):
    """
    Extract call graph from Python AST.

    Traverses AST to find all function calls and builds caller-callee relationships.
    """

    def __init__(self):
        self.calls: List[CallRelationship] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None
        self.function_stack: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        """Track current class context"""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track current function context"""
        # Build qualified name
        if self.current_class:
            func_name = f"{self.current_class}.{node.name}"
        else:
            func_name = node.name

        # Push onto stack
        old_function = self.current_function
        self.current_function = func_name
        self.function_stack.append(func_name)

        # Visit function body
        self.generic_visit(node)

        # Pop from stack
        self.function_stack.pop()
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Track async function context (same as regular function)"""
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call):
        """Extract call target"""
        if not self.current_function:
            # Call at module level, skip
            self.generic_visit(node)
            return

        callee = None
        is_method = False

        if isinstance(node.func, ast.Name):
            # Direct call: foo()
            callee = node.func.id
            is_method = False

        elif isinstance(node.func, ast.Attribute):
            # Method call: obj.foo() or module.foo()
            callee = node.func.attr
            is_method = True

            # Try to get full qualified name for known patterns
            if isinstance(node.func.value, ast.Name):
                # obj.method() or module.function()
                obj_name = node.func.value.id
                if obj_name == 'self':
                    # self.method() - qualify with current class
                    if self.current_class:
                        callee = f"{self.current_class}.{callee}"
                else:
                    # Could be module.function() or obj.method()
                    # Store as-is, let resolution happen later
                    pass

        elif isinstance(node.func, ast.Subscript):
            # Callable subscript: foo[bar]()
            # Skip for now
            pass

        if callee:
            self.calls.append(CallRelationship(
                caller=self.current_function,
                callee=callee,
                line=node.lineno,
                is_method=is_method
            ))

        self.generic_visit(node)

    def extract(self, tree: ast.AST) -> List[CallRelationship]:
        """
        Extract all call relationships from AST.

        Args:
            tree: Python AST tree

        Returns:
            List of CallRelationship objects
        """
        self.calls = []
        self.current_function = None
        self.current_class = None
        self.function_stack = []

        self.visit(tree)

        return self.calls

    def get_calls_by_function(self) -> Dict[str, List[str]]:
        """
        Get calls grouped by caller function.

        Returns:
            Dict mapping function name to list of called functions
        """
        calls_by_func: Dict[str, List[str]] = {}

        for call in self.calls:
            if call.caller not in calls_by_func:
                calls_by_func[call.caller] = []
            calls_by_func[call.caller].append(call.callee)

        return calls_by_func


def extract_call_graph(source_code: str, filename: str = '<unknown>') -> List[CallRelationship]:
    """
    Extract call graph from Python source code.

    Args:
        source_code: Python source code string
        filename: Optional filename for error messages

    Returns:
        List of CallRelationship objects
    """
    try:
        tree = ast.parse(source_code, filename=filename)
        extractor = CallGraphExtractor()
        return extractor.extract(tree)
    except SyntaxError as e:
        logger.error(f"Syntax error in {filename}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error extracting call graph from {filename}: {e}")
        return []


def extract_call_graph_from_file(file_path: str) -> List[CallRelationship]:
    """
    Extract call graph from Python file.

    Args:
        file_path: Path to Python file

    Returns:
        List of CallRelationship objects
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        return extract_call_graph(source_code, filename=file_path)
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return []

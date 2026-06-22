"""
Tests for Python AST Analyzer
"""
import pytest
from pathlib import Path
from quro_cli.analysis.python_ast_analyzer import PythonASTAnalyzer, PythonSymbol, PythonImport


@pytest.fixture
def analyzer():
    """Create PythonASTAnalyzer instance"""
    return PythonASTAnalyzer()


@pytest.fixture
def sample_python_file(tmp_path):
    """Create a sample Python file for testing"""
    file_path = tmp_path / "sample.py"
    content = '''
"""Sample module docstring"""
import os
import sys
from typing import List, Dict

class SampleClass:
    """Sample class docstring"""

    def __init__(self):
        self.value = 0

    def method(self) -> int:
        """Sample method"""
        return self.value

async def async_function(x: int) -> str:
    """Async function"""
    return str(x)

def regular_function(name: str) -> None:
    """Regular function"""
    print(name)

@property
def decorated_function():
    """Decorated function"""
    pass

variable: int = 42

__all__ = ["SampleClass", "async_function", "regular_function"]
'''
    file_path.write_text(content)
    return str(file_path)


def test_parse_file_success(analyzer, sample_python_file):
    """Test parsing a valid Python file"""
    tree = analyzer.parse_file(sample_python_file)
    assert tree is not None


def test_parse_file_not_found(analyzer):
    """Test parsing non-existent file"""
    tree = analyzer.parse_file("/nonexistent/file.py")
    assert tree is None


def test_extract_symbols_classes(analyzer, sample_python_file):
    """Test extracting class symbols"""
    tree = analyzer.parse_file(sample_python_file)
    symbols = analyzer.extract_symbols(tree)

    classes = [s for s in symbols if s.kind == "class"]
    assert len(classes) == 1
    assert classes[0].name == "SampleClass"
    assert classes[0].docstring == "Sample class docstring"


def test_extract_symbols_functions(analyzer, sample_python_file):
    """Test extracting function symbols"""
    tree = analyzer.parse_file(sample_python_file)
    symbols = analyzer.extract_symbols(tree)

    functions = [s for s in symbols if s.kind == "function"]
    assert len(functions) >= 2

    func_names = [f.name for f in functions]
    assert "regular_function" in func_names


def test_extract_symbols_async_functions(analyzer, sample_python_file):
    """Test extracting async function symbols"""
    tree = analyzer.parse_file(sample_python_file)
    symbols = analyzer.extract_symbols(tree)

    async_funcs = [s for s in symbols if s.kind == "async_function"]
    assert len(async_funcs) >= 1
    assert async_funcs[0].name == "async_function"
    assert async_funcs[0].type_hint == "str"


def test_extract_symbols_variables_not_extracted(analyzer, sample_python_file):
    """Test that annotated variable assignments (ast.AnnAssign) are NOT extracted.

    Module-level variables are not semantic symbols — they lack behavioral_tags,
    role, and intent. Removing them reduces noise sent to AI analysis.
    """
    tree = analyzer.parse_file(sample_python_file)
    symbols = analyzer.extract_symbols(tree)

    variables = [s for s in symbols if s.kind == "variable"]
    assert len(variables) == 0


def test_extract_imports(analyzer, sample_python_file):
    """Test extracting imports"""
    tree = analyzer.parse_file(sample_python_file)
    imports = analyzer.extract_imports(tree)

    assert len(imports) >= 2

    modules = [imp.module for imp in imports]
    assert "os" in modules
    assert "sys" in modules
    assert "typing" in modules


def test_extract_exports(analyzer, sample_python_file):
    """Test extracting exports"""
    tree = analyzer.parse_file(sample_python_file)
    exports = analyzer.extract_exports(tree)

    assert len(exports) == 3
    assert "SampleClass" in exports
    assert "async_function" in exports
    assert "regular_function" in exports


def test_get_file_symbols(analyzer, sample_python_file):
    """Test get_file_symbols convenience method"""
    symbols = analyzer.get_file_symbols(sample_python_file)
    assert len(symbols) > 0


def test_get_file_imports(analyzer, sample_python_file):
    """Test get_file_imports convenience method"""
    imports = analyzer.get_file_imports(sample_python_file)
    assert len(imports) > 0


def test_get_file_exports(analyzer, sample_python_file):
    """Test get_file_exports convenience method"""
    exports = analyzer.get_file_exports(sample_python_file)
    assert len(exports) == 3


def test_extract_symbols_with_decorators(analyzer, sample_python_file):
    """Test extracting symbols with decorators"""
    tree = analyzer.parse_file(sample_python_file)
    symbols = analyzer.extract_symbols(tree)

    decorated = [s for s in symbols if s.decorators]
    assert len(decorated) >= 1


def test_extract_symbols_with_type_hints(analyzer, sample_python_file):
    """Test extracting symbols with type hints"""
    tree = analyzer.parse_file(sample_python_file)
    symbols = analyzer.extract_symbols(tree)

    typed = [s for s in symbols if s.type_hint]
    assert len(typed) >= 1

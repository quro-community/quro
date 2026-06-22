"""
Tests for Tree-sitter Parser
"""
import pytest
from pathlib import Path
from quro_cli.analysis.treesitter_parser import TreeSitterParser, TreeSitterSymbol, TreeSitterImport


@pytest.fixture
def parser():
    """Create TreeSitterParser instance"""
    return TreeSitterParser()


@pytest.fixture
def sample_typescript_file(tmp_path):
    """Create a sample TypeScript file for testing"""
    file_path = tmp_path / "sample.ts"
    content = '''
import { foo, bar } from './module';
import baz from './other';

interface SampleInterface {
    name: string;
    value: number;
}

class SampleClass {
    constructor() {
        this.value = 0;
    }

    method(): number {
        return this.value;
    }
}

async function asyncFunction(x: number): Promise<string> {
    return String(x);
}

function regularFunction(name: string): void {
    console.log(name);
}

const variable = 42;
'''
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def sample_javascript_file(tmp_path):
    """Create a sample JavaScript file for testing"""
    file_path = tmp_path / "sample.js"
    content = '''
import { foo, bar } from './module';
import * as utils from './utils';

class SampleClass {
    constructor() {
        this.value = 0;
    }

    method() {
        return this.value;
    }
}

async function asyncFunction(x) {
    return String(x);
}

function regularFunction(name) {
    console.log(name);
}

const variable = 42;
let another = "test";
'''
    file_path.write_text(content)
    return str(file_path)


def test_parser_initialization(parser):
    """Test parser initialization"""
    assert parser is not None


def test_extract_symbols_regex_functions(parser, sample_typescript_file):
    """Test extracting function symbols using regex fallback"""
    with open(sample_typescript_file, 'r') as f:
        source = f.read()

    symbols = parser._extract_symbols_regex(source)
    functions = [s for s in symbols if s.kind == "function"]

    assert len(functions) >= 2
    func_names = [f.name for f in functions]
    assert "asyncFunction" in func_names
    assert "regularFunction" in func_names


def test_extract_symbols_regex_classes(parser, sample_typescript_file):
    """Test extracting class symbols using regex fallback"""
    with open(sample_typescript_file, 'r') as f:
        source = f.read()

    symbols = parser._extract_symbols_regex(source)
    classes = [s for s in symbols if s.kind == "class"]

    assert len(classes) >= 1
    assert classes[0].name == "SampleClass"


def test_extract_symbols_regex_interfaces(parser, sample_typescript_file):
    """Test extracting interface symbols using regex fallback"""
    with open(sample_typescript_file, 'r') as f:
        source = f.read()

    symbols = parser._extract_symbols_regex(source)
    interfaces = [s for s in symbols if s.kind == "interface"]

    assert len(interfaces) >= 1
    assert interfaces[0].name == "SampleInterface"


def test_extract_symbols_regex_variables(parser, sample_typescript_file):
    """Test extracting variable symbols using regex fallback"""
    with open(sample_typescript_file, 'r') as f:
        source = f.read()

    symbols = parser._extract_symbols_regex(source)
    variables = [s for s in symbols if s.kind == "variable"]

    assert len(variables) >= 1
    var_names = [v.name for v in variables]
    assert "variable" in var_names


def test_extract_imports_regex_named(parser, sample_typescript_file):
    """Test extracting named imports using regex fallback"""
    with open(sample_typescript_file, 'r') as f:
        source = f.read()

    imports = parser._extract_imports_regex(source)

    assert len(imports) >= 2

    # Check for { foo, bar } from './module'
    module_imports = [imp for imp in imports if imp.source == './module']
    assert len(module_imports) >= 1
    assert "foo" in module_imports[0].names
    assert "bar" in module_imports[0].names


def test_extract_imports_regex_default(parser, sample_typescript_file):
    """Test extracting default imports using regex fallback"""
    with open(sample_typescript_file, 'r') as f:
        source = f.read()

    imports = parser._extract_imports_regex(source)

    # Check for baz from './other'
    other_imports = [imp for imp in imports if imp.source == './other']
    assert len(other_imports) >= 1
    assert "baz" in other_imports[0].names


def test_extract_imports_regex_namespace(parser, sample_javascript_file):
    """Test extracting namespace imports using regex fallback"""
    with open(sample_javascript_file, 'r') as f:
        source = f.read()

    imports = parser._extract_imports_regex(source)

    # Check for * as utils from './utils'
    utils_imports = [imp for imp in imports if imp.source == './utils']
    assert len(utils_imports) >= 1
    assert "utils" in utils_imports[0].names


def test_get_file_symbols_typescript(parser, sample_typescript_file):
    """Test get_file_symbols for TypeScript file"""
    symbols = parser.get_file_symbols(sample_typescript_file)
    assert len(symbols) > 0


def test_get_file_symbols_javascript(parser, sample_javascript_file):
    """Test get_file_symbols for JavaScript file"""
    symbols = parser.get_file_symbols(sample_javascript_file)
    assert len(symbols) > 0


def test_get_file_imports_typescript(parser, sample_typescript_file):
    """Test get_file_imports for TypeScript file"""
    imports = parser.get_file_imports(sample_typescript_file)
    assert len(imports) > 0


def test_get_file_imports_javascript(parser, sample_javascript_file):
    """Test get_file_imports for JavaScript file"""
    imports = parser.get_file_imports(sample_javascript_file)
    assert len(imports) > 0


def test_get_file_symbols_nonexistent(parser):
    """Test get_file_symbols with non-existent file"""
    symbols = parser.get_file_symbols("/nonexistent/file.ts")
    assert len(symbols) == 0


def test_get_file_imports_nonexistent(parser):
    """Test get_file_imports with non-existent file"""
    imports = parser.get_file_imports("/nonexistent/file.ts")
    assert len(imports) == 0

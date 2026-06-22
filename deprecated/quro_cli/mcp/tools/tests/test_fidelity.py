"""
Test identify_symbol fidelity computation
"""
import pytest
from pathlib import Path
import tempfile
from quro_cli.mcp.tools.symbol_tools import SymbolTools


class TestFidelityComputation:
    """Test fidelity metric in identify_symbol"""

    @pytest.fixture
    def temp_workspace(self):
        """Create temp workspace with test files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            # Python file with 3 methods, symbol has 2
            py_file = workspace / "test_module.py"
            py_file.write_text('''
class MyClass:
    def method_one(self):
        """First method"""
        pass

    def method_two(self):
        """Second method"""
        pass

    def helper(self):
        """Helper"""
        pass
''')

            # TypeScript file with 4 methods, symbol has 2
            ts_file = workspace / "test_file.ts"
            ts_file.write_text('''
class LlmGuard {
    async acquire() {
        // acquire lock
    }

    async release() {
        // release lock
    }

    helper() {
        // helper
    }

    anotherMethod() {
        // another
    }
}
''')

            yield workspace

    def test_compute_fidelity_python(self, temp_workspace):
        """Test fidelity computation for Python symbol"""
        tools = SymbolTools(workspace_root=temp_workspace, db_pool=None, analyzer_getter=None)

        # Read full file
        source = (temp_workspace / "test_module.py").read_text()

        # Symbol body with 2 methods (out of 3 total)
        symbol_body = '''class MyClass:
    def method_one(self):
        """First method"""
        pass

    def method_two(self):
        """Second method"""
        pass
'''

        fidelity = tools._compute_fidelity(source, symbol_body, ".py")

        # 2 methods found, 3 total → 0.67
        assert 0.66 <= fidelity <= 0.68

    def test_compute_fidelity_typescript(self, temp_workspace):
        """Test fidelity computation for TypeScript symbol"""
        tools = SymbolTools(workspace_root=temp_workspace, db_pool=None, analyzer_getter=None)

        # Read full file
        source = (temp_workspace / "test_file.ts").read_text()

        # Symbol body with 2 methods (out of 4 total)
        symbol_body = '''class LlmGuard {
    async acquire() {
        // acquire lock
    }

    async release() {
        // release lock
    }
}
'''

        fidelity = tools._compute_fidelity(source, symbol_body, ".ts")

        # 2 methods found, 4 total → 0.5
        assert 0.49 <= fidelity <= 0.51

    def test_compute_fidelity_empty_symbol(self, temp_workspace):
        """Test fidelity with empty symbol body"""
        tools = SymbolTools(workspace_root=temp_workspace, db_pool=None, analyzer_getter=None)

        source = (temp_workspace / "test_module.py").read_text()
        fidelity = tools._compute_fidelity(source, "", ".py")

        # Empty symbol → fallback to 1.0
        assert fidelity == 1.0

    def test_compute_fidelity_all_methods(self, temp_workspace):
        """Test fidelity when all methods found"""
        tools = SymbolTools(workspace_root=temp_workspace, db_pool=None, analyzer_getter=None)

        source = (temp_workspace / "test_module.py").read_text()
        # Use entire file as symbol body
        fidelity = tools._compute_fidelity(source, source, ".py")

        # All methods → 1.0
        assert fidelity == 1.0

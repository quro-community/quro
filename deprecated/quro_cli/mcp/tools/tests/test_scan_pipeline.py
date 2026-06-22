"""
Tests for two-phase scan pipeline.

Phase 1 (scan): deterministic, local, fingerprint-aware diff
Phase 2 (enrich): AI, optional, conditional
"""
import hashlib
import pytest
from pathlib import Path
import tempfile

from quro_cli.mcp.tools.scan_tools import (
    compute_fingerprint,
    normalize_imports,
    compute_fidelity,
    detect_language,
)
from quro_cli.analysis.python_ast_analyzer import PythonImport


class TestComputeFingerprint:
    """SHA256(source + normalized_imports) captures semantic drift."""

    def test_same_source_same_imports_same_fingerprint(self):
        source = "class Foo: pass"
        imports = [{"source": "os", "names": ["path"], "line": 1}]
        fp1 = compute_fingerprint(source, normalize_imports(imports))
        fp2 = compute_fingerprint(source, normalize_imports(imports))
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_source_unchanged_import_changed_fingerprint_differs(self):
        source = "class LlmGuard: pass"

        imports_v1 = [{"source": "./async_lock", "names": ["AsyncLock"], "line": 1}]
        imports_v2 = [{"source": "./redis_lock", "names": ["RedisLock"], "line": 1}]

        fp1 = compute_fingerprint(source, normalize_imports(imports_v1))
        fp2 = compute_fingerprint(source, normalize_imports(imports_v2))

        assert fp1 != fp2  # Semantic drift detected

    def test_imports_unchanged_source_changed_fingerprint_differs(self):
        imports = [{"source": "os", "names": ["path"], "line": 1}]

        fp1 = compute_fingerprint("class Foo: pass", normalize_imports(imports))
        fp2 = compute_fingerprint("class Foo:\n    def bar(self): pass", normalize_imports(imports))

        assert fp1 != fp2

    def test_empty_imports(self):
        fp = compute_fingerprint("def foo(): pass", normalize_imports([]))
        assert len(fp) == 64

    def test_import_order_irrelevant(self):
        """Normalization sorts imports — order doesn't matter."""
        source = "class X: pass"

        imports_a = [
            {"source": "sys", "names": ["argv"], "line": 5},
            {"source": "os", "names": ["path"], "line": 1},
        ]
        imports_b = [
            {"source": "os", "names": ["path"], "line": 1},
            {"source": "sys", "names": ["argv"], "line": 5},
        ]

        fp_a = compute_fingerprint(source, normalize_imports(imports_a))
        fp_b = compute_fingerprint(source, normalize_imports(imports_b))
        assert fp_a == fp_b


class TestNormalizeImports:
    def test_sorts_by_source(self):
        imports = [
            {"source": "sys", "names": ["argv"], "line": 2},
            {"source": "os", "names": ["path"], "line": 1},
        ]
        result = normalize_imports(imports)
        lines = result.strip().split("\n")
        assert lines[0].startswith("os:")
        assert lines[1].startswith("sys:")

    def test_empty_list(self):
        assert normalize_imports([]) == ""

    def test_sorts_names_within_import(self):
        imports = [{"source": "os", "names": ["path", "environ"], "line": 1}]
        result = normalize_imports(imports)
        assert "environ,path" in result


class TestComputeFidelity:
    def test_perfect_fidelity(self):
        source = "def a(): pass\ndef b(): pass\n"
        bodies = ["def a(): pass", "def b(): pass"]
        assert compute_fidelity(source, bodies, ".py") == 1.0

    def test_partial_fidelity(self):
        source = "def a(): pass\ndef b(): pass\ndef c(): pass\n"
        bodies = ["def a(): pass", "def b(): pass"]
        result = compute_fidelity(source, bodies, ".py")
        assert 0.66 <= result <= 0.67  # 2/3

    def test_zero_methods_in_symbol(self):
        source = "def a(): pass\ndef b(): pass\n"
        assert compute_fidelity(source, ["class Foo: pass"], ".py") == 0.0

    def test_no_methods_in_file(self):
        """No methods → fidelity = 1.0 (nothing to miss)."""
        source = "# just a comment\n"
        assert compute_fidelity(source, [], ".py") == 1.0

    def test_empty_source(self):
        assert compute_fidelity("", [], ".py") == 1.0

    def test_async_methods_counted(self):
        source = "async def a(): pass\ndef b(): pass\n"
        bodies = ["async def a(): pass"]
        result = compute_fidelity(source, bodies, ".py")
        assert 0.49 <= result <= 0.51  # 1/2

    def test_typescript_methods(self):
        source = "function a() {}\nfunction b() {}\nfunction c() {}\n"
        bodies = ["function a() {}\nfunction b() {}"]
        result = compute_fidelity(source, bodies, ".ts")
        assert 0.66 <= result <= 0.67  # 2/3

    def test_capped_at_one(self):
        """Fidelity never exceeds 1.0 even if overcounting."""
        source = "def a(): pass\n"
        bodies = ["def a(): pass", "def a(): pass"]  # counted twice
        assert compute_fidelity(source, bodies, ".py") == 1.0


class TestNormalizeImportsWithPythonImport:
    """normalize_imports must handle PythonImport dataclass objects (not just dicts)."""

    def test_python_import_objects(self):
        imports = [
            PythonImport(module="sys", names=["argv"], line=5),
            PythonImport(module="os", names=["path"], line=1),
        ]
        result = normalize_imports(imports)
        assert "os:path" in result
        assert "sys:argv" in result

    def test_mixed_dict_and_python_import(self):
        imports = [
            PythonImport(module="os", names=["path"], line=1),
            {"source": "sys", "names": ["argv"], "line": 2},
        ]
        result = normalize_imports(imports)
        lines = result.strip().split("\n")
        assert lines[0].startswith("os:")
        assert lines[1].startswith("sys:")

    def test_fingerprint_with_python_imports(self):
        source = "class Foo: pass"
        imports = [PythonImport(module="os", names=["path"], line=1)]
        fp = compute_fingerprint(source, normalize_imports(imports))
        assert len(fp) == 64


class TestDetectLanguage:
    def test_python(self):
        assert detect_language(".py") == "python"

    def test_typescript(self):
        assert detect_language(".ts") == "typescript"
        assert detect_language(".tsx") == "typescript"

    def test_javascript(self):
        assert detect_language(".js") == "javascript"
        assert detect_language(".jsx") == "javascript"

    def test_unknown(self):
        assert detect_language(".txt") is None
        assert detect_language(".md") is None

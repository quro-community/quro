"""Tests for DeepScanner audit rules — diagnostic functions."""
import pytest

from quro_cli.scanner_deep.class_signature import ClassSignature
from quro_cli.scanner_deep.audit_rules import (
    check_unbound_attributes,
    check_structural_mismatch,
    check_deprecated_references,
    check_dual_write_patterns,
    _attr_ref_is_builtin,
)


def _make_sig(class_name: str, file_path: str = "test.py", **kwargs) -> ClassSignature:
    defaults = {"explicit_attrs": (), "property_attrs": (), "method_names": ()}
    defaults.update(kwargs)
    return ClassSignature(class_name=class_name, file_path=file_path, **defaults)


class TestCheckUnboundAttributes:
    """Test UNBOUND_ATTRIBUTE_REFERENCE detection."""

    def test_no_unbound(self):
        """All referenced attrs are observed — no diagnostics."""
        sigs = [_make_sig("Foo", "a.py", explicit_attrs=("x", "y"), method_names=("run",))]
        source = "Foo.x\nFoo.y\nFoo.run"
        diags = check_unbound_attributes("a.py", source, sigs)
        assert len(diags) == 0

    def test_unbound_detected(self):
        """Unobserved attr triggers diagnostic."""
        sigs = [_make_sig("Foo", "a.py", explicit_attrs=("x",))]
        source = "Foo.x\nFoo.nonexistent"
        diags = check_unbound_attributes("a.py", source, sigs)
        assert len(diags) == 1
        assert diags[0]["type"] == "UNBOUND_ATTRIBUTE_REFERENCE"
        assert diags[0]["class_name"] == "Foo"
        assert diags[0]["attribute"] == "nonexistent"
        assert diags[0]["observation_scope"] == "AST_ONLY"

    def test_multiple_unbound(self):
        """Multiple unbound attrs — each unique pair reported once."""
        sigs = [_make_sig("Foo", "a.py")]
        source = "Foo.a\nFoo.b\nFoo.a"
        diags = check_unbound_attributes("a.py", source, sigs)
        assert len(diags) == 2
        attrs = {d["attribute"] for d in diags}
        assert attrs == {"a", "b"}

    def test_builtin_skip(self):
        """Builtin attrs are not reported as unbound."""
        sigs = [_make_sig("Foo", "a.py")]
        source = "Foo.format\nFoo.keys\nFoo.append"
        diags = check_unbound_attributes("a.py", source, sigs)
        assert len(diags) == 0

    def test_module_skip(self):
        """Standard library modules are skipped."""
        sigs = [_make_sig("Foo", "a.py")]
        source = "os.path\njson.loads\nPath.cwd"
        diags = check_unbound_attributes("a.py", source, sigs)
        assert len(diags) == 0

    def test_private_class_skip(self):
        """Class names starting with _ are skipped (class_ref, not attr)."""
        sigs = [_make_sig("Foo", "a.py")]
        source = "_Helper.something"
        diags = check_unbound_attributes("a.py", source, sigs)
        assert len(diags) == 0

    def test_private_attr_reported(self):
        """Private attrs (_private) are reported if class is known."""
        sigs = [_make_sig("Foo", "a.py")]
        source = "Foo._private"
        diags = check_unbound_attributes("a.py", source, sigs)
        assert len(diags) == 1
        assert diags[0]["attribute"] == "_private"

    def test_unknown_class_ignored(self):
        """References to classes not in signatures are ignored."""
        sigs = [_make_sig("Foo", "a.py")]
        source = "Bar.unknown_attr"
        diags = check_unbound_attributes("a.py", source, sigs)
        assert len(diags) == 0

    def test_method_recognized(self):
        """Methods in method_names are not reported as unbound."""
        sigs = [_make_sig("Foo", "a.py", method_names=("compute", "run"))]
        source = "Foo.compute\nFoo.run"
        diags = check_unbound_attributes("a.py", source, sigs)
        assert len(diags) == 0

    def test_property_recognized(self):
        """Property attrs are not reported as unbound."""
        sigs = [_make_sig("Foo", "a.py", property_attrs=("value",))]
        source = "Foo.value"
        diags = check_unbound_attributes("a.py", source, sigs)
        assert len(diags) == 0


class TestCheckStructuralMismatch:
    """Test STRUCTURAL_MISMATCH detection."""

    def test_no_mismatch(self):
        """All registry symbols found in git AST — no diagnostics."""
        registry = [
            {"symbol_name": "Foo", "file_path": "a.py"},
            {"symbol_name": "Bar", "file_path": "b.py"},
        ]
        git_ast = {"a.py::Foo", "b.py::Bar"}
        diags = check_structural_mismatch(registry, git_ast)
        assert len(diags) == 0

    def test_mismatch_detected(self):
        """Registry symbol not in git AST triggers diagnostic."""
        registry = [
            {"symbol_name": "Foo", "file_path": "a.py"},
            {"symbol_name": "Deleted", "file_path": "a.py"},
        ]
        git_ast = {"a.py::Foo"}
        diags = check_structural_mismatch(registry, git_ast)
        assert len(diags) == 1
        assert diags[0]["type"] == "STRUCTURAL_MISMATCH"
        assert diags[0]["symbol"] == "Deleted"
        assert diags[0]["registry_has"] is True
        assert diags[0]["git_has"] is False

    def test_empty_inputs(self):
        """Empty inputs produce no diagnostics."""
        diags = check_structural_mismatch([], set())
        assert len(diags) == 0


class TestCheckDeprecatedReferences:
    """Test DEPRECATED_SYMBOL_STILL_REFERENCED detection."""

    def test_no_references(self):
        """Deprecated symbol not referenced — no diagnostics."""
        deprecated = [{"symbol_name": "OldAPI", "deprecated_at": "2026-01-01"}]
        sources = {"current.py": "def foo(): pass"}
        diags = check_deprecated_references(deprecated, sources)
        assert len(diags) == 0

    def test_reference_detected(self):
        """Deprecated symbol referenced in active file triggers diagnostic."""
        deprecated = [{"symbol_name": "OldAPI", "deprecated_at": "2026-01-01"}]
        sources = {"current.py": "from old import OldAPI\nresult = OldAPI()"}
        diags = check_deprecated_references(deprecated, sources)
        assert len(diags) == 1
        assert diags[0]["type"] == "DEPRECATED_SYMBOL_STILL_REFERENCED"
        assert diags[0]["symbol"] == "OldAPI"
        assert diags[0]["referenced_in"] == "current.py"
        assert diags[0]["reference_count"] == 2

    def test_multiple_files(self):
        """Same deprecated symbol in multiple files — one diagnostic per file."""
        deprecated = [{"symbol_name": "OldAPI", "deprecated_at": "2026-01-01"}]
        sources = {
            "a.py": "OldAPI()",
            "b.py": "OldAPI.call()",
        }
        diags = check_deprecated_references(deprecated, sources)
        assert len(diags) == 2
        files = {d["referenced_in"] for d in diags}
        assert files == {"a.py", "b.py"}

    def test_empty_symbol_name(self):
        """Symbols with empty name are skipped."""
        deprecated = [{"symbol_name": "", "deprecated_at": "2026-01-01"}]
        sources = {"a.py": "pass"}
        diags = check_deprecated_references(deprecated, sources)
        assert len(diags) == 0


class TestCheckDualWritePatterns:
    """Test DUAL_WRITE_PATTERN detection."""

    def test_single_insert(self):
        """Single INSERT — no diagnostic."""
        source = "INSERT INTO users VALUES (1, 'alice')"
        diags = check_dual_write_patterns(source, "query.py")
        assert len(diags) == 0

    def test_dual_insert(self):
        """Two INSERT INTO same scope — triggers diagnostic."""
        source = "INSERT INTO users VALUES (1, 'alice')\nINSERT INTO audit_log VALUES (1, 'created')"
        diags = check_dual_write_patterns(source, "query.py")
        assert len(diags) == 1
        assert diags[0]["type"] == "DUAL_WRITE_PATTERN"
        assert len(diags[0]["tables"]) == 2

    def test_allowed_pattern(self):
        """Dual write with allowed pattern keyword — suppressed."""
        source = "INSERT INTO users VALUES (1, 'alice')\nINSERT INTO audit_log VALUES (1, 'created')\n# shadow_write bridge"
        diags = check_dual_write_patterns(source, "query.py")
        assert len(diags) == 0

    def test_comment_lines_ignored(self):
        """INSERT in comments is not counted."""
        source = "# INSERT INTO ignored VALUES (1)\nINSERT INTO real VALUES (1)"
        diags = check_dual_write_patterns(source, "query.py")
        assert len(diags) == 0

    def test_case_insensitive(self):
        """INSERT INTO is case-insensitive."""
        source = "insert into foo values (1)\nINSERT INTO bar values (2)"
        diags = check_dual_write_patterns(source, "query.py")
        assert len(diags) == 1


class TestAttrRefIsBuiltin:
    """Test the _attr_ref_is_builtin helper."""

    def test_common_builtins(self):
        """Standard Python builtins return True."""
        for name in ("format", "join", "split", "keys", "values", "items",
                      "append", "extend", "get", "pop", "len", "range",
                      "open", "print", "isinstance", "hasattr"):
            assert _attr_ref_is_builtin(name), f"{name} should be builtin"

    def test_non_builtins(self):
        """Custom names return False."""
        for name in ("compute", "processData", "customMethod", "foo_bar"):
            assert not _attr_ref_is_builtin(name), f"{name} should not be builtin"

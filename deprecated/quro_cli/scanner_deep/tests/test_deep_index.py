"""Tests for Deep Index — SQLite storage for ClassSignature data."""
import json
import pytest

from quro_cli.scanner_deep.class_signature import ClassSignature
from quro_cli.scanner_deep.deep_index import DeepIndex


def _make_sig(class_name: str, file_path: str = "test.py", **kwargs) -> ClassSignature:
    """Helper to create ClassSignature with defaults."""
    defaults = {
        "explicit_attrs": (),
        "property_attrs": (),
        "method_names": (),
    }
    defaults.update(kwargs)
    return ClassSignature(class_name=class_name, file_path=file_path, **defaults)


class TestDeepIndexInMemory:
    """Test DeepIndex in-memory mode."""

    def test_rebuild_empty(self):
        """Rebuild with empty signatures returns 0."""
        idx = DeepIndex(in_memory=True)
        count = idx.rebuild([])
        assert count == 0
        idx.close()

    def test_rebuild_and_count(self):
        """Rebuild stores all signatures and count matches."""
        sigs = [
            _make_sig("Foo", "a.py", explicit_attrs=("x",)),
            _make_sig("Bar", "b.py", method_names=("run",)),
        ]
        idx = DeepIndex(in_memory=True)
        count = idx.rebuild(sigs)
        assert count == 2
        assert idx.class_count() == 2
        idx.close()

    def test_lookup_class_found(self):
        """lookup_class returns the correct ClassSignature."""
        sigs = [_make_sig("Foo", "a.py", explicit_attrs=("x", "y"), method_names=("run",))]
        idx = DeepIndex(in_memory=True)
        idx.rebuild(sigs)

        result = idx.lookup_class("a.py", "Foo")
        assert result is not None
        assert result.class_name == "Foo"
        assert result.file_path == "a.py"
        assert result.explicit_attrs == ("x", "y")
        assert result.method_names == ("run",)
        assert result.observation_scope == "AST_ONLY"
        idx.close()

    def test_lookup_class_not_found(self):
        """lookup_class returns None for missing class."""
        idx = DeepIndex(in_memory=True)
        idx.rebuild([_make_sig("Foo", "a.py")])
        result = idx.lookup_class("a.py", "NonExistent")
        assert result is None
        idx.close()

    def test_lookup_file(self):
        """lookup_file returns all classes for a file."""
        sigs = [
            _make_sig("Foo", "a.py"),
            _make_sig("Bar", "a.py"),
            _make_sig("Baz", "b.py"),
        ]
        idx = DeepIndex(in_memory=True)
        idx.rebuild(sigs)

        result = idx.lookup_file("a.py")
        assert len(result) == 2
        names = {s.class_name for s in result}
        assert names == {"Foo", "Bar"}
        idx.close()

    def test_lookup_file_empty(self):
        """lookup_file returns empty list for file with no classes."""
        idx = DeepIndex(in_memory=True)
        idx.rebuild([_make_sig("Foo", "a.py")])
        result = idx.lookup_file("b.py")
        assert result == []
        idx.close()

    def test_get_all_signatures(self):
        """get_all_signatures returns all indexed classes."""
        sigs = [
            _make_sig("Foo", "a.py"),
            _make_sig("Bar", "b.py"),
        ]
        idx = DeepIndex(in_memory=True)
        idx.rebuild(sigs)
        result = idx.get_all_signatures()
        assert len(result) == 2
        idx.close()

    def test_rebuild_overwrites(self):
        """Second rebuild replaces all data."""
        sigs_v1 = [_make_sig("Foo", "a.py")]
        sigs_v2 = [_make_sig("Bar", "a.py"), _make_sig("Baz", "b.py")]

        idx = DeepIndex(in_memory=True)
        idx.rebuild(sigs_v1)
        assert idx.class_count() == 1

        idx.rebuild(sigs_v2)
        assert idx.class_count() == 2
        assert idx.lookup_class("a.py", "Foo") is None
        assert idx.lookup_class("a.py", "Bar") is not None
        idx.close()

    def test_source_hashes_stored(self):
        """Source hashes are stored alongside signatures."""
        sigs = [_make_sig("Foo", "a.py")]
        idx = DeepIndex(in_memory=True)
        idx.rebuild(sigs, source_hashes={"a.py": "abc123"})
        result = idx.lookup_class("a.py", "Foo")
        assert result is not None
        idx.close()

    def test_close_is_idempotent(self):
        """close() can be called multiple times safely."""
        idx = DeepIndex(in_memory=True)
        idx.close()
        idx.close()  # Should not raise


class TestDeepIndexPersisted:
    """Test DeepIndex persisted mode (uses temp directory)."""

    def test_persisted_rebuild(self, tmp_path):
        """Persisted mode creates DB file and stores data."""
        db_path = str(tmp_path / "sub" / "dir" / "test.db")
        sigs = [_make_sig("Foo", "a.py", explicit_attrs=("x",))]

        idx = DeepIndex(db_path=db_path)
        count = idx.rebuild(sigs)
        assert count == 1

        # Verify file was created
        assert (tmp_path / "sub" / "dir" / "test.db").exists()
        idx.close()

    def test_persisted_lookup(self, tmp_path):
        """Data persists across connections (file-based)."""
        db_path = str(tmp_path / "test.db")
        sigs = [_make_sig("Foo", "a.py", explicit_attrs=("x",))]

        idx1 = DeepIndex(db_path=db_path)
        idx1.rebuild(sigs)
        idx1.close()

        # Open new connection to same DB
        idx2 = DeepIndex(db_path=db_path)
        result = idx2.lookup_class("a.py", "Foo")
        assert result is not None
        assert result.explicit_attrs == ("x",)
        idx2.close()

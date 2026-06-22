"""Tests for ClassSignature extraction — AST-based structural annotation."""
import pytest

from quro_cli.scanner_deep.class_signature import (
    AttributeSource,
    ClassSignature,
    extract_class_signature,
)


class TestExtractClassSignature:
    """Test extract_class_signature function."""

    def test_basic_class(self):
        """Extraction from a simple class with methods and attributes."""
        source = """
class Foo:
    def __init__(self):
        self.x = 1
        self.y = "hello"

    def method_a(self):
        return self.x

    async def async_method(self):
        await self.method_a()
"""
        sigs = extract_class_signature(source, "test.py")
        assert len(sigs) == 1
        sig = sigs[0]
        assert sig.class_name == "Foo"
        assert sig.file_path == "test.py"
        assert "x" in sig.explicit_attrs
        assert "y" in sig.explicit_attrs
        assert "method_a" in sig.method_names
        assert "async_method" in sig.method_names
        assert sig.observation_scope == "AST_ONLY"

    def test_property_decorator(self):
        """@property and @staticmethod should appear in property_attrs."""
        source = """
class Bar:
    @property
    def computed(self):
        return 42

    @staticmethod
    def helper():
        pass

    @classmethod
    def from_dict(cls, data):
        return cls()
"""
        sigs = extract_class_signature(source, "test.py")
        assert len(sigs) == 1
        sig = sigs[0]
        assert "computed" in sig.property_attrs
        assert "helper" in sig.property_attrs
        assert "from_dict" in sig.property_attrs

    def test_empty_class(self):
        """Empty class should have no attributes."""
        source = "class Empty:\n    pass\n"
        sigs = extract_class_signature(source, "test.py")
        assert len(sigs) == 1
        sig = sigs[0]
        assert sig.class_name == "Empty"
        assert len(sig.explicit_attrs) == 0
        assert len(sig.method_names) == 0

    def test_multiple_classes(self):
        """Extract all classes when class_name is None."""
        source = """
class Alpha:
    def a(self):
        pass

class Beta:
    def b(self):
        pass
"""
        sigs = extract_class_signature(source, "test.py")
        assert len(sigs) == 2
        names = {s.class_name for s in sigs}
        assert names == {"Alpha", "Beta"}

    def test_filter_by_class_name(self):
        """Extract only the specified class."""
        source = """
class Alpha:
    def a(self): pass
class Beta:
    def b(self): pass
"""
        sigs = extract_class_signature(source, "test.py", class_name="Beta")
        assert len(sigs) == 1
        assert sigs[0].class_name == "Beta"

    def test_class_not_found(self):
        """Return empty list when class_name doesn't match."""
        source = "class Alpha:\n    pass\n"
        sigs = extract_class_signature(source, "test.py", class_name="NonExistent")
        assert sigs == []

    def test_syntax_error(self):
        """Return empty list on syntax error."""
        sigs = extract_class_signature("def broken(:\n", "test.py")
        assert sigs == []

    def test_init_with_nested_control_flow(self):
        """self.xxx assignments inside if/for/try in __init__."""
        source = """
class Controller:
    def __init__(self, config):
        self.config = config
        if config.get("debug"):
            self.debug = True
        for name in config.get("plugins", []):
            self.plugins = []
        try:
            self.client = create_client()
        except Exception:
            self.client = None
"""
        sigs = extract_class_signature(source, "test.py")
        assert len(sigs) == 1
        sig = sigs[0]
        assert "config" in sig.explicit_attrs
        assert "debug" in sig.explicit_attrs
        assert "plugins" in sig.explicit_attrs
        assert "client" in sig.explicit_attrs

    def test_type_annotations_in_init(self):
        """self.xxx: Optional[T] annotations in __init__."""
        source = """
class Service:
    def __init__(self):
        self.name: str = "default"
        self._cache: Optional[dict] = None
"""
        sigs = extract_class_signature(source, "test.py")
        assert len(sigs) == 1
        sig = sigs[0]
        assert "name" in sig.explicit_attrs
        assert "_cache" in sig.explicit_attrs

    def test_class_body_assignment(self):
        """Class-level self.xxx = ... (unusual but valid)."""
        source = """
class Shared:
    counter = 0

    def __init__(self):
        self.instance_id = id(self)
"""
        sigs = extract_class_signature(source, "test.py")
        assert len(sigs) == 1
        # counter is class-level (not self.xxx), so not in explicit_attrs
        # instance_id is in __init__
        assert "instance_id" in sigs[0].explicit_attrs


class TestClassSignature:
    """Test ClassSignature dataclass behavior."""

    def test_frozen(self):
        """ClassSignature should be immutable."""
        source = "class Foo:\n    def m(self): pass\n"
        sigs = extract_class_signature(source, "test.py")
        sig = sigs[0]
        with pytest.raises(AttributeError):
            sig.class_name = "Bar"

    def test_lookup_explicit(self):
        """lookup returns EXPLICIT_AST for explicit attrs."""
        sig = ClassSignature(
            class_name="Test",
            file_path="test.py",
            explicit_attrs=("x", "y"),
            method_names=("run",),
        )
        assert sig.lookup("x") == AttributeSource.EXPLICIT_AST
        assert sig.lookup("run") == AttributeSource.EXPLICIT_AST

    def test_lookup_property(self):
        """lookup returns PROPERTY_DECORATOR for property attrs."""
        sig = ClassSignature(
            class_name="Test",
            file_path="test.py",
            property_attrs=("computed",),
        )
        assert sig.lookup("computed") == AttributeSource.PROPERTY_DECORATOR

    def test_lookup_missing(self):
        """lookup returns None for unobserved attributes."""
        sig = ClassSignature(
            class_name="Test",
            file_path="test.py",
            explicit_attrs=("x",),
        )
        assert sig.lookup("nonexistent") is None

    def test_all_observed(self):
        """all_observed returns union of all sets."""
        sig = ClassSignature(
            class_name="Test",
            file_path="test.py",
            explicit_attrs=("a", "b"),
            property_attrs=("c",),
            method_names=("d",),
        )
        assert sig.all_observed == {"a", "b", "c", "d"}

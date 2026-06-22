"""
DeepScanner test fixture — intentional scenarios for E2E verification.

@module quro_cli.test_fixtures.deep_scanner_fixture
@intent Provides target files with known structural issues that DeepScanner should detect.
"""

# Scenario 1: UNBOUND_ATTRIBUTE_REFERENCE
# Foo has 'genuine' and '_cache' in AST.
# The test code below references Foo.nonexistent — which is NOT in AST.
class Foo:
    """A class with both valid and unbound attribute references."""

    def __init__(self):
        self.genuine = True
        self._cache = {}

    def compute(self, value: int) -> int:
        """A real method that uses genuine attrs."""
        result = self.genuine * value
        return result

    @property
    def cached(self):
        return self._cache

    @staticmethod
    def helper():
        return 42

    def process(self, data: dict) -> dict:
        """Process data using cache."""
        cleaned = self.helper()
        return data


class Bar:
    """A class that intentionally references an unbound attribute on Foo."""

    def check(self) -> bool:
        # Foo.genuine is valid — exists in AST
        val = Foo.genuine
        # Foo.nonexistent is NOT in Foo's AST — should trigger UNBOUND
        return Foo.nonexistent

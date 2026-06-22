"""Scanner v3 - File Filter Gate

@module quro.scanner.gates.file_filter
@intent Stateless file filtering (quroignore, size limits, binary detection)
@constraint Pure function, no mutations
"""

from pathlib import Path
from typing import Set
from scanner.gates.types import GateResult


class FileFilterGate:
    """Stateless file filtering gate.

    Filters files based on:
    - .quroignore rules
    - File size limits
    - Binary file detection
    - Extension whitelist

    Invariant: Pure function - same file → same result
    """

    # File size limit (10MB)
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

    # Supported extensions
    SUPPORTED_EXTENSIONS = {".py", ".pyi"}

    # Binary file detection (check first N bytes)
    BINARY_CHECK_BYTES = 8192

    def __init__(self, workspace_root: Path, quroignore_patterns: Set[str] | None = None):
        """Initialize file filter gate.

        Args:
            workspace_root: Workspace root directory
            quroignore_patterns: Optional .quroignore patterns (if None, loads from file)
        """
        self.workspace_root = Path(workspace_root).resolve()
        self.quroignore_patterns = quroignore_patterns or self._load_quroignore()

    def validate(self, file_path: Path) -> GateResult:
        """Validate file against filter rules.

        Pure function: file_path → GateResult

        Args:
            file_path: File path to validate (absolute or relative to workspace)

        Returns:
            GateResult with passed=True if file should be scanned
        """
        # Resolve to absolute path
        if not file_path.is_absolute():
            file_path = (self.workspace_root / file_path).resolve()

        # Sub-gate 1: File must exist
        if not file_path.exists():
            return GateResult(passed=False, reason="file_not_found")

        # Sub-gate 2: Must be a file (not directory)
        if not file_path.is_file():
            return GateResult(passed=False, reason="not_a_file")

        # Sub-gate 3: Extension whitelist
        if file_path.suffix not in self.SUPPORTED_EXTENSIONS:
            return GateResult(passed=False, reason="unsupported_extension")

        # Sub-gate 4: .quroignore rules
        relative_path = self._get_relative_path(file_path)
        if self._is_ignored(relative_path):
            return GateResult(passed=False, reason="quroignore")

        # Sub-gate 5: File size limit
        try:
            file_size = file_path.stat().st_size
            if file_size > self.MAX_FILE_SIZE_BYTES:
                return GateResult(
                    passed=False,
                    reason="file_too_large",
                    metadata={"size_bytes": file_size, "limit_bytes": self.MAX_FILE_SIZE_BYTES},
                )
        except OSError:
            return GateResult(passed=False, reason="file_stat_error")

        # Sub-gate 6: Binary file detection
        if self._is_binary(file_path):
            return GateResult(passed=False, reason="binary_file")

        # All gates passed
        return GateResult(passed=True, metadata={"size_bytes": file_size})

    def _load_quroignore(self) -> Set[str]:
        """Load .quroignore patterns from workspace root.

        Returns:
            Set of ignore patterns
        """
        quroignore_path = self.workspace_root / ".quroignore"
        if not quroignore_path.exists():
            return self._get_default_patterns()

        patterns = set()
        try:
            with open(quroignore_path, "r") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith("#"):
                        patterns.add(line)
        except OSError:
            # If can't read, use defaults
            return self._get_default_patterns()

        return patterns

    def _get_default_patterns(self) -> Set[str]:
        """Get default ignore patterns.

        Returns:
            Set of default patterns
        """
        return {
            # Python
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".Python",
            "*.so",
            "*.egg",
            "*.egg-info",
            "dist",
            "build",
            ".eggs",
            # Virtual environments
            "venv",
            ".venv",
            "env",
            ".env",
            # IDE
            ".vscode",
            ".idea",
            "*.swp",
            "*.swo",
            # Version control
            ".git",
            ".svn",
            ".hg",
            # Node
            "node_modules",
            # Quro
            ".quro_context",
            ".quroignore",
        }

    def _get_relative_path(self, file_path: Path) -> str:
        """Get path relative to workspace root.

        Args:
            file_path: Absolute file path

        Returns:
            Relative path string
        """
        try:
            return str(file_path.relative_to(self.workspace_root))
        except ValueError:
            # File is outside workspace
            return str(file_path)

    def _is_ignored(self, relative_path: str) -> bool:
        """Check if path matches any ignore pattern.

        Args:
            relative_path: Path relative to workspace root

        Returns:
            True if path should be ignored
        """
        path_parts = Path(relative_path).parts

        for pattern in self.quroignore_patterns:
            # Exact match
            if relative_path == pattern:
                return True

            # Directory match (any part of path)
            if pattern in path_parts:
                return True

            # Wildcard match (simple glob)
            if "*" in pattern:
                if self._matches_glob(relative_path, pattern):
                    return True

        return False

    def _matches_glob(self, path: str, pattern: str) -> bool:
        """Simple glob matching.

        Args:
            path: Path to check
            pattern: Glob pattern (e.g., '*.pyc', 'test_*.py')

        Returns:
            True if path matches pattern
        """
        filename = Path(path).name

        # Handle *.ext patterns (suffix match)
        if pattern.startswith("*") and "*" not in pattern[1:]:
            suffix = pattern[1:]
            return filename.endswith(suffix)

        # Handle prefix_* patterns (prefix match)
        if pattern.endswith("*") and "*" not in pattern[:-1]:
            prefix = pattern[:-1]
            return filename.startswith(prefix)

        # Handle prefix_*_suffix patterns (e.g., test_*.py)
        if "*" in pattern:
            parts = pattern.split("*")
            if len(parts) == 2:
                prefix, suffix = parts
                return filename.startswith(prefix) and filename.endswith(suffix)

        return False

    def _is_binary(self, file_path: Path) -> bool:
        """Detect if file is binary.

        Checks first N bytes for null bytes.

        Args:
            file_path: File path to check

        Returns:
            True if file appears to be binary
        """
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(self.BINARY_CHECK_BYTES)
                # Check for null bytes (common in binary files)
                return b"\x00" in chunk
        except OSError:
            # If can't read, assume binary
            return True

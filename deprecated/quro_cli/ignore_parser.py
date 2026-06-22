"""
.quroignore parser and matcher

@module quro_cli.ignore_parser
@intent Parse .quroignore file and provide path matching logic

.quroignore format (gitignore-compatible):
- Lines starting with # are comments
- Blank lines are ignored
- Patterns use glob syntax (* and **)
- Leading / matches from workspace root
- Trailing / matches directories only
- ! prefix negates pattern
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Set


class QuroIgnore:
    """
    Parser and matcher for .quroignore files.

    @intent Provide gitignore-compatible ignore logic for scanner
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.patterns: List[tuple[bool, re.Pattern]] = []
        self._load_ignore_file()

    def _load_ignore_file(self) -> None:
        """Load and parse .quroignore file."""
        ignore_file = self.workspace_root / '.quroignore'

        if not ignore_file.exists():
            # Use default patterns
            self._add_default_patterns()
            return

        with open(ignore_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                # Skip comments and blank lines
                if not line or line.startswith('#'):
                    continue

                # Check for negation
                negate = False
                if line.startswith('!'):
                    negate = True
                    line = line[1:]

                # Convert glob to regex
                pattern = self._glob_to_regex(line)
                self.patterns.append((negate, pattern))

    def _add_default_patterns(self) -> None:
        """Add default ignore patterns when .quroignore doesn't exist."""
        default_patterns = [
            '.claude/worktrees/**',
            'node_server/**',
            '.git/**',
            '__pycache__/**',
            '*.pyc',
            '.venv/**',
            'venv/**',
            'node_modules/**',
            'dist/**',
            'build/**',
        ]

        for pattern in default_patterns:
            regex = self._glob_to_regex(pattern)
            self.patterns.append((False, regex))

    def _glob_to_regex(self, pattern: str) -> re.Pattern:
        r"""
        Convert glob pattern to regex.

        @intent Support gitignore-style patterns

        Examples:
            *.py -> .*\.py$
            **/*.py -> .*/.*\.py$
            /foo -> ^foo
            foo/ -> foo/.*
        """
        # Escape special regex characters except * and /
        pattern = re.escape(pattern)
        pattern = pattern.replace(r'\*\*', '§DOUBLESTAR§')
        pattern = pattern.replace(r'\*', '[^/]*')
        pattern = pattern.replace('§DOUBLESTAR§', '.*')

        # Handle leading /
        if pattern.startswith(r'\/'):
            pattern = '^' + pattern[2:]
        else:
            # Match anywhere in path
            pattern = '(^|/)' + pattern

        # Handle trailing /
        if pattern.endswith(r'\/'):
            pattern = pattern + '.*'

        # Anchor at end
        if not pattern.endswith('.*'):
            pattern = pattern + '$'

        return re.compile(pattern)

    def is_ignored(self, file_path: str | Path) -> bool:
        """
        Check if file path should be ignored.

        @intent Apply ignore patterns with negation support

        Args:
            file_path: Relative path from workspace root

        Returns:
            True if file should be ignored
        """
        if isinstance(file_path, Path):
            file_path = str(file_path)

        # Normalize path separators
        file_path = file_path.replace('\\', '/')

        ignored = False

        for negate, pattern in self.patterns:
            if pattern.search(file_path):
                if negate:
                    ignored = False
                else:
                    ignored = True

        return ignored

    def filter_paths(self, paths: List[Path]) -> List[Path]:
        """
        Filter list of paths, removing ignored ones.

        @intent Batch filtering for scanner

        Args:
            paths: List of absolute paths

        Returns:
            Filtered list of paths
        """
        filtered = []

        for path in paths:
            try:
                relative = path.relative_to(self.workspace_root)
                if not self.is_ignored(relative):
                    filtered.append(path)
            except ValueError:
                # Path not relative to workspace, skip
                continue

        return filtered

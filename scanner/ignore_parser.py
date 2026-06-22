"""
.quroignore parser and matcher

@module scanner.ignore_parser
@intent Parse .quroignore file and provide path matching logic

.quroignore format (gitignore-compatible):
- Lines starting with # are comments
- Blank lines are ignored
- Patterns use glob syntax (* and **)
- Leading / matches from workspace root
- Trailing / matches directories only
- ! prefix negates pattern
"""

import re
from pathlib import Path
from typing import List


class QuroIgnore:
    """
    Parser and matcher for .quroignore files.
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.patterns: List[tuple[bool, re.Pattern]] = []
        self._load_ignore_file()

    def _load_ignore_file(self) -> None:
        """Load and parse .quroignore file."""
        ignore_file = self.workspace_root / '.quroignore'

        if not ignore_file.exists():
            self._add_default_patterns()
            return

        with open(ignore_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith('#'):
                    continue

                negate = False
                if line.startswith('!'):
                    negate = True
                    line = line[1:]

                pattern = self._glob_to_regex(line)
                self.patterns.append((negate, pattern))

    def _add_default_patterns(self) -> None:
        """Add default ignore patterns when .quroignore doesn't exist."""
        default_patterns = [
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
        """Convert glob pattern to regex."""
        pattern = re.escape(pattern)
        pattern = pattern.replace(r'\*\*', '§DOUBLESTAR§')
        pattern = pattern.replace(r'\*', '[^/]*')
        pattern = pattern.replace('§DOUBLESTAR§', '.*')

        if pattern.startswith(r'\/'):
            pattern = '^' + pattern[2:]
        else:
            pattern = '(^|/)' + pattern

        if pattern.endswith(r'\/'):
            pattern = pattern + '.*'

        if not pattern.endswith('.*'):
            pattern = pattern + '$'

        return re.compile(pattern)

    def is_ignored(self, file_path: str | Path) -> bool:
        """Check if file path should be ignored."""
        if isinstance(file_path, Path):
            file_path = str(file_path)

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
        """Filter list of paths, removing ignored ones."""
        filtered = []

        for path in paths:
            try:
                relative = path.relative_to(self.workspace_root)
                if not self.is_ignored(relative):
                    filtered.append(path)
            except ValueError:
                continue

        return filtered
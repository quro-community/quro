"""
Test suite for .quroignore parser

@module quro_cli.tests.test_ignore_parser
@intent Verify .quroignore parsing and matching logic
"""

import tempfile
from pathlib import Path

import pytest

from quro_cli.ignore_parser import QuroIgnore


@pytest.fixture
def temp_workspace():
    """Create temporary workspace with .quroignore"""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create .quroignore
        ignore_file = workspace / '.quroignore'
        ignore_file.write_text("""
# Comments
*.pyc
__pycache__/**
.venv/**

# Worktrees
.claude/worktrees/**

# Negation
!important.pyc
""")

        yield workspace


def test_ignore_parser_loads_file(temp_workspace):
    """Test that parser loads .quroignore correctly"""
    parser = QuroIgnore(temp_workspace)
    assert len(parser.patterns) > 0


def test_ignore_parser_matches_patterns(temp_workspace):
    """Test pattern matching"""
    parser = QuroIgnore(temp_workspace)

    # Should ignore
    assert parser.is_ignored('test.pyc')
    assert parser.is_ignored('__pycache__/foo.py')
    assert parser.is_ignored('.venv/lib/python3.11/site-packages/foo.py')
    assert parser.is_ignored('.claude/worktrees/fix-123/test.py')

    # Should not ignore
    assert not parser.is_ignored('test.py')
    assert not parser.is_ignored('src/main.py')


def test_ignore_parser_negation(temp_workspace):
    """Test negation patterns"""
    parser = QuroIgnore(temp_workspace)

    # Normal .pyc files are ignored
    assert parser.is_ignored('test.pyc')

    # But important.pyc is negated
    assert not parser.is_ignored('important.pyc')


def test_ignore_parser_filter_paths(temp_workspace):
    """Test batch filtering"""
    parser = QuroIgnore(temp_workspace)

    paths = [
        temp_workspace / 'test.py',
        temp_workspace / 'test.pyc',
        temp_workspace / '__pycache__' / 'foo.py',
        temp_workspace / 'src' / 'main.py',
    ]

    filtered = parser.filter_paths(paths)

    # Should keep .py files, remove .pyc and __pycache__
    assert len(filtered) == 2
    assert temp_workspace / 'test.py' in filtered
    assert temp_workspace / 'src' / 'main.py' in filtered


def test_ignore_parser_default_patterns():
    """Test default patterns when .quroignore doesn't exist"""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        parser = QuroIgnore(workspace)

        # Default patterns should be loaded
        assert parser.is_ignored('.claude/worktrees/fix-123/test.py')
        assert parser.is_ignored('node_server/cli/llm.ts')
        assert parser.is_ignored('__pycache__/foo.py')
        assert parser.is_ignored('.venv/lib/foo.py')

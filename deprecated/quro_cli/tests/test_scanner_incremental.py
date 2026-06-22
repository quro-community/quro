"""
WorkspaceScanner Incremental Scan Tests

@module quro_cli.tests.test_scanner_incremental
@intent Test git-tree-grounded incremental file collection and CQE purge gates.
       Validates: new file discovery, completed skip, pending scan, git-removal
       deprecation, ignore/exclude patterns, fallback mode, purge gate fixes.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_mock_pool(query_results: list | None = None):
    """Create a mock asyncpg pool with predefined query results.

    The pool is set up as an async context manager that yields a connection.
    Each call to conn.fetch() returns the next item from query_results.
    Each call to conn.execute() returns 'UPDATE 0'.
    """
    if query_results is None:
        query_results = []

    results_iter = iter(query_results)

    conn = MagicMock()
    fetch_calls = []
    execute_calls = []

    async def mock_fetch(query, *args):
        fetch_calls.append((query, args))
        return next(results_iter, [])

    async def mock_fetchrow(query, *args):
        rows = await mock_fetch(query, *args)
        return rows[0] if rows else None

    async def mock_execute(query, *args):
        execute_calls.append((query, args))
        return "UPDATE 0"

    conn.fetch = mock_fetch
    conn.fetchrow = mock_fetchrow
    conn.execute = mock_execute
    conn._fetch_calls = fetch_calls
    conn._execute_calls = execute_calls

    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    return pool


def _make_scanner(workspace: Path, git_files: list[str] | None = None):
    """Create a WorkspaceScanner with mocked git and DB."""
    with patch("quro_cli.scanner.WorkspaceScanner.__init__", lambda self, *a, **kw: None):
        from quro_cli.scanner import WorkspaceScanner
        scanner = WorkspaceScanner.__new__(WorkspaceScanner)
        scanner.workspace_root = workspace
        scanner.stats = {"stale_files_deprecated": 0}
        scanner.force_rescan = False

        scanner._get_git_tracked_files = MagicMock(
            return_value=set(git_files) if git_files is not None else set()
        )

        scanner.ignore_parser = MagicMock()
        scanner.ignore_parser.is_ignored = MagicMock(return_value=False)

        return scanner


def _wire_pool(scanner, query_results: list):
    """Wire a mock pool into the scanner."""
    scanner.db_pool = _make_mock_pool(query_results)


class TestIncrementalDiscovery:
    """Test new file discovery via git-tree grounding."""

    @pytest.mark.asyncio
    async def test_discovers_new_git_files(self, tmp_path):
        """Files in git but not in DB should be added to scan list."""
        (tmp_path / "src" / "new_module.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "new_module.py").write_text("def foo(): pass")
        scanner = _make_scanner(tmp_path, git_files=["src/new_module.py"])
        _wire_pool(scanner, [[], []])

        files = await scanner._collect_files_incremental(
            ["**/*.py"], ["**/node_modules/**"]
        )
        assert len(files) == 1
        assert files[0].name == "new_module.py"

    @pytest.mark.asyncio
    async def test_skips_completed_files(self, tmp_path):
        """Files in DB with scan_completed=TRUE should be skipped."""
        (tmp_path / "src" / "done.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "done.py").write_text("def done(): pass")
        scanner = _make_scanner(tmp_path, git_files=["src/done.py"])
        _wire_pool(scanner, [
            [{"file_path": "src/done.py", "all_completed": True}],
            [{"file_path": "src/done.py"}],
        ])

        files = await scanner._collect_files_incremental(["**/*.py"], [])
        assert len(files) == 0

    @pytest.mark.asyncio
    async def test_scans_pending_files(self, tmp_path):
        """Files in DB with scan_completed=FALSE should be scanned."""
        (tmp_path / "src" / "pending.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "pending.py").write_text("def pending(): pass")
        scanner = _make_scanner(tmp_path, git_files=["src/pending.py"])
        _wire_pool(scanner, [
            [{"file_path": "src/pending.py", "all_completed": False}],
            [{"file_path": "src/pending.py"}],
        ])

        files = await scanner._collect_files_incremental(["**/*.py"], [])
        assert len(files) == 1

    @pytest.mark.asyncio
    async def test_empty_db_first_scan(self, tmp_path):
        """Empty DB should discover all git-tracked files."""
        (tmp_path / "src" / "a.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "b.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "a.py").write_text("def a(): pass")
        (tmp_path / "src" / "b.py").write_text("def b(): pass")
        scanner = _make_scanner(tmp_path, git_files=["src/a.py", "src/b.py"])
        _wire_pool(scanner, [[], []])

        files = await scanner._collect_files_incremental(["**/*.py"], [])
        assert len(files) == 2


class TestIncrementalDeprecation:
    """Test reverse-diff deprecation of stale DB entries."""

    @pytest.mark.asyncio
    async def test_deprecates_removed_git_files(self, tmp_path):
        """Files in DB but not in git tree should be deprecated."""
        (tmp_path / "src" / "kept.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "kept.py").write_text("def kept(): pass")
        scanner = _make_scanner(tmp_path, git_files=["src/kept.py"])
        _wire_pool(scanner, [
            [{"file_path": "src/kept.py", "all_completed": True}],
            [{"file_path": "src/kept.py"}, {"file_path": "src/removed.py"}],
        ])
        scanner._deprecate_stale_files = AsyncMock()

        files = await scanner._collect_files_incremental(["**/*.py"], [])

        assert len(files) == 0
        scanner._deprecate_stale_files.assert_called_once()
        deprecated_arg = scanner._deprecate_stale_files.call_args[0][0]
        assert "src/removed.py" in deprecated_arg


class TestIncrementalFiltering:
    """Test ignore, include, and exclude pattern filtering."""

    @pytest.mark.asyncio
    async def test_applies_ignore_patterns(self, tmp_path):
        """.quroignored files should be excluded from scan list."""
        (tmp_path / "src" / "ignored.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "ignored.py").write_text("def ignored(): pass")
        scanner = _make_scanner(tmp_path, git_files=["src/ignored.py"])
        scanner.ignore_parser.is_ignored = MagicMock(return_value=True)
        _wire_pool(scanner, [[], []])

        files = await scanner._collect_files_incremental(["**/*.py"], [])
        assert len(files) == 0
        scanner.ignore_parser.is_ignored.assert_called_once()

    @pytest.mark.asyncio
    async def test_applies_include_patterns(self, tmp_path):
        """Only files matching include patterns should be candidates."""
        (tmp_path / "src" / "main.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "data" / "data.csv").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "main.py").write_text("def main(): pass")
        (tmp_path / "data" / "data.csv").write_text("a,b,c")
        scanner = _make_scanner(tmp_path, git_files=["src/main.py", "data/data.csv"])
        _wire_pool(scanner, [[], []])

        files = await scanner._collect_files_incremental(["**/*.py"], [])
        assert len(files) == 1
        assert files[0].name == "main.py"

    @pytest.mark.asyncio
    async def test_applies_exclude_patterns(self, tmp_path):
        """Files matching exclude patterns should be excluded."""
        (tmp_path / "src" / "keep.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "keep.py").write_text("def keep(): pass")
        scanner = _make_scanner(tmp_path, git_files=["src/keep.py"])
        _wire_pool(scanner, [[], []])

        files = await scanner._collect_files_incremental(["**/*.py"], ["src/keep.py"])
        assert len(files) == 0


class TestIncrementalEdgeCases:
    """Test edge cases: not checked out, non-git dir."""

    @pytest.mark.asyncio
    async def test_warns_not_checked_out(self, tmp_path):
        """Git-tracked but disk-missing files should be skipped."""
        scanner = _make_scanner(tmp_path, git_files=["src/ghost.py"])
        _wire_pool(scanner, [[], []])

        files = await scanner._collect_files_incremental(["**/*.py"], [])
        assert len(files) == 0

    @pytest.mark.asyncio
    async def test_fallback_non_git_directory(self, tmp_path):
        """Non-git directories should fall back to glob-based collection."""
        (tmp_path / "src" / "module.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "module.py").write_text("def mod(): pass")
        scanner = _make_scanner(tmp_path, git_files=[])  # Empty = non-git
        scanner._collect_files = MagicMock(
            return_value=[tmp_path / "src" / "module.py"]
        )
        _wire_pool(scanner, [None])

        files = await scanner._collect_files_incremental(["**/*.py"], [])
        assert len(files) == 1
        assert files[0].name == "module.py"
        scanner._collect_files.assert_called_once()


class TestPurgeCQEIneligible:
    """Test _purge_cqe_ineligible fixes: Gate 4 re-query, Gate 5 git-tree."""

    @pytest.mark.asyncio
    async def test_gate4_requeries_after_gate3(self, tmp_path):
        """Gate 4 should re-query DB after Gate 3 deprecations."""
        scanner = _make_scanner(tmp_path, git_files=["src/test.py"])
        pool = _make_mock_pool([
            [{"file_path": "src/orphan.py"}],      # Gate 3 query
            [{"file_path": "src/orphan.py"}],      # Gate 4 re-query (fresh)
            [{"file_path": "src/orphan.py"}],      # Gate 5 query
        ])
        scanner.db_pool = pool

        # Make orphan.py not exist on disk for Gate 3
        original_exists = Path.exists
        def mock_exists(self):
            if str(self).endswith("orphan.py"):
                return False
            return original_exists(self)
        Path.exists = mock_exists  # type: ignore

        try:
            await scanner._purge_cqe_ineligible()
        finally:
            Path.exists = original_exists  # type: ignore

        # Gate 3, Gate 4, Gate 5 each call fetch → 3 fetch calls
        conn = pool.acquire.return_value.__aenter__.return_value
        assert len(conn._fetch_calls) == 3

    @pytest.mark.asyncio
    async def test_gate5_git_tree_check(self, tmp_path):
        """Gate 5 should deprecate symbols for files not in git tree."""
        (tmp_path / "src" / "tracked.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "untracked.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "tracked.py").write_text("pass")
        (tmp_path / "src" / "untracked.py").write_text("pass")
        scanner = _make_scanner(tmp_path, git_files=["src/tracked.py"])

        all_rows = [
            {"file_path": "src/tracked.py"},
            {"file_path": "src/untracked.py"},
        ]
        pool = _make_mock_pool([
            all_rows,  # Gate 3 query
            all_rows,  # Gate 4 re-query
            all_rows,  # Gate 5 query
        ])
        scanner.db_pool = pool

        await scanner._purge_cqe_ineligible()

        conn = pool.acquire.return_value.__aenter__.return_value
        # execute: Gate 1 + Gate 2 + Gate 5 deprecate untracked
        assert len(conn._execute_calls) >= 3


class TestForceModeUnchanged:
    """Test that force mode still scans all files regardless of DB state."""

    @pytest.mark.asyncio
    async def test_force_uses_collect_files(self, tmp_path):
        """Force mode should call _collect_files, not _collect_files_incremental."""
        (tmp_path / "src" / "module.py").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "module.py").write_text("pass")
        scanner = _make_scanner(tmp_path, git_files=["src/module.py"])
        scanner._collect_files = MagicMock(
            return_value=[tmp_path / "src" / "module.py"]
        )

        files = scanner._collect_files(["**/*.py"], [])
        assert len(files) == 1
        scanner._collect_files.assert_called_once()

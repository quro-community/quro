"""
Workspace Scanner - Python implementation with V2 dual-write support

@module quro_cli.scanner
@intent Scan workspace files, extract symbols, perform semantic analysis, write to V2 schema
"""

import asyncio
import asyncpg
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Optional, Set, Any, Callable
from dataclasses import dataclass
from datetime import datetime

from quro_cli.config import QURO_DB_URL
from quro_cli.registry.registry_v2 import RegistryV2
from quro_cli.analysis.typescript_probe import TypeScriptProbe
from quro_cli.analysis.python_ast_analyzer import PythonASTAnalyzer
from quro_cli.analysis.lsh_engine import MinHashLSH
from quro_cli.analysis.call_graph_extractor import CallGraphExtractor
from quro_cli.analysis.semantic_analyzer import SemanticAnalyzer
from quro_cli.analysis.structural_tag_extractor import (
    StructuralTags,
    extract_tags,
    merge_with_llm_tags,
)
from quro_cli.ignore_parser import QuroIgnore
from quro_cli.scanner_utils import (
    compute_fingerprint,
    check_contract,
    ContractStatus,
    ContractType,
    normalize_imports,
)
from quro_cli.scanner_deep.class_signature import (
    extract_class_signature,
    ClassSignature,
)
from quro_cli.scanner_deep.deep_index import DeepIndex

logger = logging.getLogger(__name__)

# Map LLM-generated tag variants to canonical CQE _CATEGORY_INVARIANTS keys.
# Applied after semantic analysis to ensure tags bridge to CQE categories.
_TAG_CANONICAL_MAP: Dict[str, str] = {
    "network_io": "network",
    "file_io": "filesystem",
    "database_io": "database",
    "resource_management": "memory",
    "resource_manager": "memory",
    "data_structure": "container",
    "state_management": "atomic",
    "context_manager": "raii",
    "command_line": "entry_point",
}

# High-frequency symbol names that match thousands of DB rows.
# Processing these causes massive CALLS edge lookups and memory blowups.
# They are never useful as semantic symbols — skip entirely.
_SKIP_SYMBOL_NAMES = frozenset(
    {
        # Generic data/flow variable names
        "task_id",
        "path",
        "symbol",
        "error",
        "ok",
        "status",
        "result",
        "data",
        "value",
        "key",
        "name",
        "type",
        "content",
        "text",
        "item",
        "items",
        "entry",
        "record",
        "row",
        "field",
        "col",
        "msg",
        "message",
        "args",
        "kwargs",
        "self",
        "cls",
        "config",
        "options",
        "params",
        "headers",
        "payload",
        "request",
        "response",
        "output",
        "input",
        "buffer",
        "offset",
        "length",
        "index",
        "count",
        "total",
        "size",
        "kind",
        "node",
        "parent",
        "child",
        "children",
        "source",
        "target",
        "source_code",
        # Common Python dunder/magic
        "__init__",
        "__repr__",
        "__str__",
        "__eq__",
        "__hash__",
        "__len__",
        # Internal sentinels (never real symbols)
        "__file_sentinel__",
    }
)

# Memory budget: refuse to tokenize files that would produce excessive token sets.
_MAX_TOKEN_COUNT = 50_000

# LSH matrix dimension safety cap (100 MB in float64)
_MAX_LSH_MATRIX_ELEMENTS = 100_000_000


def canonicalize_tags(tags: List[str]) -> List[str]:
    """Expand tags with canonical CQE category keys and filter garbage.

    For each tag that has a canonical mapping, appends the canonical key
    if not already present. Filters out garbage tags (single-char,
    whitespace-only, non-printable) before they reach the database.

    Returns a new list (immutable pattern).
    """
    # Defense: if tags is not a list (e.g., a JSON string), reset to empty.
    # This prevents double-encoding corruption from reaching the DB.
    if not isinstance(tags, list):
        logger.warning(
            "canonicalize_tags: received %s instead of list, resetting",
            type(tags).__name__,
        )
        tags = []

    # Filter garbage tags first
    cleaned = [
        t
        for t in tags
        if isinstance(t, str) and len(t) >= 2 and t.isprintable() and not t.isspace()
    ]
    if len(cleaned) != len(tags):
        rejected = [t for t in tags if t not in cleaned]
        logger.debug(
            "canonicalize_tags: filtered %d garbage tags: %s",
            len(rejected),
            rejected[:5],
        )

    expanded = list(cleaned)
    seen = set(cleaned)
    for tag in cleaned:
        canonical = _TAG_CANONICAL_MAP.get(tag)
        if canonical and canonical not in seen:
            expanded.append(canonical)
            seen.add(canonical)
    return expanded


@dataclass
class SymbolInfo:
    """Symbol information extracted from source code"""

    name: str
    type: str  # function, async_function, class, method, variable
    file_path: str
    line: int
    char: int
    signature: Optional[str] = None
    calls: List[str] = None  # Symbol names called by this symbol
    imports: List[str] = None  # Import paths
    decorators: List[str] = None  # AST decorator names
    docstring: Optional[str] = None  # AST docstring
    ast_kind: Optional[str] = None  # Raw AST kind (e.g. 'async_function')

    def __post_init__(self):
        if self.calls is None:
            self.calls = []
        if self.imports is None:
            self.imports = []
        if self.decorators is None:
            self.decorators = []


class WorkspaceScanner:
    """
    Scan workspace and index symbols with V2 schema support.

    Replaces node_server/cli/scanner.ts with Python-native implementation.
    """

    def __init__(
        self,
        workspace_root: Path,
        db_pool: asyncpg.Pool,
        enable_v2_write: bool = True,
        enable_semantic_analysis: bool = True,
        on_progress: Callable[[str, str], None] | None = None,
    ):
        self.workspace_root = workspace_root
        self.db_pool = db_pool
        self.registry_v2 = RegistryV2(db_pool, enable_v2_write)
        self.ts_probe: Optional[TypeScriptProbe] = None
        self.py_analyzer = PythonASTAnalyzer()
        self.lsh_engine = MinHashLSH()

        # Semantic analyzer (OpenAI-based)
        self.enable_semantic_analysis = enable_semantic_analysis
        self.semantic_analyzer: Optional[SemanticAnalyzer] = None

        # .quroignore parser
        self.ignore_parser = QuroIgnore(workspace_root)

        # Deep Index — built during scan, rebuilt atomically at the end
        self._deep_index = DeepIndex()
        self._pending_signatures: List[ClassSignature] = []
        self._source_hashes: Dict[str, str] = {}

        # Failed-symbol blacklist: symbols that failed AI quality gate >= N times
        self._ai_failure_counts: Dict[str, int] = {}
        self._blacklisted_symbols: Set[str] = set()

        # Progress callback: on_progress(event, message)
        # event: "file:start", "symbol:done", "symbol:skip", "symbol:low_quality"
        self._on_progress = on_progress

        # Statistics
        self.stats = {
            "files_scanned": 0,
            "symbols_found": 0,
            "symbols_analyzed": 0,
            "symbols_skipped": 0,
            "morphisms_created": 0,
            "stale_files_deprecated": 0,
            "errors": 0,
        }

    @property
    def deep_index(self) -> DeepIndex:
        """Access the Deep Index (read-only, after scan completes)."""
        return self._deep_index

    async def setup(self):
        """Initialize scanner components"""
        await self.registry_v2.setup()

        # Start TypeScript probe for TS/JS analysis
        self.ts_probe = TypeScriptProbe()
        try:
            await self.ts_probe.start()
            logger.info("TypeScript probe started successfully")
        except Exception as e:
            logger.warning(
                f"TypeScript probe failed to start: {e}. Will use fallback parser."
            )
            self.ts_probe = None

        # Initialize semantic analyzer if enabled
        if self.enable_semantic_analysis:
            try:
                self.semantic_analyzer = SemanticAnalyzer()
                logger.info(
                    f"Semantic analyzer initialized with model: {self.semantic_analyzer.model}"
                )
            except Exception as e:
                logger.warning(
                    f"Semantic analyzer failed to initialize: {e}. Will use heuristic analysis."
                )
                self.semantic_analyzer = None

    async def cleanup(self):
        """Cleanup resources"""
        if self.ts_probe:
            await self.ts_probe.stop()

    async def scan(
        self,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        force: bool = False,
        use_ai: bool = False,
        file_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Scan workspace and index symbols.

        Args:
            include_patterns: File patterns to include (e.g., ['**/*.py', '**/*.ts'])
            exclude_patterns: Patterns to exclude (e.g., ['**/node_modules/**', '**/.venv/**'])
            force: Force rescan even if files haven't changed (ignores scan_completed flag)
            use_ai: Enable AI-driven semantic analysis (Phase 2)
            file_paths: Optional list of specific files to scan (partial scan)

        Returns:
            Dict with status, files_scanned, files_changed, symbols_found, duration_ms, changed_files
        """
        start_time = time.time()

        logger.info(f"Starting workspace scan: {self.workspace_root}")
        logger.info(f"Force rescan: {force}")
        logger.info(f"Use AI: {use_ai}")

        # Store force flag for use in _semantic_analysis
        self.force_rescan = force

        # Purge symbols that no longer qualify for CQE indexing
        # (not in git tree, matches .quroignore, file deleted, etc.)
        purged = await self._purge_cqe_ineligible()
        if purged:
            logger.info("Pre-scan purge: %d ineligible symbols deprecated", purged)

        # Load blacklist from report file
        self._load_blacklist()

        # Default patterns
        if include_patterns is None:
            include_patterns = ["**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"]

        if exclude_patterns is None:
            exclude_patterns = [
                "**/node_modules/**",
                "**/.venv/**",
                "**/venv/**",
                "**/__pycache__/**",
                "**/dist/**",
                "**/build/**",
                "**/.git/**",
                "**/quro_bundle/**",
                "**/.quro_context/**",
            ]

        # Collect files
        if file_paths:
            # Partial scan: specific files
            files_to_scan = []
            for fp in file_paths:
                p = Path(fp)
                if not p.is_absolute():
                    p = self.workspace_root / p
                if p.exists():
                    files_to_scan.append(p)
            logger.info(f"Partial scan: {len(files_to_scan)} files")
        elif force:
            # Force mode: scan all matching files
            files_to_scan = self._collect_files(include_patterns, exclude_patterns)
            logger.info(f"Found {len(files_to_scan)} files to scan (force mode)")
        else:
            # Incremental mode: git-tree-grounded diff against DB
            files_to_scan = await self._collect_files_incremental(
                include_patterns, exclude_patterns
            )
            logger.info(
                f"Found {len(files_to_scan)} files with pending symbols (incremental mode)"
            )

        # Scan files in batches
        batch_size = 10
        for i in range(0, len(files_to_scan), batch_size):
            batch = files_to_scan[i : i + batch_size]
            await asyncio.gather(
                *[self._scan_file(f, use_ai=use_ai) for f in batch],
                return_exceptions=True,
            )

        # Rebuild Deep Index with collected ClassSignatures
        if self._pending_signatures:
            class_count = self._deep_index.rebuild(
                self._pending_signatures,
                source_hashes=self._source_hashes,
            )
            logger.info("Deep Index rebuilt: %d classes indexed", class_count)
        else:
            logger.info("Deep Index: no ClassSignatures collected — skipping rebuild")

        # Show final statistics
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Scan complete: {self.stats} ({duration_ms}ms)")

        if self.semantic_analyzer:
            analyzer_stats = self.semantic_analyzer.get_stats()
            logger.info(f"Semantic analysis stats:")
            logger.info(f"  Total requests: {analyzer_stats['total_requests']}")
            logger.info(f"  Failed requests: {analyzer_stats['failed_requests']}")
            logger.info(f"  Total tokens: {analyzer_stats['total_tokens']}")
            logger.info(
                f"  Estimated cost: ${analyzer_stats['estimated_cost_usd']:.4f}"
            )

        return {
            "status": "success",
            "files_scanned": self.stats["files_scanned"],
            "files_changed": self.stats[
                "files_scanned"
            ],  # all scanned files are "changed" in this context
            "symbols_found": self.stats["symbols_found"],
            "duration_ms": duration_ms,
            "changed_files": [],
            "symbols_skipped": self.stats["symbols_skipped"],
            "errors": self.stats["errors"],
        }

    async def _purge_cqe_ineligible(self) -> int:
        """Deprecate symbols that would fail CQE admission gates.

        CQE admission criteria (from cqe_index_pipeline._reject_file_path):
        1. File path must not be empty
        2. File must exist on disk
        3. File must not match .quroignore
        4. File path must contain '/' (no flat paths)
        5. File must be in git tree (deterministic source of truth)

        Returns:
            Number of symbols deprecated.

        This method proactively cleans PG so CQE never sees invalid data.
        """
        purged = 0
        async with self.db_pool.acquire() as conn:
            # Gate 1: Empty file path
            result = await conn.execute("""
                UPDATE symbols SET deprecated_at = NOW()
                WHERE deprecated_at IS NULL
                AND file_id IN (
                    SELECT id FROM files
                    WHERE file_path = '' OR file_path IS NULL
                )
            """)
            n = int(result.split()[-1]) if result else 0
            purged += n
            if n:
                logger.info(f"CQE gate: deprecated {n} symbols with empty file_path")

            # Gate 2: Flat path (no directory separator)
            result = await conn.execute("""
                UPDATE symbols SET deprecated_at = NOW()
                WHERE deprecated_at IS NULL
                AND file_id IN (
                    SELECT id FROM files
                    WHERE file_path IS NOT NULL
                    AND file_path != ''
                    AND position('/' IN file_path) = 0
                )
            """)
            n = int(result.split()[-1]) if result else 0
            purged += n
            if n:
                logger.info(f"CQE gate: deprecated {n} symbols with flat file_path")

            # Gate 3: File not found on disk
            rows = await conn.fetch("""
                SELECT DISTINCT f.file_path
                FROM files f
                JOIN symbols s ON s.file_id = f.id
                WHERE s.deprecated_at IS NULL
                AND f.file_path IS NOT NULL
                AND f.file_path != ''
            """)
            for row in rows:
                abs_path = self.workspace_root / row["file_path"]
                if not abs_path.exists():
                    r = await conn.execute(
                        """
                        UPDATE symbols SET deprecated_at = NOW()
                        WHERE file_id = (SELECT id FROM files WHERE file_path = $1)
                        AND deprecated_at IS NULL
                    """,
                        row["file_path"],
                    )
                    n = int(r.split()[-1]) if r else 0
                    purged += n

            # Gate 4: .quroignore match (re-query after Gate 3 deprecations)
            if self.ignore_parser:
                rows = await conn.fetch("""
                    SELECT DISTINCT f.file_path
                    FROM files f
                    JOIN symbols s ON s.file_id = f.id
                    WHERE s.deprecated_at IS NULL
                    AND f.file_path IS NOT NULL
                    AND f.file_path != ''
                """)
                for row in rows:
                    if self.ignore_parser.is_ignored(row["file_path"]):
                        r = await conn.execute(
                            """
                            UPDATE symbols SET deprecated_at = NOW()
                            WHERE file_id = (SELECT id FROM files WHERE file_path = $1)
                            AND deprecated_at IS NULL
                        """,
                            row["file_path"],
                        )
                        n = int(r.split()[-1]) if r else 0
                        purged += n

            # Gate 5: Not in git tree (deterministic source of truth)
            tracked_files = self._get_git_tracked_files()
            if tracked_files:
                rows = await conn.fetch("""
                    SELECT DISTINCT f.file_path
                    FROM files f
                    JOIN symbols s ON s.file_id = f.id
                    WHERE s.deprecated_at IS NULL
                    AND f.file_path IS NOT NULL
                    AND f.file_path != ''
                """)
                for row in rows:
                    if row["file_path"] not in tracked_files:
                        r = await conn.execute(
                            """
                            UPDATE symbols SET deprecated_at = NOW()
                            WHERE file_id = (SELECT id FROM files WHERE file_path = $1)
                            AND deprecated_at IS NULL
                        """,
                            row["file_path"],
                        )
                        n = int(r.split()[-1]) if r else 0
                        purged += n
                logger.info("CQE gate: git-tree validation complete")

        if purged:
            logger.info(f"CQE gate: total {purged} symbols deprecated")
        else:
            logger.info("CQE gate: no ineligible symbols found")

        # Cascade cleanup: delete morphism_edges that reference deprecated symbols.
        # Without this, edges accumulate as orphaned rows (97%+ orphan rate observed),
        # wasting space and causing the CQE pipeline to fail edge matching.
        if purged > 0:
            async with self.db_pool.acquire() as conn:
                deleted = await conn.execute("""
                    DELETE FROM morphism_edges
                    WHERE from_symbol_id IN (SELECT id FROM symbols WHERE deprecated_at IS NOT NULL)
                       OR to_symbol_id IN (SELECT id FROM symbols WHERE deprecated_at IS NOT NULL)
                """)
                n = int(deleted.split()[-1]) if deleted else 0
                if n:
                    logger.info("CQE gate: cleaned %d orphaned morphism_edges", n)

        return purged

    def _collect_files(
        self, include_patterns: List[str], exclude_patterns: List[str]
    ) -> List[Path]:
        """Collect files matching patterns (git-tracked + .quroignore)"""
        # Get git-tracked files (same constraint as node_server scanner)
        tracked_files = self._get_git_tracked_files()

        files = set()

        for pattern in include_patterns:
            for file_path in self.workspace_root.glob(pattern):
                if file_path.is_file():
                    # Check exclusions
                    relative = file_path.relative_to(self.workspace_root)
                    relative_str = str(relative)

                    # .quroignore check (primary defense — always enforced)
                    if self.ignore_parser.is_ignored(relative):
                        continue

                    # Git worktree constraint: only scan tracked files
                    if tracked_files and relative_str not in tracked_files:
                        continue

                    excluded = False
                    for exclude in exclude_patterns:
                        if relative.match(exclude):
                            excluded = True
                            break

                    if not excluded:
                        files.add(file_path)

        return sorted(files)

    async def _collect_files_incremental(
        self, include_patterns: List[str], exclude_patterns: List[str]
    ) -> List[Path]:
        """Git-tree-grounded incremental file collection.

        Algorithm:
        1. Get canonical file list from git ls-files (source of truth)
        2. Apply include/exclude/ignore filters
        3. Diff against DB: classify each file as new/pending/skip
        4. Reverse diff: DB files not in git tree -> deprecate

        Returns:
            List of Path objects to scan.
        """
        # Step 1: Get git-tracked files
        tracked_files = self._get_git_tracked_files()
        if not tracked_files:
            logger.warning(
                "Not a git repository or git ls-files failed. "
                "Falling back to glob-based collection."
            )
            return await self._collect_files_fallback(
                include_patterns, exclude_patterns
            )

        # Step 2: Filter through include/exclude/ignore patterns
        candidate_files: Set[str] = set()
        for rel_path in tracked_files:
            # .quroignore check
            if self.ignore_parser.is_ignored(rel_path):
                continue

            # Include pattern check
            relative = Path(rel_path)
            matches_include = False
            for pattern in include_patterns:
                if relative.match(pattern):
                    matches_include = True
                    break
            if not matches_include:
                continue

            # Exclude pattern check
            excluded = False
            for exclude in exclude_patterns:
                if relative.match(exclude):
                    excluded = True
                    break
            if excluded:
                continue

            candidate_files.add(rel_path)

        # Step 3: Batch-query DB for scan state of candidate files
        db_file_states: Dict[str, bool] = {}
        async with self.db_pool.acquire() as conn:
            if candidate_files:
                rows = await conn.fetch(
                    """
                    SELECT f.file_path,
                           COALESCE(BOOL_AND(s.scan_completed = TRUE), FALSE) AS all_completed
                    FROM files f
                    JOIN symbols s ON s.file_id = f.id
                    WHERE s.deprecated_at IS NULL
                    AND f.file_path = ANY($1::text[])
                    GROUP BY f.file_path
                """,
                    list(candidate_files),
                )

                db_file_states = {
                    row["file_path"]: row["all_completed"] for row in rows
                }

            # Also get ALL non-deprecated file paths in DB (for reverse diff)
            all_db_rows = await conn.fetch("""
                SELECT DISTINCT f.file_path
                FROM files f
                JOIN symbols s ON s.file_id = f.id
                WHERE s.deprecated_at IS NULL
                AND f.file_path IS NOT NULL
                AND f.file_path != ''
            """)

        all_db_files = {row["file_path"] for row in all_db_rows}

        # Step 4: Classify files
        files_to_scan: Set[Path] = set()
        new_count = 0
        pending_count = 0
        skipped_count = 0

        for rel_path in candidate_files:
            abs_path = self.workspace_root / rel_path

            if not abs_path.exists():
                logger.warning(
                    "Git-tracked file not on disk (not checked out?): %s", rel_path
                )
                continue

            db_state = db_file_states.get(rel_path)

            if db_state is None:
                # NOT in DB -> new file discovery
                files_to_scan.add(abs_path)
                new_count += 1
            elif not db_state:
                # In DB but not all symbols completed -> pending work
                files_to_scan.add(abs_path)
                pending_count += 1
            else:
                # In DB and all symbols completed -> skip
                skipped_count += 1

        # Step 5: Reverse diff -- deprecate DB files not in git tree
        stale_db_files = all_db_files - candidate_files
        if stale_db_files:
            truly_stale = [fp for fp in stale_db_files if "/" in fp]
            if truly_stale:
                await self._deprecate_stale_files(truly_stale)

        logger.info(
            "Incremental: %d new, %d pending, %d skipped, %d deprecated",
            new_count,
            pending_count,
            skipped_count,
            len(stale_db_files),
        )

        return sorted(files_to_scan)

    async def _collect_files_fallback(
        self, include_patterns: List[str], exclude_patterns: List[str]
    ) -> List[Path]:
        """Fallback file collection for non-git directories.

        Uses glob patterns (same as force mode) but filters out files
        that are already scan_completed=TRUE in DB.
        """
        all_files = self._collect_files(include_patterns, exclude_patterns)

        files_to_scan = []
        async with self.db_pool.acquire() as conn:
            for file_path in all_files:
                rel_path = str(file_path.relative_to(self.workspace_root))
                row = await conn.fetchrow(
                    """
                    SELECT COALESCE(BOOL_AND(s.scan_completed = TRUE), FALSE) AS all_completed
                    FROM files f
                    JOIN symbols s ON s.file_id = f.id
                    WHERE s.deprecated_at IS NULL
                    AND f.file_path = $1
                    GROUP BY f.file_path
                """,
                    rel_path,
                )

                if row is None or not row["all_completed"]:
                    files_to_scan.append(file_path)

        return files_to_scan

    async def _deprecate_stale_files(self, stale_files: List[str]) -> None:
        """
        Deprecate symbols for files that no longer exist on disk.

        @intent Automatic cleanup of stale database entries
        """
        async with self.db_pool.acquire() as conn:
            for file_path_str in stale_files:
                try:
                    # Mark all symbols in this file as deprecated
                    result = await conn.execute(
                        """
                        UPDATE symbols
                        SET deprecated_at = NOW()
                        WHERE file_id IN (
                            SELECT id FROM files WHERE file_path = $1
                        )
                        AND deprecated_at IS NULL
                    """,
                        file_path_str,
                    )

                    # Extract row count from result
                    rows_affected = int(result.split()[-1]) if result else 0

                    if rows_affected > 0:
                        logger.info(
                            f"Deprecated {rows_affected} symbols from stale file: {file_path_str}"
                        )
                        self.stats["stale_files_deprecated"] += 1

                except Exception as e:
                    logger.error(f"Failed to deprecate stale file {file_path_str}: {e}")

    def _get_git_tracked_files(self) -> Set[str]:
        """Get set of git-tracked files (git ls-files)"""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                tracked = set(
                    line.strip() for line in result.stdout.split("\n") if line.strip()
                )
                logger.info(f"Found {len(tracked)} git-tracked files")
                return tracked
            else:
                logger.warning(f"git ls-files failed: {result.stderr}")
                return set()

        except Exception as e:
            logger.warning(
                f"Failed to get git tracked files: {e}. Falling back to basic ignore logic."
            )
            return set()

    async def _scan_file(self, file_path: Path, use_ai: bool = False):
        """Scan a single file and extract symbols"""
        contract_status = ContractStatus.INCOMPLETE
        parse_error = None

        try:
            relative_path = str(file_path.relative_to(self.workspace_root))
            if self._on_progress:
                self._on_progress("file:start", relative_path)
            logger.info(f"Scanning: {relative_path}")

            # Read file content
            content = file_path.read_text(encoding="utf-8")

            # DeepScanner: extract ClassSignatures for Python files
            if file_path.suffix == ".py":
                try:
                    sigs = extract_class_signature(content, relative_path)
                    self._pending_signatures.extend(sigs)
                    self._source_hashes[relative_path] = hashlib.sha256(
                        content.encode()
                    ).hexdigest()[:16]
                except Exception as e:
                    logger.debug(
                        "ClassSignature extraction failed for %s: %s", relative_path, e
                    )

            # Extract symbols based on language
            symbols = []
            if file_path.suffix == ".py":
                symbols = await self._extract_python_symbols(file_path, content)
            elif file_path.suffix in [".ts", ".tsx", ".js", ".jsx"]:
                symbols = await self._extract_typescript_symbols(file_path, content)

            # Compute fingerprint (source + imports)
            imports_raw = []
            if file_path.suffix == ".py":
                try:
                    imports_raw = self.py_analyzer.get_file_imports(str(file_path))
                except Exception:
                    pass  # Non-critical — fingerprint degrades gracefully
            imports_normalized = normalize_imports(imports_raw)
            fingerprint = compute_fingerprint(content, imports_normalized)

            # Determine contract type
            contract = ContractType.AST_PUBLIC_METHODS.value
            if file_path.suffix in (".ts", ".tsx"):
                contract = ContractType.TS_EXPORTS.value

            # Check contract (replaces fidelity)
            contract_status = check_contract(
                source=content,
                symbols_extracted=len(symbols),
                parse_error=parse_error,
            )

            # Process each symbol
            self.stats["symbols_found"] += len(symbols)
            for symbol in symbols:
                await self._process_symbol(
                    symbol,
                    content,
                    use_ai=use_ai,
                    fingerprint=fingerprint,
                    contract_status=contract_status.value,
                )

            # Edge case: file has zero symbols (e.g. __init__.py with only imports).
            # Write a sentinel so incremental scan sees scan_completed=TRUE and skips
            # this file on next run — otherwise it loops forever as "new".
            if len(symbols) == 0:
                await self.registry_v2.insert_symbol(
                    file_path=relative_path,
                    symbol_name="__file_sentinel__",
                    symbol_type="function",  # Must match DB CHECK constraint
                    role="file_sentinel",
                    intent="No extractable symbols in this file",
                    tags=[],
                    confidence=0.0,
                    scan_completed=True,
                    fingerprint=fingerprint,
                    contract_status=contract_status.value,
                )

            self.stats["files_scanned"] += 1

        except Exception as e:
            parse_error = str(e)
            contract_status = ContractStatus.ERROR
            logger.error(f"Error scanning {file_path}: {e}")
            self.stats["errors"] += 1

    @staticmethod
    def _extract_symbol_code(
        symbol: SymbolInfo, file_content: str, max_lines: int = 80
    ) -> str:
        """Extract code snippet for a specific symbol from file content.

        Instead of sending the entire file (up to 1000 chars) to the LLM,
        extract the symbol's own code block. This gives the LLM much better
        context for analysis.

        For functions/classes: extracts from the definition line.
        For variables: extracts the assignment line + surrounding context.
        """
        lines = file_content.splitlines()
        # AST line numbers are 1-based
        start = max(0, symbol.line - 1)  # 0-indexed
        end = min(len(lines), start + max_lines)
        return "\n".join(lines[start:end])

    async def _extract_python_symbols(
        self, file_path: Path, content: str
    ) -> List[SymbolInfo]:
        """Extract symbols from Python file using AST"""
        symbols = []

        try:
            # Parse file to AST
            tree = self.py_analyzer.parse_file(str(file_path))
            if not tree:
                return symbols

            # Extract symbols
            py_symbols = self.py_analyzer.extract_symbols(tree)

            # Extract call graph
            call_extractor = CallGraphExtractor()
            call_relationships = call_extractor.extract(tree)

            # Build calls mapping: function_name -> [called_functions]
            calls_by_function = call_extractor.get_calls_by_function()

            for sym in py_symbols:
                # Preserve raw AST kind (e.g. 'async_function') for structural tag extraction.
                # V2 schema symbol_type uses 'function' for both sync and async,
                # but the kind signal is critical for tag derivation.
                ast_kind = sym.kind
                symbol_type = sym.kind
                if symbol_type == "async_function":
                    symbol_type = "function"  # V2 schema doesn't have async_function

                # Get calls for this symbol
                symbol_calls = calls_by_function.get(sym.name, [])

                symbols.append(
                    SymbolInfo(
                        name=sym.name,
                        type=symbol_type,
                        file_path=str(file_path.relative_to(self.workspace_root)),
                        line=sym.line,
                        char=sym.col,
                        signature=sym.type_hint,
                        calls=symbol_calls,
                        decorators=sym.decorators or [],
                        docstring=sym.docstring,
                        ast_kind=ast_kind,
                    )
                )

        except Exception as e:
            logger.error(f"Python AST parsing failed for {file_path}: {e}")

        return symbols

    async def _extract_typescript_symbols(
        self, file_path: Path, content: str
    ) -> List[SymbolInfo]:
        """Extract symbols from TypeScript/JavaScript file"""
        symbols = []

        if not self.ts_probe:
            logger.warning(f"TypeScript probe not available, skipping {file_path}")
            return symbols

        try:
            # Extract call graph and build SymbolInfo objects from it
            calls_by_function = await self.ts_probe.extract_call_graph(str(file_path))

            for func_name, calls in calls_by_function.items():
                # Skip private helpers but keep dunder methods
                if func_name.startswith("_") and not func_name.startswith("__"):
                    continue
                symbols.append(
                    SymbolInfo(
                        name=func_name,
                        type="function",
                        file_path=str(file_path),
                        line=0,
                        char=0,
                        calls=calls or [],
                    )
                )

            logger.debug(
                "Extracted %d TS/JS symbols from %s",
                len(symbols),
                file_path.name,
            )

        except Exception as e:
            logger.error(f"TypeScript probe failed for {file_path}: {e}")

        return symbols

    async def _process_symbol(
        self,
        symbol: SymbolInfo,
        file_content: str,
        use_ai: bool = False,
        fingerprint: Optional[str] = None,
        contract_status: str = "INCOMPLETE",
    ):
        """Process symbol: semantic analysis, LSH, write to DB"""
        try:
            # ── Guard 0: Skip blacklisted symbols (AI failed >= 3 times) ──
            canonical_uid = f"{symbol.file_path}::{symbol.name}"
            if canonical_uid in self._blacklisted_symbols:
                self.stats["symbols_skipped"] += 1
                logger.debug("Skipping blacklisted symbol: %s", symbol.name)
                return

            # ── Guard 1: Skip high-frequency generic names ──
            if symbol.name in _SKIP_SYMBOL_NAMES:
                self.stats["symbols_skipped"] += 1
                logger.debug("Skipping generic symbol: %s", symbol.name)
                return

            # ── Guard 2: Memory budget on tokenization ──
            tokens = self.lsh_engine.tokenize_code(file_content)
            if len(tokens) > _MAX_TOKEN_COUNT:
                logger.warning(
                    "File too large for LSH: %s (%d tokens > %d limit) — skipping symbol %s",
                    symbol.file_path,
                    len(tokens),
                    _MAX_TOKEN_COUNT,
                    symbol.name,
                )
                self.stats["symbols_skipped"] += 1
                return

            # ── Guard 3: LSH matrix dimension cap ──
            # MinHash signature is (num_hashes,) = (128,) uint32 — fixed size.
            # But compute_minhash does O(len(tokens) * num_hashes) work.
            # Cap total work: tokens * num_hashes must stay under budget.
            lsh_work = len(tokens) * self.lsh_engine.config.num_hashes
            assert lsh_work < _MAX_LSH_MATRIX_ELEMENTS, (
                f"LSH work too large: {lsh_work} elements for {symbol.name} in {symbol.file_path}"
            )

            # Extract symbol-specific code snippet (not the entire file)
            symbol_code = self._extract_symbol_code(symbol, file_content)

            # Compute LSH signature
            minhash = self.lsh_engine.compute_minhash(tokens)

            # Convert signature to bytes for storage
            lsh_signature_bytes = self.lsh_engine.signature_to_bytes(minhash)
            lsh_signature = lsh_signature_bytes.hex()  # Store as hex string

            # Perform semantic analysis (role, intent, tags)
            # When use_ai=False, skip AI analysis and use heuristics only
            semantic_info = await self._semantic_analysis(
                symbol, symbol_code, use_ai=use_ai
            )

            # Write to V2 schema
            result = await self.registry_v2.insert_symbol(
                file_path=symbol.file_path,
                symbol_name=symbol.name,
                symbol_type=symbol.type,
                role=semantic_info.get("role"),
                intent=semantic_info.get("intent"),
                tags=semantic_info.get("tags", []),
                confidence=semantic_info.get("confidence", 0.8),
                lsh_signature=lsh_signature,
                signature=symbol.signature,
                scan_completed=semantic_info.get("scan_completed", False),
                fingerprint=fingerprint,
                contract_status=contract_status,
            )

            # Create morphism edges for calls
            if symbol.calls and result.get("v2_id"):
                await self._create_call_edges(
                    result["v2_id"], symbol.calls, symbol.file_path
                )

            # Create DEFINES edge (file defines symbol)
            if result.get("v2_id"):
                await self._create_defines_edge(result["v2_id"], symbol.file_path)

        except Exception as e:
            logger.error(f"Error processing symbol {symbol.name}: {e}")

    async def _semantic_analysis(
        self, symbol: SymbolInfo, symbol_code: str, use_ai: bool = False
    ) -> Dict[str, Any]:
        """
        Perform semantic analysis to extract role, intent, tags.

        Pipeline (Design 55 — structural-primary):
        1. StructuralTagExtractor produces deterministic tags from AST signals.
        2. If LLM is available and use_ai=True, LLM adds intent + extra tags.
        3. Structural tags are never overridden — LLM is additive only.

        Args:
            symbol: Symbol metadata (name, type, file_path, etc.)
            symbol_code: Extracted code snippet for this specific symbol.
            use_ai: If True, use AI-based enrichment (intent + extra tags).
        """
        # Check if symbol already has scan_completed = TRUE
        async with self.db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT scan_completed, role, intent, tags, confidence
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE f.file_path = $1 AND s.symbol_name = $2
                AND s.deprecated_at IS NULL
            """,
                symbol.file_path,
                symbol.name,
            )

            if (
                existing
                and existing["scan_completed"]
                and not getattr(self, "force_rescan", False)
            ):
                # Skip - already analyzed (unless force_rescan=True)
                self.stats["symbols_skipped"] += 1
                logger.debug(
                    f"Skipping {symbol.name} - already analyzed (scan_completed=TRUE)"
                )
                if self._on_progress:
                    self._on_progress("symbol:skip", symbol.name)
                return {
                    "role": existing["role"],
                    "intent": existing["intent"],
                    "tags": canonicalize_tags(
                        json.loads(existing["tags"])
                        if isinstance(existing["tags"], str)
                        else (existing["tags"] or [])
                    ),
                    "confidence": existing["confidence"] or 0.8,
                    "scan_completed": True,
                }

        # ── Step 1: Structural tag extraction (primary, always runs) ──
        structural_tags = extract_tags(
            kind=symbol.ast_kind or symbol.type,
            source_code=symbol_code,
            symbol_name=symbol.name,
            file_path=symbol.file_path,
            decorators=symbol.decorators,
            call_count=len(symbol.calls),
        )

        # ── Step 2: LLM enrichment (optional, additive only) ──
        llm_intent = f"{symbol.name}"  # Fallback intent = symbol name
        llm_tags: Optional[List[str]] = None

        if use_ai and self.semantic_analyzer:
            try:
                result = await self.semantic_analyzer.analyze_symbol(
                    symbol_name=symbol.name,
                    symbol_type=symbol.type,
                    file_path=symbol.file_path,
                    source_code=symbol_code[:1000]
                    if len(symbol_code) > 1000
                    else symbol_code,
                )

                if result:
                    self.stats["symbols_analyzed"] += 1

                    # Use LLM intent if available and non-garbage
                    if result.intent and not result.intent.startswith("Implements "):
                        llm_intent = result.intent

                    # Pass LLM tags through for merging
                    llm_tags = result.tags

                    # Log progress
                    total_symbols = self.stats["symbols_found"]
                    completed = self.stats["symbols_analyzed"]
                    pct = (
                        100.0 * completed / total_symbols if total_symbols > 0 else 0.0
                    )
                    logger.info(
                        f"LLM enriched {symbol.name} ({completed}/{total_symbols}, {pct:.1f}%)"
                    )
                    if self._on_progress:
                        self._on_progress("symbol:done", symbol.name)

            except Exception as e:
                logger.error(f"LLM enrichment failed for {symbol.name}: {e}")

        # ── Step 3: Merge structural + LLM tags ──
        final_tags = merge_with_llm_tags(structural_tags, llm_tags)

        # Apply canonicalization (bridges variant tags to CQE keys)
        canonical_tags = canonicalize_tags(list(final_tags.tags))

        return {
            "role": final_tags.role,
            "intent": llm_intent,
            "tags": canonical_tags,
            "confidence": 0.8 if final_tags.source == "merged" else 0.9,
            "scan_completed": True,  # Structural analysis always completes
        }

    async def _create_call_edges(
        self, from_symbol_id: int, called_symbols: List[str], file_path: str
    ):
        """Create CALLS morphism edges.

        Enhanced to prioritize same-file symbols for internal method calls.
        This fixes the "edge vacuum" issue where methods calling other methods
        in the same class don't create edges.
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Get CALLS morphism type ID
                morphism_type_id = self.registry_v2._morphism_type_cache.get("CALLS")
                if not morphism_type_id:
                    return

                for called_name in called_symbols:
                    # Handle qualified names (ClassName.method)
                    # Extract just the method name for matching
                    if '.' in called_name:
                        # CQEIndexPipeline._extract_atoms → _extract_atoms
                        called_name = called_name.split('.')[-1]

                    # Strategy 1: Find target symbol in same file (prioritize internal calls)
                    rows = await conn.fetch(
                        """
                        SELECT id FROM symbols
                        WHERE symbol_name = $1
                        AND file_path = $2
                        AND deprecated_at IS NULL
                        LIMIT 1
                    """,
                        called_name,
                        file_path,
                    )

                    # Strategy 2: Find target symbol globally if not found in same file
                    if not rows:
                        rows = await conn.fetch(
                            """
                            SELECT id FROM symbols
                            WHERE symbol_name = $1
                            AND deprecated_at IS NULL
                            LIMIT 1
                        """,
                            called_name,
                        )

                    if rows:
                        to_symbol_id = rows[0]["id"]

                        # Insert morphism edge
                        await conn.execute(
                            """
                            INSERT INTO morphism_edges (
                                from_symbol_id, to_symbol_id, morphism_type_id, weight
                            ) VALUES ($1, $2, $3, $4)
                            ON CONFLICT (from_symbol_id, to_symbol_id, morphism_type_id) DO NOTHING
                        """,
                            from_symbol_id,
                            to_symbol_id,
                            morphism_type_id,
                            0.9,
                        )

                        self.stats["morphisms_created"] += 1

        except Exception as e:
            logger.error(f"Error creating call edges: {e}")

    async def _create_defines_edge(self, symbol_id: int, file_path: str):
        """Create DEFINES morphism edge (file defines symbol)"""
        try:
            async with self.db_pool.acquire() as conn:
                # Get DEFINES morphism type ID
                morphism_type_id = self.registry_v2._morphism_type_cache.get("DEFINES")
                if not morphism_type_id:
                    # Cache miss, reload from DB (same logic as RegistryV2.setup)
                    rows = await conn.fetch(
                        "SELECT id, type_name FROM morphism_types"
                    )
                    self.registry_v2._morphism_type_cache = {
                        row["type_name"]: row["id"] for row in rows
                    }
                    morphism_type_id = self.registry_v2._morphism_type_cache.get(
                        "DEFINES"
                    )
                    if not morphism_type_id:
                        logger.warning("DEFINES morphism type not found")
                        return

                # Get file_id for this file_path
                file_row = await conn.fetchrow(
                    """
                    SELECT id FROM files WHERE file_path = $1
                """,
                    file_path,
                )

                if not file_row:
                    logger.warning(f"File not found: {file_path}")
                    return

                file_id = file_row["id"]

                # Create a pseudo-symbol for the file (or use file_id directly)
                # For now, we'll create DEFINES edge from file's first symbol to this symbol
                # Actually, we need a different approach - DEFINES should be file -> symbol
                # But morphism_edges expects symbol_id -> symbol_id
                # Let's create a file-level symbol entry

                # Get or create file-level symbol
                file_symbol_row = await conn.fetchrow(
                    """
                    SELECT id FROM symbols
                    WHERE file_id = $1 AND symbol_name = '__file__'
                    AND deprecated_at IS NULL
                """,
                    file_id,
                )

                if not file_symbol_row:
                    # Create file-level symbol
                    registry = RegistryV2(self.db_pool, enable_v2_write=True)
                    canonical_uid = registry._compute_canonical_uid(
                        file_path, "__file__"
                    )
                    canonical_hash = registry._compute_canonical_hash(
                        file_path, "__file__"
                    )

                    # Compute content_hash for file-level symbol
                    content_hash = hashlib.sha256(
                        f"{file_path}::__file__".encode()
                    ).hexdigest()[:16]

                    file_symbol_row = await conn.fetchrow(
                        """
                        INSERT INTO symbols (
                            canonical_uid, file_id, symbol_name, symbol_type,
                            content_hash, canonical_hash, role, intent, tags, confidence,
                            scanned_at, updated_at, scan_completed
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, TRUE)
                        ON CONFLICT (canonical_uid) DO UPDATE SET updated_at = $12, scan_completed = TRUE
                        RETURNING id
                    """,
                        canonical_uid,
                        file_id,
                        "__file__",
                        "function",
                        content_hash,
                        canonical_hash,
                        "container",
                        f"File: {file_path}",
                        json.dumps(["file"]),
                        1.0,
                        datetime.utcnow(),
                        datetime.utcnow(),
                    )

                file_symbol_id = file_symbol_row["id"]

                # Insert DEFINES edge: file_symbol -> symbol
                await conn.execute(
                    """
                    INSERT INTO morphism_edges (
                        from_symbol_id, to_symbol_id, morphism_type_id, weight
                    ) VALUES ($1, $2, $3, $4)
                    ON CONFLICT (from_symbol_id, to_symbol_id, morphism_type_id) DO NOTHING
                """,
                    file_symbol_id,
                    symbol_id,
                    morphism_type_id,
                    1.0,
                )

                self.stats["morphisms_created"] += 1

        except Exception as e:
            logger.error(f"Error creating defines edge: {e}")

    def _load_blacklist(self) -> None:
        """Load blacklist from report file."""
        blacklist_path = self.workspace_root / ".quro_context" / "scan_blacklist.jsonl"
        if blacklist_path.exists():
            try:
                for line in blacklist_path.read_text().strip().split("\n"):
                    if line:
                        entry = json.loads(line)
                        self._blacklisted_symbols.add(entry["canonical_uid"])
                logger.info(
                    f"Loaded {len(self._blacklisted_symbols)} blacklisted symbols from report"
                )
            except Exception as e:
                logger.warning(f"Failed to load blacklist: {e}")

    def _write_blacklist_entry(self, symbol: SymbolInfo, failures: List[str]) -> None:
        """Append blacklisted symbol to report file for user review."""
        report_dir = self.workspace_root / ".quro_context"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "scan_blacklist.jsonl"

        uid = f"{symbol.file_path}::{symbol.name}"
        entry = {
            "canonical_uid": uid,
            "symbol_name": symbol.name,
            "file_path": symbol.file_path,
            "symbol_type": symbol.type,
            "failure_reasons": failures,
            "failure_count": self._ai_failure_counts.get(uid, 0),
            "blacklisted_at": datetime.utcnow().isoformat(),
        }

        with open(report_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


async def main():
    """CLI entry point for scanner"""
    import sys

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Get workspace path
    workspace = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

    # Connect to database
    db_pool = await asyncpg.create_pool(QURO_DB_URL, min_size=2, max_size=10)

    # Create scanner
    scanner = WorkspaceScanner(workspace, db_pool, enable_v2_write=True)

    try:
        await scanner.setup()
        await scanner.scan()
    finally:
        await scanner.cleanup()
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())

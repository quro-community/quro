"""
@module: quro_cli.mcp.tools.scan_tools
@intent: Two-phase workspace scanning — deterministic local scan + optional AI enrich

Phase 1 (scan): Parse files, compute fingerprint (source + imports), extract tags,
    compute fidelity. Deterministic, no external AI. Full overwrite on changed files.
Phase 2 (enrich): AI-driven role/intent tagging. Only touches AI-owned columns.
    Conditional on fingerprint change.
"""

import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import asyncpg

from quro_cli.analysis.python_ast_analyzer import PythonASTAnalyzer
from quro_cli.analysis.lsh_engine import MinHashLSH, LSHConfig
from quro_cli.config import QURO_DB_URL
from quro_cli.registry.database import init_database, close_database
from quro_cli.registry.morphism_registry import MorphismRegistry

logger = logging.getLogger(__name__)

# DB symbol_type constraint: only these values are allowed
VALID_SYMBOL_TYPES = frozenset(
    [
        "class",
        "function",
        "interface",
        "type",
        "variable",
        "method",
        "property",
    ]
)

# Default file patterns
DEFAULT_INCLUDE = ["**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"]
DEFAULT_EXCLUDE = [
    "**/node_modules/**",
    "**/.venv/**",
    "**/dist/**",
    "**/__pycache__/**",
    "**/.git/**",
]


def _normalize_symbol_kind(kind: str) -> str:
    """Normalize AST analyzer kind to DB constraint values."""
    if kind in VALID_SYMBOL_TYPES:
        return kind
    # async_function → function, async_method → method
    if kind.startswith("async_"):
        stripped = kind[6:]  # Remove 'async_' prefix
        if stripped in VALID_SYMBOL_TYPES:
            return stripped
    # Fallback: treat unknown kinds as 'function'
    return "function"


def compute_fingerprint(source: str, imports_normalized: str) -> str:
    """Compute semantic fingerprint = SHA256(source + normalized_imports).

    This captures both implementation AND dependency context changes.
    Language-agnostic: Scanner doesn't interpret *why* imports matter,
    just that they changed.
    """
    combined = f"{source}\n__IMPORTS__\n{imports_normalized}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def normalize_imports(imports: List[Any]) -> str:
    """Normalize imports to a deterministic string for fingerprinting.

    Accepts both PythonImport dataclass objects and plain dicts.
    """
    parts = []
    for imp in sorted(imports, key=lambda x: (_imp_source(x), _imp_line(x))):
        source = _imp_source(imp)
        names = _imp_names(imp)
        if isinstance(names, list):
            names = sorted(str(n) for n in names)
        parts.append(f"{source}:{','.join(names)}")
    return "\n".join(parts)


def _imp_source(imp: Any) -> str:
    """Get source module from PythonImport or dict."""
    if hasattr(imp, "module"):
        return imp.module
    return imp.get("source", "") if isinstance(imp, dict) else ""


def _imp_line(imp: Any) -> int:
    """Get line number from PythonImport or dict."""
    if hasattr(imp, "line"):
        return imp.line
    return imp.get("line", 0) if isinstance(imp, dict) else 0


def _imp_names(imp: Any) -> list:
    """Get imported names from PythonImport or dict."""
    if hasattr(imp, "names"):
        return imp.names
    return imp.get("names", []) if isinstance(imp, dict) else []


def compute_fidelity(source: str, symbol_bodies: List[str], file_ext: str) -> float:
    """Compute fidelity = sum(methods in symbols) / total_methods_in_file.

    Args:
        source: Full file source
        symbol_bodies: List of extracted symbol body strings
        file_ext: File extension (.py, .ts, etc.)

    Returns:
        Float in [0.0, 1.0]
    """
    if not source:
        return 1.0

    lang = "typescript" if file_ext in (".ts", ".tsx", ".js", ".jsx") else "python"

    if lang == "python":
        pattern = r"\b(?:async )?def \w+"
    else:
        pattern = r"(?:async )?(?:function|\w+)\s*\("

    total = len(re.findall(pattern, source))
    if total == 0:
        return 1.0

    found = sum(len(re.findall(pattern, body)) for body in symbol_bodies)
    return min(found / total, 1.0)


def detect_language(suffix: str) -> Optional[str]:
    """Map file extension to language string."""
    mapping = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
    }
    return mapping.get(suffix)


class ScanTools:
    """
    @intent: Two-phase workspace scanning — deterministic local scan + optional AI enrich

    Phase 1 (scan): Parse, fingerprint, tag, compute fidelity. No external AI.
    Phase 2 (enrich): AI-driven role/intent. Conditional on fingerprint change.
    """

    def __init__(
        self,
        workspace_root: str,
        db_pool: Optional[asyncpg.Pool] = None,
        db_url: Optional[str] = None,
        analyzer_getter: Optional[callable] = None,
    ):
        self.workspace_root = Path(workspace_root)
        self.db_pool = db_pool  # Legacy: unused, kept for backward compat
        self.db_url = db_url or QURO_DB_URL
        self.analyzer_getter = analyzer_getter

    # =========================================================================
    # Phase 1: Scan (deterministic, local, full overwrite)
    # =========================================================================

    async def scan(
        self,
        file_paths: Optional[List[str]] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Phase 1: Deterministic scan — parse, fingerprint, tag, fidelity.

        Only processes files whose fingerprint changed (unless force=True).
        Returns list of changed files for Phase 2 enrichment.

        Args:
            file_paths: Specific files to scan (relative paths). None = all.
            force: Rescan all files regardless of fingerprint.

        Returns:
            {
                "status": "success" | "error",
                "files_scanned": int,
                "files_changed": int,
                "symbols_found": int,
                "changed_files": [str],  // relative paths for Phase 2
                "duration_ms": int,
            }
        """
        start_time = time.time()

        try:
            db_manager = await init_database(self.db_url)
            registry = MorphismRegistry(db_manager)
            python_analyzer = PythonASTAnalyzer()
            lsh_engine = MinHashLSH(LSHConfig())

            # Discover files
            if file_paths:
                candidates = [self.workspace_root / fp for fp in file_paths]
                candidates = [p for p in candidates if p.is_file()]
            else:
                candidates = self._discover_files()

            files_scanned = 0
            files_changed = 0
            symbols_found = 0
            changed_file_paths: List[str] = []

            for file_path in candidates:
                suffix = file_path.suffix
                language = detect_language(suffix)
                if not language:
                    continue

                logger.debug(f"Parsing {file_path.relative_to(self.workspace_root)}")

                try:
                    source = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Cannot read {file_path}: {e}")
                    continue

                # Parse symbols and imports
                symbols, imports, exports = self._parse_file(
                    file_path, source, language, python_analyzer
                )

                # Compute fingerprint (source + imports)
                imports_normalized = normalize_imports(imports)
                fingerprint = compute_fingerprint(source, imports_normalized)

                # Diff check
                if not force:
                    stored_fp = await registry.get_file_fingerprint(
                        str(file_path.relative_to(self.workspace_root))
                    )
                    if stored_fp == fingerprint:
                        files_scanned += 1
                        continue

                # Fingerprint changed (or force) — full overwrite
                content_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()

                # Compute fidelity
                symbol_bodies = self._extract_symbol_bodies(source, symbols, suffix)
                fidelity = compute_fidelity(source, symbol_bodies, suffix)

                rel_path = str(file_path.relative_to(self.workspace_root))
                logger.info(
                    f"  [changed] {rel_path} ({len(symbols)} symbols, fidelity={fidelity:.2f})"
                )

                # Build morphism data
                morphism_data = {
                    "symbols": [
                        {
                            "name": sym.name,
                            "kind": _normalize_symbol_kind(sym.kind),
                            "line": sym.line,
                            "col": sym.col,
                            "docstring": sym.docstring,
                            "decorators": sym.decorators,
                            "type_hint": sym.type_hint,
                            "role": None,
                            "intent": sym.docstring[:100] if sym.docstring else None,
                            "behavioral_tags": [],
                        }
                        for sym in symbols
                    ],
                    "imports": [
                        {
                            "source": imp.module,
                            "names": imp.names,
                            "alias": imp.alias,
                            "line": imp.line,
                        }
                        for imp in imports
                    ],
                    "exports": [
                        {"name": exp, "is_default": False, "symbol": exp}
                        for exp in exports
                    ],
                }

                rel_path = str(file_path.relative_to(self.workspace_root))
                await registry.save_file_morphism(
                    rel_path,
                    language,
                    content_hash,
                    morphism_data,
                    fingerprint=fingerprint,
                    fidelity=fidelity,
                )

                # Update LSH signatures for symbols
                for symbol in symbols:
                    tags = lsh_engine.extract_behavioral_tags(source, language)
                    signature = lsh_engine.compute_minhash(tags)
                    signature_bytes = lsh_engine.signature_to_bytes(signature)
                    band_hashes = lsh_engine.compute_bands(signature)

                    db_symbol = await registry.get_symbol(symbol.name)
                    if db_symbol:
                        await registry.update_symbol_lsh(
                            db_symbol["id"],
                            signature_bytes,
                            list(tags),
                            band_hashes,
                        )

                files_scanned += 1
                files_changed += 1
                symbols_found += len(symbols)
                changed_file_paths.append(rel_path)

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"Scan complete: {files_scanned} files scanned, "
                f"{files_changed} changed, {symbols_found} symbols, {duration_ms}ms"
            )

            # Record scan
            await registry.record_workspace_scan(
                "full" if force else "incremental",
                files_scanned,
                symbols_found,
                0,
                duration_ms,
            )

            return {
                "status": "success",
                "files_scanned": files_scanned,
                "files_changed": files_changed,
                "symbols_found": symbols_found,
                "changed_files": changed_file_paths,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            logger.error(f"Error in scan: {e}")
            return {"status": "error", "error": str(e)}

    # =========================================================================
    # Phase 2: Enrich (AI, optional, overwrite AI fields only)
    # =========================================================================

    async def enrich(
        self,
        file_paths: Optional[List[str]] = None,
        use_ai: bool = False,
    ) -> Dict[str, Any]:
        """Phase 2: AI-driven role/intent enrichment.

        Only processes files whose AI fields need updating.
        When use_ai=False, this is a no-op (returns changed_files count as 0).

        Args:
            file_paths: Specific files to enrich. None = use all from last scan.
            use_ai: Enable commercial AI tagging (role, intent, behavioral_tags).

        Returns:
            {
                "status": "success",
                "files_enriched": int,
                "symbols_enriched": int,
                "skipped_no_ai": bool,
            }
        """
        if not use_ai:
            return {
                "status": "success",
                "files_enriched": 0,
                "symbols_enriched": 0,
                "skipped_no_ai": True,
                "message": "AI enrichment disabled (use_ai=False)",
            }

        # TODO: Implement AI enrichment pipeline
        # When use_ai=True:
        #   1. For each file in file_paths (or all files):
        #      - Fetch symbols from DB
        #      - Call AI with (symbol_source, imports, bindings) context
        #      - AI returns { role, intent, behavioral_tags }
        #      - UPDATE symbols SET role=$1, intent=$2, behavioral_tags=$3
        #        WHERE id=$4 (only AI-owned columns)
        #
        # The key contract: Phase 2 NEVER touches local-computed fields:
        #   - name, kind, line, col, signature, docstring, type_hint, decorators
        #   - These belong to Phase 1 (scan)
        return {
            "status": "success",
            "files_enriched": 0,
            "symbols_enriched": 0,
            "skipped_no_ai": False,
            "message": "AI enrichment not yet implemented",
        }

    # =========================================================================
    # Backward-compatible aliases (deprecated — use scan() instead)
    # =========================================================================

    async def scan_workspace(
        self,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        incremental: bool = False,
    ) -> Dict[str, Any]:
        """Deprecated: Use scan() instead.

        Preserved for backward compatibility with existing callers.
        """
        logger.warning("scan_workspace() is deprecated — use scan()")
        return await self.scan(force=not incremental)

    async def index_symbols(
        self,
        file_paths: Optional[List[str]] = None,
        force_reindex: bool = False,
    ) -> Dict[str, Any]:
        """Deprecated: Use scan() instead.

        Preserved for backward compatibility with existing callers.
        """
        logger.warning("index_symbols() is deprecated — use scan()")
        result = await self.scan(file_paths=file_paths, force=force_reindex)
        # Map to old response format
        return {
            "status": result["status"],
            "symbols_indexed": result.get("symbols_found", 0),
            "files_processed": result.get("files_scanned", 0),
            "force_reindex": force_reindex,
        }

    # =========================================================================
    # File morphism read/write
    # =========================================================================

    async def get_file_morphism(self, file_path: str) -> Dict[str, Any]:
        """Get file morphism data from registry."""
        try:
            db_manager = await init_database(self.db_url)
            registry = MorphismRegistry(db_manager)
            morphism = await registry.get_file_morphism(file_path)
            if morphism:
                return {
                    "status": "success",
                    "file_path": file_path,
                    "morphism": morphism,
                }
            return {
                "status": "not_found",
                "file_path": file_path,
                "error": "Morphism not found in registry",
            }
        except Exception as e:
            return {"status": "error", "file_path": file_path, "error": str(e)}

    async def save_file_morphism(
        self, file_path: str, morphism_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Save file morphism data to registry."""
        try:
            db_manager = await init_database(self.db_url)
            registry = MorphismRegistry(db_manager)
            await registry.save_morphism(file_path, morphism_data)
            return {"status": "success", "file_path": file_path}
        except Exception as e:
            return {"status": "error", "file_path": file_path, "error": str(e)}

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _discover_files(self) -> List[Path]:
        """Discover files matching default include/exclude patterns."""
        candidates = []
        for pattern in DEFAULT_INCLUDE:
            for file_path in self.workspace_root.glob(pattern):
                if not file_path.is_file():
                    continue
                excluded = any(file_path.match(excl) for excl in DEFAULT_EXCLUDE)
                if not excluded:
                    candidates.append(file_path)
        return candidates

    def _parse_file(
        self,
        file_path: Path,
        source: str,
        language: str,
        python_analyzer: PythonASTAnalyzer,
    ) -> Tuple[List, List, List]:
        """Parse file into symbols, imports, exports.

        Returns:
            (symbols, imports, exports) — types depend on analyzer used.
        """
        if language == "python":
            symbols = python_analyzer.get_file_symbols(str(file_path))
            imports = python_analyzer.get_file_imports(str(file_path))
            exports = python_analyzer.get_file_exports(str(file_path))
        else:
            # TypeScript/JavaScript: return empty lists
            # Future: integrate TypeScript analyzer via analyzer_getter
            symbols = []
            imports = []
            exports = []

        return symbols, imports, exports

    def _extract_symbol_bodies(
        self, source: str, symbols: List, file_ext: str
    ) -> List[str]:
        """Extract symbol body strings for fidelity computation.

        Uses AST for Python, line-range heuristic for others.
        """
        if not symbols:
            return []

        if file_ext == ".py":
            return self._extract_python_bodies(source, symbols)

        # Fallback: return empty — fidelity will default to 1.0
        # Future: integrate TS analyzer for proper body extraction
        return []

    @staticmethod
    def _extract_python_bodies(source: str, symbols: list) -> List[str]:
        """Extract Python symbol bodies using line ranges."""
        lines = source.splitlines()
        bodies = []

        for sym in symbols:
            start = sym.line - 1  # 0-indexed
            if start < 0 or start >= len(lines):
                continue

            # For classes/functions, body extends until dedent
            if sym.kind in ("class", "function"):
                # Find the end by tracking indentation
                body_lines = [lines[start]]
                base_indent = len(lines[start]) - len(lines[start].lstrip())

                for i in range(start + 1, len(lines)):
                    line = lines[i]
                    if not line.strip():
                        body_lines.append(line)
                        continue
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent <= base_indent and line.strip():
                        break
                    body_lines.append(line)

                bodies.append("\n".join(body_lines))
            else:
                bodies.append(lines[start])

        return bodies

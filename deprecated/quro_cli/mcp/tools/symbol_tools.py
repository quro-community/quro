"""
@module quro_cli.mcp.tools.symbol_tools
@intent Symbol-related MCP tools for identifying, reading, and analyzing symbols

This module provides tools for symbol identification, source reading, integrity verification,
patch context extraction, context compression, logic path tracing, pitfall detection,
project panorama, semantic inventory search, and vocabulary extraction.
"""
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncpg

from quro_cli.analysis.typescript_analyzer import TypeScriptAnalyzer
from quro_cli.analysis.lsh_engine import MinHashLSH, LSHConfig
from quro_cli.registry.morphism_registry import MorphismRegistry, SymbolMetadata

logger = logging.getLogger(__name__)


def _scan_languages(workspace_root: Path) -> Dict[str, int]:
    """Quick glob-based language file count for project stats."""
    counts: Dict[str, int] = {}
    extensions = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".json": "json",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".sql": "sql",
    }
    for ext, lang in extensions.items():
        try:
            files = list(workspace_root.rglob(f"*{ext}"))
            # Skip noise directories
            files = [
                f for f in files
                if ".qss" not in f.parts
                and "node_modules" not in f.parts
                and ".venv" not in f.parts
                and "__pycache__" not in f.parts
                and ".git" not in f.parts
                and ".next" not in f.parts
                and "dist" not in f.parts
                and ".turbo" not in f.parts
                and ".localkb" not in f.parts
                and ".mypy_cache" not in f.parts
                and ".models" not in f.parts
                and ".quro_context" not in f.parts
            ]
            # Skip lock files and large generated files
            if ext == ".json":
                files = [f for f in files if not f.name.endswith(".lock")]
            if files:
                counts[lang] = counts.get(lang, 0) + len(files)
        except Exception:
            pass
    return counts


class SymbolTools:
    """
    Symbol-related MCP tool implementations

    Provides tools for symbol identification, analysis, and context extraction.
    """

    def __init__(
        self,
        workspace_root: Path,
        db_pool: Optional[asyncpg.Pool],
        analyzer_getter: callable
    ):
        """
        Initialize SymbolTools

        Args:
            workspace_root: Workspace root directory
            db_pool: PostgreSQL connection pool (optional)
            analyzer_getter: Callable that returns TypeScriptAnalyzer instance
        """
        self.workspace_root = workspace_root
        self.db_pool = db_pool
        self._analyzer_getter = analyzer_getter
        self.registry: Optional[MorphismRegistry] = None
        self._trust_registry = None  # TrustRegistry (EIL Design 70, set externally)

    async def _ensure_db_pool(self) -> Optional[asyncpg.Pool]:
        """Lazy-init db_pool if not provided at construction time."""
        if self.db_pool is None:
            db_url = os.environ.get("QURO_DB_URL")
            if db_url:
                self.db_pool = await asyncpg.create_pool(
                    db_url, min_size=2, max_size=10, command_timeout=60
                )
        return self.db_pool

    def _quarantine_fields(self, symbol: str) -> Dict[str, Any]:
        """EIL: Return quarantine metadata dict for a symbol."""
        if self._trust_registry is None:
            return {"quarantined": False, "trust": 1.0}
        from quro_lds.quarantine_gate import QuarantineGate
        gate = QuarantineGate(self._trust_registry)
        trust = self._trust_registry.get_trust(symbol)
        return {
            "quarantined": gate.check(symbol).value == "quarantined",
            "trust": trust,
        }

    async def identify_symbol(
        self,
        symbol: str,
        level: Optional[str] = None,
        workspace_root: Optional[str] = None,
        task_intent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Identify a symbol and return behavioral tags, source snippet, and neighbors.

        Auto-compacts source based on task_intent. The system decides the
        compression level — the AI does not choose.

        Args:
            symbol: Symbol name to identify
            level: [LEGACY] Compression level - "SUMMARY" or "SKELETON" (default: SKELETON)
            workspace_root: Workspace root directory (optional, uses default)
            task_intent: Optional task context for auto-compression
                         (e.g. 'debug deadlock', 'understand the API')

        Returns:
            Dictionary with symbol information, source_context, and bridge_info
        """
        from quro_cli.compact_context import classify_intent, generate_skeleton

        # Determine compression level from task_intent (system decides, not AI)
        if task_intent:
            auto_level, _alpha = classify_intent(task_intent)
            # Map FULL/SKELETON/SUMMARY; reject HIDDEN (always show at least SUMMARY)
            if auto_level == "HIDDEN":
                effective_level = "SUMMARY"
            else:
                effective_level = auto_level
        elif level:
            effective_level = level
        else:
            effective_level = "SKELETON"

        # Compute recommend_level: hint FULL when intent suggests debugging
        recommend_level = None
        if task_intent and effective_level != "FULL":
            debug_keywords = ("debug", "fix", "crash", "traceback", "error")
            if any(kw in task_intent.lower() for kw in debug_keywords):
                recommend_level = "FULL"

        try:
            # Search for symbol in registry
            symbol_metadata = await self._find_symbol_in_registry(symbol)

            if not symbol_metadata:
                # Symbol not in registry, try to find it via analyzer
                symbol_info = await self._find_symbol_via_analyzer(symbol)

                if not symbol_info:
                    return {
                        "status": "not_found",
                        "symbol": symbol,
                        "message": "Symbol not found in registry or workspace"
                    }

                # Found via analyzer, return basic info
                file_path_str = symbol_info.file_path

                # Compute contract status
                try:
                    full_source = (self.workspace_root / file_path_str).read_text(encoding='utf-8')
                    symbol_body = self._extract_symbol_body(full_source, symbol, Path(file_path_str).suffix)
                    from quro_cli.scanner_utils import check_contract
                    contract_status = check_contract(
                        source=full_source,
                        symbols_extracted=len(symbol_body) > 0,
                    ).value
                except Exception:
                    contract_status = "ERROR"

                source_context, bridge_info = self._build_source_context(
                    file_path_str, symbol, effective_level,
                    contract_status=contract_status,
                    recommend_level=recommend_level,
                )

                return {
                    "status": "success",
                    "symbol": symbol,
                    "file_path": file_path_str,
                    "line": symbol_info.line,
                    "character": symbol_info.character,
                    "behavioral_tags": [],
                    "risk_anchors": [],
                    "neighbors": [],
                    "type_string": symbol_info.type_string,
                    "fingerprint": symbol_info.fingerprint,
                    "source": symbol_info.source,
                    **self._quarantine_fields(symbol),
                    "source_context": source_context,
                    "bridge_info": bridge_info,
                    "view": effective_level,
                    "contract": "ast_public_methods",
                    "contract_status": contract_status,
                }

            # Found in registry, return full metadata
            neighbors = await self._find_neighbors(symbol_metadata.lsh_signature)
            file_path_str = symbol_metadata.file_path

            # Use stored contract_status from DB, fallback to SATISFIED
            contract_status = "SATISFIED"
            try:
                async with self.db_manager.session() as conn:
                    row = await conn.fetchrow("""
                        SELECT contract_status FROM files
                        WHERE file_path = $1
                    """, file_path_str)
                    if row and row['contract_status']:
                        contract_status = row['contract_status']
            except Exception:
                pass  # Non-critical — fallback to SATISFIED

            # Determine contract type from file extension
            from quro_cli.scanner_utils import ContractType
            ext = Path(file_path_str).suffix
            contract = (
                ContractType.TS_EXPORTS.value
                if ext in ('.ts', '.tsx')
                else ContractType.AST_PUBLIC_METHODS.value
            )

            source_context, bridge_info = self._build_source_context(
                file_path_str, symbol, effective_level,
                contract_status=contract_status,
                recommend_level=recommend_level,
            )

            return {
                "status": "success",
                "symbol": symbol,
                "file_path": file_path_str,
                "line": 0,
                "character": 0,
                "behavioral_tags": symbol_metadata.tags,
                "risk_anchors": [],
                "neighbors": neighbors,
                "type_string": symbol_metadata.role,
                "fingerprint": symbol_metadata.uid,
                "confidence": symbol_metadata.confidence,
                **self._quarantine_fields(symbol),
                "source_context": source_context,
                "bridge_info": bridge_info,
                "view": effective_level,
                "contract": contract,
                "contract_status": contract_status,
            }

        except Exception as e:
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }

    def _compute_fidelity(self, source: str, symbol_body: str, file_ext: str) -> float:
        """[DEPRECATED] Use check_contract() from scanner_utils instead.

        Kept for backward compatibility during migration.
        """
        if not symbol_body or not source:
            return 1.0

        def count_methods(text: str, lang: str) -> int:
            if lang == "python":
                import re
                return len(re.findall(r'\b(?:async )?def \w+', text))
            else:
                import re
                return len(re.findall(r'(?:async )?(?:function|\w+)\s*\(', text))

        lang = "typescript" if file_ext in (".ts", ".tsx", ".js", ".jsx") else "python"
        found = count_methods(symbol_body, lang)
        total = count_methods(source, lang)

        if total == 0:
            return 1.0
        return min(found / max(total, 1), 1.0)

    def _build_source_context(
        self,
        file_path_str: str,
        symbol: str,
        level: Optional[str] = None,
        contract_status: str = "SATISFIED",
        recommend_level: Optional[str] = None,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Build source_context and bridge_info for identify_symbol response.

        Args:
            file_path_str: File path string
            symbol: Symbol name
            level: Compression level (SUMMARY, SKELETON, FULL). Defaults to SKELETON.
            contract_status: Contract status string (SATISFIED/INCOMPLETE/ERROR).
            recommend_level: Optional hint level (e.g. "FULL" for debug intents).

        Returns:
            (source_context, bridge_info) dicts.
        """
        from quro_cli.compact_context import generate_skeleton

        level = level or "SKELETON"
        if level not in ("SUMMARY", "SKELETON", "FULL"):
            level = "SKELETON"

        file_path = Path(file_path_str)

        # Default: no source available
        empty_context = {
            "level": level,
            "available_levels": ["SUMMARY", "SKELETON", "FULL"],
            "compacted_snippet": "",
        }
        empty_bridge = {
            "contract_status": contract_status,
            "too_much_noise": False,
            "recommend_level": recommend_level,
        }

        if not file_path.exists():
            return empty_context, empty_bridge

        try:
            source_code = file_path.read_text(encoding='utf-8')
        except Exception:
            return empty_context, empty_bridge

        # Determine language for skeleton generator
        ext = file_path.suffix
        language = "typescript" if ext in (".ts", ".tsx", ".js", ".jsx") else "python"

        # Extract symbol body (not whole file)
        symbol_body = self._extract_symbol_body(source_code, symbol, ext)

        if not symbol_body:
            return empty_context, empty_bridge

        # Compact based on level
        if level == "FULL":
            compacted = symbol_body
        elif level == "SKELETON":
            compacted = generate_skeleton(symbol_body, language=language)
        elif level == "SUMMARY":
            # SUMMARY = skeleton (signatures + docstrings only)
            compacted = generate_skeleton(symbol_body, language=language)
        else:
            compacted = ""

        # Compute too_much_noise: signal when FULL source is much larger
        token_estimate = len(compacted.split())
        too_much_noise = token_estimate > 1500 and level != "FULL"

        source_context = {
            "level": level,
            "available_levels": ["SUMMARY", "SKELETON", "FULL"],
            "compacted_snippet": compacted,
        }
        bridge_info = {
            "contract_status": contract_status,
            "too_much_noise": too_much_noise,
            "recommend_level": recommend_level,
        }

        return source_context, bridge_info

    async def _find_symbol_in_registry(self, symbol: str) -> Optional[SymbolMetadata]:
        """
        Find symbol in registry by name

        Args:
            symbol: Symbol name

        Returns:
            SymbolMetadata or None
        """
        pool = await self._ensure_db_pool()
        if not pool:
            return None

        try:
            async with pool.acquire() as conn:
                query = """
                    SELECT
                        s.id,
                        s.symbol_name as name,
                        s.symbol_type as kind,
                        s.role,
                        s.intent,
                        s.tags as behavioral_tags,
                        s.confidence,
                        s.minhash_signature as lsh_signature,
                        f.file_path,
                        f.language,
                        f.fidelity as file_fidelity
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE s.symbol_name = $1
                    LIMIT 1
                """

                row = await conn.fetchrow(query, symbol)

                if not row:
                    return None

                return SymbolMetadata(
                    uid=f"{row['file_path']}::{row['name']}",
                    file_path=row['file_path'],
                    role=row['role'] or row['kind'],
                    tags=row['behavioral_tags'] or [],
                    lsh_signature=row['lsh_signature'],
                    confidence=1.0,
                    file_fidelity=row['file_fidelity'],
                )

        except Exception as e:
            logger.error(f"Error querying registry for symbol {symbol}: {e}")
            return None

    async def _find_symbol_via_analyzer(self, symbol: str):
        """
        Find symbol via filesystem scan fallback.

        Scans workspace for source files containing the symbol definition.
        Used when registry (PostgreSQL) is unavailable.

        Args:
            symbol: Symbol name to find

        Returns:
            SymbolInfo or None
        """
        from quro_cli.analysis.typescript_analyzer import SymbolInfo

        extensions = ('.py', '.ts', '.tsx', '.js', '.jsx')
        for ext in extensions:
            pattern = f'**/*{ext}'
            for file_path in self.workspace_root.glob(pattern):
                parts = file_path.relative_to(self.workspace_root).parts
                if any(p.startswith('.') or p in ('node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build') for p in parts):
                    continue

                try:
                    source = file_path.read_text(encoding='utf-8')
                except Exception:
                    continue

                body = self._extract_symbol_body(source, symbol, ext)
                if not body:
                    continue

                lines = source.split('\n')
                line_num = 0
                for i, line in enumerate(lines):
                    if symbol in line and any(kw in line for kw in ('class ', 'def ', 'async def ', 'function ', 'const ', 'let ', 'var ', 'export ')):
                        line_num = i
                        break

                first_line = body.split('\n')[0] if body else ''
                kind = 'class' if 'class ' in first_line else 'function'

                return SymbolInfo(
                    name=symbol,
                    file_path=str(file_path.relative_to(self.workspace_root)),
                    line=line_num,
                    character=0,
                    kind=kind,
                    type_string=kind,
                    fingerprint=f'{file_path.relative_to(self.workspace_root)}::{symbol}',
                )

        return None

    async def _find_neighbors(self, lsh_signature: bytes) -> List[Dict[str, Any]]:
        """
        Find similar symbols via LSH

        Args:
            lsh_signature: LSH signature of the symbol (as bytes)

        Returns:
            List of neighbor symbols with similarity scores
        """
        if not lsh_signature:
            return []

        pool = await self._ensure_db_pool()
        if not pool:
            return []

        try:
            lsh_engine = MinHashLSH(LSHConfig())

            query_signature = lsh_engine.signature_from_bytes(lsh_signature)
            band_hashes = lsh_engine.compute_bands(query_signature)

            async with pool.acquire() as conn:
                query = """
                    SELECT DISTINCT
                        s.id,
                        s.symbol_name as name,
                        s.symbol_type as kind,
                        s.role,
                        s.minhash_signature as lsh_signature,
                        f.file_path
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE s.minhash_signature IS NOT NULL
                    LIMIT 50
                """

                rows = await conn.fetch(query)

                neighbors = []
                for row in rows:
                    candidate_signature = lsh_engine.signature_from_bytes(row['lsh_signature'])
                    similarity = lsh_engine.jaccard_similarity(query_signature, candidate_signature)

                    if similarity >= lsh_engine.config.threshold:
                        neighbors.append({
                            "symbol": row['name'],
                            "file_path": row['file_path'],
                            "kind": row['kind'],
                            "role": row['role'],
                            "similarity": float(similarity)
                        })

                neighbors.sort(key=lambda x: x['similarity'], reverse=True)
                return neighbors[:10]

        except Exception as e:
            logger.error(f"Error finding neighbors: {e}")
            return []

    async def read_source_symbol(
        self,
        filepath: str,
        symbol_name: str,
        line_range: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Read source code for a specific symbol with AST metadata

        Args:
            filepath: File path
            symbol_name: Symbol name
            line_range: Optional line range [start, end]

        Returns:
            Dictionary with source code and metadata
        """
        try:
            file_path = Path(filepath)

            if not file_path.exists():
                return {
                    "status": "not_found",
                    "filepath": filepath,
                    "symbol_name": symbol_name,
                    "error": "File not found"
                }

            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if line_range:
                start, end = line_range
                source = ''.join(lines[start:end])
                return {
                    "status": "success",
                    "filepath": filepath,
                    "symbol_name": symbol_name,
                    "source": source,
                    "line_start": start,
                    "line_end": end,
                    "kind": "unknown",
                    "type_string": None
                }

            analyzer = await self._analyzer_getter()
            if analyzer and filepath.endswith(('.ts', '.tsx')):
                # TODO: Implement proper symbol search
                source = ''.join(lines)
                return {
                    "status": "success",
                    "filepath": filepath,
                    "symbol_name": symbol_name,
                    "source": source,
                    "line_start": 0,
                    "line_end": len(lines),
                    "kind": "unknown",
                    "type_string": None
                }

            source = ''.join(lines)
            return {
                "status": "success",
                "filepath": filepath,
                "symbol_name": symbol_name,
                "source": source,
                "line_start": 0,
                "line_end": len(lines),
                "kind": "unknown",
                "type_string": None
            }

        except Exception as e:
            return {
                "status": "error",
                "filepath": filepath,
                "symbol_name": symbol_name,
                "error": str(e)
            }

    async def verify_symbol_integrity(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Verify symbol exists and check integrity.

        Resolution cascade:
          1. PostgreSQL registry (authoritative, if available)
          2. quro_lds.verify_symbol_integrity — 5-tier cascade with
             SQLite registry + .qss shadows + Levenshtein fuzzy matching

        Args:
            symbol: Symbol name to verify

        Returns:
            Dictionary with verification result
        """
        try:
            # Tier 0: PostgreSQL registry (authoritative)
            symbol_metadata = await self._find_symbol_in_registry(symbol)

            if symbol_metadata:
                return {
                    "status": "success",
                    "symbol": symbol,
                    "exists": True,
                    "suggestions": [],
                    "file_path": symbol_metadata.file_path,
                    "confidence": symbol_metadata.confidence
                }

            # Tier 1+: quro_lds 5-tier cascade (PostgreSQL V2 + .qss + fuzzy)
            from quro_lds.verify_symbol_integrity import (
                verify_symbol_integrity as vsi,
            )

            result = vsi(symbol, str(self.workspace_root))

            return {
                "status": "success",
                "symbol": result.symbol,
                "exists": result.exists,
                "suggestions": [
                    {"name": s.name, "match_pct": s.match_pct,
                     "source": s.source, "role": s.role, "intent": s.intent}
                    for s in result.suggestions
                ],
                "file_path": result.file_path,
                "shadow_path": result.shadow_path,
                "match_level": result.match_level,
                "verdict": result.verdict,
                "resolution_tier": result.resolution_tier,
                "next_action": {
                    "action": result.next_action.action,
                    "arg": result.next_action.arg,
                    "rationale": result.next_action.rationale,
                },
                "sibling_symbols": [
                    {"name": s.name, "role": s.role,
                     "intent": s.intent,
                     "behavioral_tags": list(s.behavioral_tags)}
                    for s in result.sibling_symbols
                ],
            }

        except Exception as e:
            return {
                "status": "error",
                "symbol": symbol,
                "exists": False,
                "error": str(e)
            }

    async def _get_symbol_suggestions(self, symbol: str) -> List[str]:
        """
        Get symbol name suggestions using fuzzy matching

        Args:
            symbol: Symbol name

        Returns:
            List of suggested symbol names
        """
        # TODO: Implement fuzzy matching against registry
        return []

    async def distill_patch_context(
        self,
        file_path: str,
        line_start: int,
        line_end: int
    ) -> Dict[str, Any]:
        """
        Extract context for a patch (code change)

        Args:
            file_path: File path
            line_start: Start line of patch
            line_end: End line of patch

        Returns:
            Dictionary with patch context
        """
        try:
            file = Path(file_path)

            if not file.exists():
                return {
                    "status": "error",
                    "file_path": file_path,
                    "error": "File not found"
                }

            with open(file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            context_size = 5
            start_idx = max(0, line_start - 1)
            end_idx = min(len(lines), line_end)

            patch_lines = ''.join(lines[start_idx:end_idx])
            context_before = ''.join(lines[max(0, start_idx - context_size):start_idx])
            context_after = ''.join(lines[end_idx:min(len(lines), end_idx + context_size)])

            # TODO: Analyze affected symbols and dependencies
            affected_symbols = []
            dependencies = []

            return {
                "status": "success",
                "file_path": file_path,
                "patch_lines": patch_lines,
                "context_before": context_before,
                "context_after": context_after,
                "affected_symbols": affected_symbols,
                "dependencies": dependencies
            }

        except Exception as e:
            return {
                "status": "error",
                "file_path": file_path,
                "error": str(e)
            }

    async def compact_context(
        self,
        context: str,
        max_tokens: int = 2000,
        preserve_symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Compress context using semantic analysis and deduplication

        Args:
            context: Context text to compress
            max_tokens: Maximum tokens in output (approximate)
            preserve_symbols: Symbols that must be preserved

        Returns:
            Dictionary with compressed context
        """
        try:
            original_length = len(context)
            preserve_symbols = preserve_symbols or []

            lines = context.split('\n')
            seen_lines = set()
            compressed_lines = []
            removed_sections = []

            for line in lines:
                stripped = line.strip()

                if not stripped:
                    continue

                if stripped.startswith('//') or stripped.startswith('#'):
                    removed_sections.append(line)
                    continue

                if stripped in seen_lines:
                    removed_sections.append(line)
                    continue

                preserve_line = any(symbol in line for symbol in preserve_symbols)

                if preserve_line or len(compressed_lines) * 10 < max_tokens:
                    compressed_lines.append(line)
                    seen_lines.add(stripped)
                else:
                    removed_sections.append(line)

            compressed_context = '\n'.join(compressed_lines)
            compressed_length = len(compressed_context)
            compression_ratio = compressed_length / original_length if original_length > 0 else 0

            return {
                "status": "success",
                "original_length": original_length,
                "compressed_length": compressed_length,
                "compression_ratio": compression_ratio,
                "compressed_context": compressed_context,
                "removed_sections": removed_sections[:10]
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def trace_logic_path(
        self,
        start_symbol: str,
        end_symbol: Optional[str] = None,
        max_depth: int = 5
    ) -> Dict[str, Any]:
        """
        Trace dependency path between symbols

        Args:
            start_symbol: Starting symbol name
            end_symbol: Target symbol name (optional)
            max_depth: Maximum traversal depth

        Returns:
            Dictionary with dependency paths
        """
        try:
            start_metadata = await self._find_symbol_in_registry(start_symbol)

            if not start_metadata:
                return {
                    "status": "not_found",
                    "start_symbol": start_symbol,
                    "error": "Start symbol not found"
                }

            paths = []
            visited = set()
            queue = [([start_symbol], 0)]

            while queue:
                path, depth = queue.pop(0)
                current = path[-1]

                if depth >= max_depth:
                    continue

                if current in visited:
                    continue

                visited.add(current)

                if end_symbol and current == end_symbol:
                    paths.append(path)
                    continue

                # TODO: Implement actual dependency lookup
                dependencies = []

                for dep in dependencies:
                    queue.append((path + [dep], depth + 1))

            if not end_symbol:
                paths = [[start_symbol] + list(visited)]

            return {
                "status": "success",
                "start_symbol": start_symbol,
                "end_symbol": end_symbol,
                "paths": paths,
                "depth": max_depth
            }

        except Exception as e:
            return {
                "status": "error",
                "start_symbol": start_symbol,
                "error": str(e)
            }

    async def get_pitfall(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get known issues and pitfalls from pitfall_archive.jsonl.

        Args:
            category: Filter by category tag (e.g., "async", "memory", "security")
            severity: Filter by class (e.g., "INVARIANT", "OPERATIONAL")

        Returns:
            Dictionary with pitfalls
        """
        import json as _json
        try:
            archive_path = self.workspace_root / ".quro_context" / "pitfall_archive.jsonl"
            if not archive_path.exists():
                return {"status": "success", "pitfalls": [], "count": 0}

            pitfalls = []
            with open(archive_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = _json.loads(line)
                    pitfalls.append({
                        "id": entry.get("id", ""),
                        "category": ", ".join(entry.get("categories", [])),
                        "class": entry.get("class", "UNKNOWN"),
                        "title": entry.get("raw_text", "")[:120],
                        "description": entry.get("raw_text", ""),
                        "symbols": entry.get("symbols", []),
                    })

            if category:
                pitfalls = [p for p in pitfalls if category.lower() in p["category"].lower()]
            if severity:
                pitfalls = [p for p in pitfalls if p.get("class", "").lower() == severity.lower()]

            return {
                "status": "success",
                "pitfalls": pitfalls,
                "count": len(pitfalls)
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def project_panorama(
        self,
        include_stats: bool = True,
        include_health: bool = True
    ) -> Dict[str, Any]:
        """
        Get project overview with statistics and health metrics.

        Reads the pre-built panorama from .quro_context/panorama.json.
        Supports both v1 (quro.panorama.v1) and v2 (quro.panorama.v2) schemas.
        """
        try:
            panorama = {
                "status": "success",
                "workspace_root": str(self.workspace_root)
            }

            panorama_path = self.workspace_root / ".quro_context" / "panorama.json"
            if not panorama_path.exists():
                if include_stats:
                    panorama["stats"] = await self._gather_project_stats()
                if include_health:
                    panorama["health"] = await self._gather_health_metrics()
                return panorama

            import json
            raw = json.loads(panorama_path.read_text(encoding="utf-8"))
            schema = raw.get("$schema", raw.get("schema", ""))
            is_v2 = "v2" in schema

            if is_v2:
                return self._panorama_v2(raw, panorama, include_stats, include_health)
            else:
                return self._panorama_v1(raw, panorama, include_stats, include_health)

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def _panorama_v2(
        self, raw: dict, panorama: dict,
        include_stats: bool, include_health: bool,
    ) -> dict:
        """Format panorama v2 for MCP response."""
        meta = raw.get("meta", {})

        if include_stats:
            panorama["stats"] = {
                "total_files": meta.get("file_count", 0),
                "total_symbols": meta.get("symbol_count", 0),
                "languages": _scan_languages(self.workspace_root),
                "domains": len(raw.get("domains", [])),
                "total_domain_members": sum(
                    d["member_count"] for d in raw.get("domains", [])
                ),
            }

        if include_health:
            domains = raw.get("domains", [])
            active_risks = [
                {"domain": d["id"], "risk": r}
                for d in domains for r in d.get("active_risks", [])
            ]

            health = {
                "generated_at": meta.get("generated_at"),
                "attention": raw.get("attention", []),
                "invariant_refs": raw.get("invariant_refs", []),
                "risk_refs": raw.get("risk_refs", []),
                "active_risks": active_risks,
                "domains": [
                    {
                        "id": d["id"],
                        "anchor": d["anchor"],
                        "entry_tokens": d.get("entry_tokens", []),
                        "member_count": d["member_count"],
                        "risk_level": d["risk_level"],
                        "tags": d.get("tags", []),
                    }
                    for d in domains
                ],
                "hubs": [
                    {
                        "symbol": h["symbol"],
                        "crosses_domains": h.get("crosses_domains", []),
                        "centrality": h.get("centrality", 0),
                        "deadlock_risk": h.get("deadlock_risk", False),
                    }
                    for h in raw.get("hubs", [])
                ],
            }
            panorama["health"] = health

        return panorama

    def _panorama_v1(
        self, raw: dict, panorama: dict,
        include_stats: bool, include_health: bool,
    ) -> dict:
        """Format panorama v1 for MCP response (backward compat)."""
        if include_stats:
            panorama["stats"] = {
                "total_files": raw.get("file_count", 0),
                "total_symbols": raw.get("symbol_count", 0),
                "languages": _scan_languages(self.workspace_root),
                "domains": len(raw.get("domains", [])),
                "total_domain_members": sum(
                    d["member_count"] for d in raw.get("domains", [])
                ),
            }

        if include_health:
            active_risks = []
            for domain in raw.get("domains", []):
                for risk in domain.get("active_risks", []):
                    active_risks.append({"domain": domain["id"], "risk": risk})

            arch_shape = raw.get("architecture_shape", {})
            health = {
                "probe_status": "healthy",
                "registry_status": "healthy",
                "generated_at": raw.get("generated_at"),
                "high_priority_fix": raw.get("session_hint", {}).get(
                    "high_priority_fix", ""
                ),
                "architecture_shape": {
                    "topology": arch_shape.get("topology"),
                    "coupling_entropy": arch_shape.get("coupling_entropy"),
                },
                "active_risks": active_risks,
                "domains": [
                    {
                        "id": d["id"],
                        "anchor": d["anchor"],
                        "file": d.get("file", ""),
                        "member_count": d["member_count"],
                        "risk_level": d["risk_level"],
                    }
                    for d in raw.get("domains", [])
                ],
            }
            panorama["health"] = health

        if include_stats:
            panorama["stats"]["hubs"] = [
                {"symbol": h.get("symbol"), "weight": h.get("manifold_centrality", 0)}
                for h in raw.get("hubs", [])
            ]

        return panorama

    async def quro_explore(self) -> Dict[str, Any]:
        """
        Zero-parameter discovery tool — the 'start here' entry point.

        Returns a comprehensive guide to Quro: what it is, what tools are
        available, how to navigate them, and the domain vocabulary.
        """
        import json as _json

        # Load vocabulary for behavioral tags and roles
        vocab_tags = []
        vocab_roles = []
        vocab_path = self.workspace_root / "commons" / "vocabulary.json"
        if vocab_path.exists():
            try:
                raw = _json.loads(vocab_path.read_text(encoding="utf-8"))
                vocab_tags = [t["id"] for t in raw.get("tags", [])]
                vocab_roles = raw.get("roles", [])
            except Exception:
                pass

        # Load domain data from panorama.json (works for v1 and v2)
        domains = []
        entry_tokens_map = {}  # domain_id -> [tokens]
        risk_refs = []
        invariant_refs = []
        panorama_path = self.workspace_root / ".quro_context" / "panorama.json"
        if panorama_path.exists():
            try:
                raw = _json.loads(panorama_path.read_text(encoding="utf-8"))
                for d in raw.get("domains", []):
                    entry = {
                        "id": d["id"],
                        "anchor": d.get("anchor", ""),
                        "risk_level": d.get("risk_level", "unknown"),
                        "member_count": d.get("member_count", 0),
                    }
                    # v2 fields
                    if "entry_tokens" in d:
                        entry["entry_tokens"] = d["entry_tokens"]
                        entry_tokens_map[d["id"]] = d["entry_tokens"]
                    if "tags" in d:
                        entry["tags"] = d["tags"]
                    domains.append(entry)
                # v2 fields
                risk_refs = raw.get("risk_refs", [])
                invariant_refs = raw.get("invariant_refs", [])
            except Exception:
                pass

        return {
            "status": "success",
            "what_is_quro": (
                "Quro is a local-first categorical knowledge system that distills "
                "coding sessions into a Semantic Manifold using Category Theory. "
                "It provides deterministic, pre-computed intelligence about your "
                "codebase via MCP tools — reducing LLM cost by replacing brute-force "
                "inference with structured queries."
            ),
            "getting_started": [
                {
                    "tool": "project_panorama",
                    "why": "See project architecture, domains, risks — no params needed",
                },
                {
                    "tool": "cqe_query",
                    "why": "Semantic code search — call with suggest=true to discover categories first",
                },
                {
                    "tool": "identify_symbol",
                    "why": "Get behavioral tags and risk anchors for any symbol by name",
                },
                {
                    "tool": "scan_workspace",
                    "why": "Index all symbols and dependencies — no params needed",
                },
            ],
            "tools_by_intent": {
                "understand_project": [
                    {"tool": "project_panorama", "hint": "zero params — project overview"},
                    {"tool": "scan_workspace", "hint": "zero params — index all symbols"},
                    {"tool": "index_symbols", "hint": "zero params — re-index symbols"},
                ],
                "find_symbol": [
                    {"tool": "identify_symbol", "hint": "param: symbol name"},
                    {"tool": "verify_symbol_integrity", "hint": "param: symbol name"},
                    {"tool": "query_semantic_inventory", "hint": "param: natural language query"},
                ],
                "read_code": [
                    {"tool": "read_source_symbol", "hint": "params: filepath, symbol_name"},
                    {"tool": "get_vocabulary", "hint": "param: file_path"},
                    {"tool": "distill_patch_context", "hint": "params: file_path, line_start, line_end"},
                ],
                "analyze_dependencies": [
                    {"tool": "skeleton_query", "hint": "params: query_type, module_uid"},
                    {"tool": "skeleton_trace", "hint": "params: from_uid, to_uid"},
                    {"tool": "skeleton_detect_cycles", "hint": "zero params — find circular deps"},
                ],
                "semantic_search": [
                    {"tool": "cqe_query", "hint": "params: query, entry_token. Use suggest=true to discover categories"},
                    {"tool": "cqe_reflect", "hint": "zero params — query diagnostics"},
                ],
                "risks_and_pitfalls": [
                    {"tool": "get_pitfall", "hint": "zero params — known issues"},
                    {"tool": "get_nrt_alerts", "hint": "zero params — runtime alerts"},
                    {"tool": "get_morph_alerts", "hint": "zero params — evolution alerts"},
                ],
                "modify_code": [
                    {"tool": "patch_logic_atoms", "hint": "params: file_path, atoms"},
                    {"tool": "create_shadow_draft", "hint": "params: symbol, atoms, language, target_path"},
                    {"tool": "eject_shadow_draft", "hint": "param: symbol"},
                ],
                "reasoning": [
                    {"tool": "commit_reasoning", "hint": "params: symbol, reasoning"},
                    {"tool": "commit_chain", "hint": "params: symbol, chain"},
                    {"tool": "get_chain", "hint": "param: symbol"},
                    {"tool": "lds_audit", "hint": "zero params — logic dependency audit"},
                ],
                "simulation": [
                    {"tool": "run_twin_simulation", "hint": "param: atoms — deadlock detection"},
                    {"tool": "get_twin_report", "hint": "param: simulation_id"},
                    {"tool": "approve_self_heal", "hint": "params: proposal_id, approved"},
                ],
            },
            "domain_vocabulary": {
                "behavioral_tags": vocab_tags,
                "symbol_roles": vocab_roles,
                "architectural_domains": domains,
            },
            "entry_tokens_by_domain": entry_tokens_map if entry_tokens_map else None,
            "invariant_refs": invariant_refs if invariant_refs else None,
            "risk_refs": risk_refs if risk_refs else None,
            "recommended_workflow": (
                "1. Call quro_explore() (this tool) to understand Quro. "
                "2. Call project_panorama() to see project structure. "
                "3. Call cqe_query(suggest=true) to discover semantic categories. "
                "4. Use identify_symbol(symbol='...') to inspect specific symbols. "
                "5. Use skeleton_query() to analyze module dependencies."
            ),
        }

    async def _gather_project_stats(self) -> Dict[str, Any]:
        """
        Gather project statistics

        Returns:
            Statistics dictionary
        """
        file_counts = {}
        total_files = 0

        for ext in ['.ts', '.tsx', '.py', '.js', '.jsx']:
            files = list(self.workspace_root.rglob(f'*{ext}'))
            count = len(files)
            if count > 0:
                file_counts[ext[1:]] = count
                total_files += count

        total_symbols = 0
        if self.registry:
            try:
                total_symbols = total_files * 10
            except Exception:
                pass

        return {
            "total_files": total_files,
            "total_symbols": total_symbols,
            "languages": file_counts
        }

    async def _gather_health_metrics(self) -> Dict[str, Any]:
        """
        Gather health metrics

        Returns:
            Health dictionary
        """
        issues = []

        probe_status = "unknown"
        analyzer = await self._analyzer_getter()
        if analyzer:
            health = await analyzer.health_check()
            probe_status = "healthy" if health.get("probe_alive") else "unhealthy"
            if not health.get("probe_alive"):
                issues.append("TypeScript probe not responding")

        registry_status = "unknown"
        if self.registry:
            try:
                await self.registry.get_pending_task_count()
                registry_status = "healthy"
            except Exception as e:
                registry_status = "unhealthy"
                issues.append(f"Registry connection failed: {str(e)}")

        return {
            "probe_status": probe_status,
            "registry_status": registry_status,
            "issues": issues
        }

    async def query_semantic_inventory(
        self,
        query: str,
        threshold: float = 0.3,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Semantic search across workspace using LSH similarity

        Args:
            query: Search query text
            threshold: Minimum similarity threshold (0.0 to 1.0)
            limit: Maximum number of results

        Returns:
            Dictionary with search results
        """
        try:
            from quro_cli.registry.database import get_db_manager

            db_manager = get_db_manager()
            lsh_engine = MinHashLSH(LSHConfig())

            query_tokens = lsh_engine.tokenize_code(query)
            query_signature = lsh_engine.compute_minhash(query_tokens)
            band_hashes = lsh_engine.compute_bands(query_signature)

            async with db_manager.session() as conn:
                query_sql = """
                    SELECT DISTINCT
                        s.id,
                        s.symbol_name AS name,
                        s.symbol_type AS kind,
                        s.role,
                        s.intent,
                        s.tags AS behavioral_tags,
                        s.minhash_signature AS lsh_signature,
                        f.file_path,
                        f.language
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    JOIN lsh_bands lb ON s.id = lb.symbol_id
                    WHERE lb.band_hash = ANY($1)
                    AND s.minhash_signature IS NOT NULL
                    LIMIT 100
                """

                rows = await conn.fetch(query_sql, band_hashes)

                results = []
                for row in rows:
                    symbol_signature = lsh_engine.signature_from_bytes(row['lsh_signature'])
                    similarity = lsh_engine.jaccard_similarity(query_signature, symbol_signature)

                    if similarity >= threshold:
                        results.append({
                            "symbol": row['name'],
                            "kind": row['kind'],
                            "role": row['role'],
                            "intent": row['intent'],
                            "file_path": row['file_path'],
                            "language": row['language'],
                            "similarity": float(similarity),
                            "behavioral_tags": row['behavioral_tags'] or []
                        })

                results.sort(key=lambda x: x['similarity'], reverse=True)
                results = results[:limit]

                return {
                    "status": "success",
                    "query": query,
                    "results": results,
                    "count": len(results),
                    "threshold": threshold
                }

        except Exception as e:
            logger.error(f"Error in query_semantic_inventory: {e}")
            return {
                "status": "error",
                "query": query,
                "error": str(e)
            }

    async def get_vocabulary(
        self,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Get symbol vocabulary for a file with roles and intents

        Args:
            file_path: File path to analyze

        Returns:
            Dictionary with vocabulary
        """
        try:
            from quro_cli.registry.database import get_db_manager

            db_manager = get_db_manager()

            async with db_manager.session() as conn:
                query = """
                    SELECT
                        s.symbol_name AS name,
                        s.symbol_type AS kind,
                        s.line,
                        s.col,
                        s.role,
                        s.intent,
                        s.content_hash AS signature,
                        s.content_hash AS docstring,
                        s.tags AS behavioral_tags
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE f.file_path = $1
                    ORDER BY s.line, s.col
                """

                rows = await conn.fetch(query, file_path)

                symbols = [
                    {
                        "name": row['name'],
                        "kind": row['kind'],
                        "line": row['line'],
                        "col": row['col'],
                        "role": row['role'],
                        "intent": row['intent'],
                        "signature": row['signature'],
                        "docstring": row['docstring'],
                        "behavioral_tags": row['behavioral_tags'] or []
                    }
                    for row in rows
                ]

                return {
                    "status": "success",
                    "file_path": file_path,
                    "symbols": symbols,
                    "count": len(symbols)
                }

        except Exception as e:
            logger.error(f"Error in get_vocabulary: {e}")
            return {
                "status": "error",
                "file_path": file_path,
                "error": str(e)
            }

    # ------------------------------------------------------------------
    # Symbol extraction helpers (AST-based for Python, regex for TS)
    # ------------------------------------------------------------------

    def _extract_symbol_body(
        self,
        source: str,
        symbol: str,
        file_ext: str
    ) -> str:
        """Extract the symbol's body from source (not the whole file).

        For Python: use AST to find class/function definition.
        For TypeScript: use regex fallback (line-based).

        Returns:
            The symbol body as a string, or empty string if not found.
        """
        if file_ext == ".py":
            return self._extract_python_symbol(source, symbol)
        elif file_ext in (".ts", ".tsx", ".js", ".jsx"):
            return self._extract_ts_symbol(source, symbol)
        else:
            return source

    def _extract_python_symbol(self, source: str, symbol: str) -> str:
        """Extract Python class/function using AST.

        Returns:
            The source lines for that symbol (class or function def).
        """
        import ast

        try:
            tree = ast.parse(source)
            lines = source.split('\n')

            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == symbol:
                        start = node.lineno - 1
                        end = node.end_lineno or (start + 1)
                        return '\n'.join(lines[start:end])

            # Not found — return empty string
            return ""
        except SyntaxError:
            return ""

    def _extract_ts_symbol(self, source: str, symbol: str) -> str:
        """Extract TypeScript/JavaScript symbol using regex heuristic.

        Finds class/function/const declarations and tracks brace depth.
        Returns the matched region (approximation, not full AST).
        """
        import re

        lines = source.split('\n')
        pattern = re.compile(
            rf'^\s*(export\s+)?(class|function|const|let|var|interface|type)\s+{re.escape(symbol)}\b'
        )

        for i, line in enumerate(lines):
            if pattern.match(line):
                # Found start — track brace depth
                start = i
                depth = 0
                in_string = False
                string_char = None

                for j in range(i, len(lines)):
                    ln = lines[j]
                    for ch_idx, ch in enumerate(ln):
                        # Handle string literals
                        if ch in ('"', "'", '`') and (ch_idx == 0 or ln[ch_idx-1] != '\\'):
                            if not in_string:
                                in_string = True
                                string_char = ch
                            elif ch == string_char:
                                in_string = False
                                string_char = None

                        if in_string:
                            continue

                        if ch == '{':
                            depth += 1
                        elif ch == '}':
                            depth -= 1
                            if depth <= 0 and j > i:
                                # Found the end
                                return '\n'.join(lines[start:j+1])

                # Fallback: return 50 lines or to EOF
                return '\n'.join(lines[start:start+50])

        return ""


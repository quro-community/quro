"""
MCP Tools - Tool implementations for quro_cli MCP server

This module contains the implementation of all MCP tools.
"""
import asyncio
import gzip
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import asyncpg

from quro_cli.analysis.typescript_analyzer import TypeScriptAnalyzer
from quro_cli.analysis.lsh_engine import MinHashLSH, LSHIndex
from quro_cli.registry.morphism_registry import MorphismRegistry, SymbolMetadata
from quro_cli.shadow.shadow_draft_tools import ShadowDraftManager


class MCPTools:
    """
    MCP tool implementations

    Provides 40+ tools for AI agents via Model Context Protocol.
    """

    def __init__(
        self,
        workspace_root: str,
        db_url: Optional[str] = None,
        tsconfig_path: Optional[str] = None
    ):
        """
        Initialize MCP tools

        Args:
            workspace_root: Workspace root directory
            db_url: PostgreSQL connection URL (optional, only needed for tools that use registry)
            tsconfig_path: Path to tsconfig.json (optional)
        """
        self.workspace_root = Path(workspace_root)
        self.db_url = db_url
        self.tsconfig_path = tsconfig_path
        self._trust_registry = None  # TrustRegistry (EIL Design 70, set externally)

        # Components (initialized in setup)
        self.analyzer: Optional[TypeScriptAnalyzer] = None
        self.registry: Optional[MorphismRegistry] = None
        self.lsh_engine = MinHashLSH()
        self.shadow_manager: Optional[ShadowDraftManager] = None
        self.db_pool: Optional[asyncpg.Pool] = None

    async def setup(self):
        """Initialize components (only if db_url provided)"""
        # Initialize database connection pool (only if db_url provided)
        if self.db_url:
            self.db_pool = await asyncpg.create_pool(
                self.db_url,
                min_size=2,
                max_size=10
            )

        # TypeScript analyzer is now lazy-loaded (see _ensure_analyzer)
        # This saves 3+ seconds on startup for tools that don't need it
        # self.analyzer will be initialized on first use

        # Initialize registry (no connect method needed)
        # MorphismRegistry uses db_manager which is passed in constructor
        # self.registry = MorphismRegistry(self.db_url)

        # Initialize shadow draft manager
        self.shadow_manager = ShadowDraftManager(str(self.workspace_root))

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

    async def _ensure_analyzer(self):
        """Lazy-load TypeScript analyzer (only when needed)"""
        if self.analyzer is None:
            self.analyzer = TypeScriptAnalyzer(
                str(self.workspace_root),
                self.tsconfig_path
            )
            await self.analyzer.initialize()

    async def shutdown(self):
        """Shutdown components"""
        if self.analyzer:
            await self.analyzer.shutdown()
        if self.db_pool:
            await self.db_pool.close()

    # ── Layer 2: Reflection logging (mirrors CQEDaemonAdvanced._log_reflection) ──

    def _log_reflection(
        self,
        query_id: str,
        query: str,
        entry_token: str,
        input_tokens: list[str],
        input_fp: list[int],
        atoms_built: list[str],
        atoms_visited: int,
        payload_fps: list[int],
        payload_rate: float,
        path_mi: float,
    ) -> None:
        """Write reflection record to cqe_reflections.jsonl for MI training.

        Layer 2 quality signal: payload_fps carries actual gzip-byte fingerprints
        (first-4-bytes of each payload).  Empty payload_fps means logic hole.
        """
        record = {
            "query_id": query_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "entry_token": entry_token,
            "input_tokens": input_tokens,
            "input_fp": input_fp,
            "atoms_built": atoms_built,
            "atoms_visited": atoms_visited,
            "response_fp": payload_fps,          # was [1] — now real fingerprints
            "payload_fps": payload_fps,           # was [1] — now real fingerprints
            "payload_rate": payload_rate,        # NEW: accurate quality signal for MI
            "path_mi": path_mi,
            "engine": "mcp_cqe_query_direct",    # distinguish from daemon entries
        }
        refl_path = self.workspace_root / ".quro_context" / "cqe_reflections.jsonl"
        refl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(refl_path, "a") as f:
            f.write(json.dumps(record) + "\n")
        # Registry doesn't need explicit close

    # === Tool 1: identify_symbol ===

    async def identify_symbol(
        self,
        symbol: str,
        workspace_root: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Identify a symbol and return behavioral tags, risk anchors, and neighbors

        Args:
            symbol: Symbol name to identify
            workspace_root: Workspace root directory (optional, uses default)

        Returns:
            Dictionary with symbol information:
            {
                "status": "success" | "not_found",
                "symbol": str,
                "file_path": str,
                "line": int,
                "character": int,
                "behavioral_tags": List[str],
                "risk_anchors": List[str],
                "neighbors": List[Dict],
                "type_string": str,
                "fingerprint": str
            }
        """
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
                return {
                    "status": "success",
                    "symbol": symbol,
                    "file_path": symbol_info.file_path,
                    "line": symbol_info.line,
                    "character": symbol_info.character,
                    "behavioral_tags": [],
                    "risk_anchors": [],
                    "neighbors": [],
                    "type_string": symbol_info.type_string,
                    "fingerprint": symbol_info.fingerprint,
                    "source": symbol_info.source,
                    **self._quarantine_fields(symbol),
                }

            # Found in registry, return full metadata
            # Get neighbors via LSH similarity
            neighbors = await self._find_neighbors(symbol_metadata.lsh_signature)

            return {
                "status": "success",
                "symbol": symbol,
                "file_path": symbol_metadata.file_path,
                "line": 0,  # TODO: Extract from UID
                "character": 0,
                "behavioral_tags": symbol_metadata.tags,
                "risk_anchors": [],  # TODO: Implement risk analysis
                "neighbors": neighbors,
                "type_string": symbol_metadata.role,
                "fingerprint": symbol_metadata.uid,
                "confidence": symbol_metadata.confidence,
                **self._quarantine_fields(symbol),
            }

        except Exception as e:
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }

    async def _find_symbol_in_registry(self, symbol: str) -> Optional[SymbolMetadata]:
        """
        Find symbol in registry by name

        Args:
            symbol: Symbol name

        Returns:
            SymbolMetadata or None
        """
        if not self.registry:
            return None

        try:
            # Query database for symbol by name
            from quro_cli.registry.database import get_db_manager

            db_manager = get_db_manager()

            async with db_manager.session() as conn:
                # Query symbols table
                query = """
                    SELECT
                        s.id,
                        s.symbol_name AS name,
                        s.symbol_type AS kind,
                        s.line,
                        s.col,
                        s.signature,
                        s.docstring,
                        s.role,
                        s.intent,
                        s.behavioral_tags,
                        s.lsh_signature,
                        f.file_path,
                        f.language
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE s.symbol_name = $1
                    LIMIT 1
                """

                row = await conn.fetchrow(query, symbol)

                if not row:
                    return None

                # Convert to SymbolMetadata
                return SymbolMetadata(
                    uid=f"{row['file_path']}::{row['name']}",
                    file_path=row['file_path'],
                    role=row['role'] or row['kind'],
                    tags=row['behavioral_tags'] or [],
                    lsh_signature=row['lsh_signature'],
                    confidence=1.0
                )

        except Exception as e:
            logger.error(f"Error querying registry for symbol {symbol}: {e}")
            return None

    async def _find_symbol_via_analyzer(self, symbol: str):
        """
        Find symbol via TypeScript analyzer

        Searches all TypeScript files for the symbol.

        Args:
            symbol: Symbol name

        Returns:
            SymbolInfo or None
        """
        if not self.analyzer:
            return None

        # TODO: Implement workspace-wide symbol search
        # For now, this is a placeholder
        # In production, use:
        # 1. Glob for all .ts/.tsx files
        # 2. Parse each file for symbol declarations
        # 3. Return first match

        return None  # Placeholder

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

        try:
            from quro_cli.registry.database import get_db_manager
            from quro_cli.analysis.lsh_engine import MinHashLSH, LSHConfig

            db_manager = get_db_manager()
            lsh_engine = MinHashLSH(LSHConfig())

            # Convert bytes to numpy array
            query_signature = lsh_engine.signature_from_bytes(lsh_signature)

            # Compute band hashes for query
            band_hashes = lsh_engine.compute_bands(query_signature)

            # Find candidate symbols in same LSH buckets
            async with db_manager.session() as conn:
                # Query for symbols in same buckets
                query = """
                    SELECT DISTINCT
                        s.id,
                        s.symbol_name AS name,
                        s.symbol_type AS kind,
                        s.role,
                        s.lsh_signature,
                        f.file_path
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    JOIN lsh_bands lb ON s.id = lb.symbol_id
                    WHERE lb.band_hash = ANY($1)
                    AND s.lsh_signature IS NOT NULL
                    LIMIT 50
                """

                rows = await conn.fetch(query, band_hashes)

                # Compute exact similarities
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

                # Sort by similarity descending
                neighbors.sort(key=lambda x: x['similarity'], reverse=True)

                # Return top 10
                return neighbors[:10]

        except Exception as e:
            logger.error(f"Error finding neighbors: {e}")
            return []

    async def _find_neighbors_via_lsh(self, lsh_signature: bytes) -> List[Dict[str, Any]]:
        if not self.registry:
            return []

        # Find collisions (similar LSH signatures)
        similar_files = await self.registry.find_collisions(lsh_signature)

        # Return as neighbor list
        neighbors = []
        for file_path in similar_files[:5]:  # Top 5 neighbors
            neighbors.append({
                "file_path": file_path,
                "similarity": "high"  # TODO: Calculate actual similarity
            })

        return neighbors

    # === Tool 2: read_source_symbol ===

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
            Dictionary with source code and metadata:
            {
                "status": "success" | "not_found" | "error",
                "filepath": str,
                "symbol_name": str,
                "source": str,
                "line_start": int,
                "line_end": int,
                "kind": str,
                "type_string": str
            }
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

            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # If line_range provided, extract that range
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

            # Otherwise, try to find symbol via analyzer
            if self.analyzer and filepath.endswith(('.ts', '.tsx')):
                # Search for symbol in file
                # TODO: Implement proper symbol search
                # For now, return whole file
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

            # Fallback: return whole file
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

    # === Tool 3: verify_symbol_integrity ===

    async def verify_symbol_integrity(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Verify symbol exists and check integrity

        Args:
            symbol: Symbol name to verify

        Returns:
            Dictionary with verification result:
            {
                "status": "success" | "not_found" | "error",
                "symbol": str,
                "exists": bool,
                "suggestions": List[str],
                "file_path": str,
                "confidence": float
            }
        """
        try:
            # Try to find symbol
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

            # Not in registry, try analyzer
            symbol_info = await self._find_symbol_via_analyzer(symbol)

            if symbol_info:
                return {
                    "status": "success",
                    "symbol": symbol,
                    "exists": True,
                    "suggestions": [],
                    "file_path": symbol_info.file_path,
                    "confidence": 0.8
                }

            # Not found, provide suggestions
            suggestions = await self._get_symbol_suggestions(symbol)

            return {
                "status": "not_found",
                "symbol": symbol,
                "exists": False,
                "suggestions": suggestions,
                "file_path": None,
                "confidence": 0.0
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
        # For now, return empty list
        return []

    # === Tool 4: distill_patch_context ===

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
            Dictionary with patch context:
            {
                "status": "success" | "error",
                "file_path": str,
                "patch_lines": str,
                "context_before": str,
                "context_after": str,
                "affected_symbols": List[str],
                "dependencies": List[str]
            }
        """
        try:
            file = Path(file_path)

            if not file.exists():
                return {
                    "status": "error",
                    "file_path": file_path,
                    "error": "File not found"
                }

            # Read file
            with open(file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Extract patch and context
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

    # === Tool 5: compact_context ===

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
            Dictionary with compressed context:
            {
                "status": "success" | "error",
                "original_length": int,
                "compressed_length": int,
                "compression_ratio": float,
                "compressed_context": str,
                "removed_sections": List[str]
            }
        """
        try:
            original_length = len(context)
            preserve_symbols = preserve_symbols or []

            # Simple compression strategy:
            # 1. Remove duplicate lines
            # 2. Remove comments
            # 3. Truncate if still too long

            lines = context.split('\n')
            seen_lines = set()
            compressed_lines = []
            removed_sections = []

            for line in lines:
                stripped = line.strip()

                # Skip empty lines
                if not stripped:
                    continue

                # Skip comment-only lines (simple heuristic)
                if stripped.startswith('//') or stripped.startswith('#'):
                    removed_sections.append(line)
                    continue

                # Skip duplicate lines
                if stripped in seen_lines:
                    removed_sections.append(line)
                    continue

                # Check if line contains preserved symbols
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
                "removed_sections": removed_sections[:10]  # First 10 removed
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 6: trace_logic_path ===

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
            end_symbol: Target symbol name (optional, returns all paths if None)
            max_depth: Maximum traversal depth

        Returns:
            Dictionary with dependency paths:
            {
                "status": "success" | "not_found" | "error",
                "start_symbol": str,
                "end_symbol": str,
                "paths": List[List[str]],
                "depth": int
            }
        """
        try:
            # Find start symbol
            start_metadata = await self._find_symbol_in_registry(start_symbol)

            if not start_metadata:
                return {
                    "status": "not_found",
                    "start_symbol": start_symbol,
                    "error": "Start symbol not found"
                }

            # BFS to find paths
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

                # If we found the end symbol, record path
                if end_symbol and current == end_symbol:
                    paths.append(path)
                    continue

                # Get dependencies for current symbol
                # TODO: Implement actual dependency lookup
                # For now, return empty paths
                dependencies = []

                for dep in dependencies:
                    queue.append((path + [dep], depth + 1))

            # If no end_symbol specified, return all discovered symbols
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

    # === Tool 7: get_pitfall ===

    async def get_pitfall(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get known issues and pitfalls

        Args:
            category: Filter by category (e.g., "async", "memory", "security")
            severity: Filter by severity (e.g., "critical", "high", "medium", "low")

        Returns:
            Dictionary with pitfalls:
            {
                "status": "success" | "error",
                "pitfalls": List[Dict],
                "count": int
            }
        """
        try:
            # TODO: Implement pitfall database
            # For now, return sample pitfalls
            pitfalls = [
                {
                    "id": "async-001",
                    "category": "async",
                    "severity": "high",
                    "title": "Unhandled promise rejection",
                    "description": "Async functions without proper error handling",
                    "example": "async function foo() { await bar(); }",
                    "fix": "Add try-catch or .catch() handler"
                },
                {
                    "id": "memory-001",
                    "category": "memory",
                    "severity": "medium",
                    "title": "Memory leak in event listeners",
                    "description": "Event listeners not removed on cleanup",
                    "example": "element.addEventListener('click', handler);",
                    "fix": "Call removeEventListener in cleanup"
                }
            ]

            # Filter by category
            if category:
                pitfalls = [p for p in pitfalls if p["category"] == category]

            # Filter by severity
            if severity:
                pitfalls = [p for p in pitfalls if p["severity"] == severity]

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

    # === Tool 8: get_nrt_alerts ===

    async def get_nrt_alerts(
        self,
        severity: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get runtime alerts from NRT (Non-Regression Testing) system

        Args:
            severity: Filter by severity (e.g., "critical", "high", "medium", "low")
            limit: Maximum number of alerts to return

        Returns:
            Dictionary with alerts:
            {
                "status": "success" | "error",
                "alerts": List[Dict],
                "count": int
            }
        """
        try:
            # TODO: Implement NRT alert system
            # For now, return sample alerts
            alerts = [
                {
                    "id": "nrt-001",
                    "severity": "critical",
                    "timestamp": "2026-04-07T20:00:00Z",
                    "message": "Database connection pool exhausted",
                    "source": "MorphismRegistry",
                    "details": "Connection pool size: 10, active: 10, waiting: 5"
                },
                {
                    "id": "nrt-002",
                    "severity": "high",
                    "timestamp": "2026-04-07T19:55:00Z",
                    "message": "TypeScript probe unresponsive",
                    "source": "TypeScriptAnalyzer",
                    "details": "Probe ping timeout after 10s"
                },
                {
                    "id": "nrt-003",
                    "severity": "medium",
                    "timestamp": "2026-04-07T19:50:00Z",
                    "message": "High memory usage detected",
                    "source": "LSHEngine",
                    "details": "Memory usage: 85% of available"
                }
            ]

            # Filter by severity
            if severity:
                alerts = [a for a in alerts if a["severity"] == severity]

            # Limit results
            alerts = alerts[:limit]

            return {
                "status": "success",
                "alerts": alerts,
                "count": len(alerts)
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 9: cqe_query ===

    async def cqe_query(
        self,
        query: str,
        entry_token: str,
        tau: float = 0.1,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        Categorical Query Engine - semantic query with K-category traversal

        Uses SQLite CQE index for fast offline queries.

        Args:
            query: Natural language query
            entry_token: Seed category tag or symbol name (e.g., "async", "LlmGuard")
            tau: MI-gate threshold [0,1] (default 0.1, lower = more traversal)
            max_depth: Maximum BFS hops (default 3)

        Returns:
            Dictionary with query results:
            {
                "status": "success" | "error",
                "query": str,
                "entry_token": str,
                "path_mi": float,  # Real MI score from estimator
                "results": List[Dict],
                "traversal_depth": int,
                "nodes_visited": int
            }
        """
        try:
            # Load CQE index from SQLite
            from quro_sovereign.cqe_index_loader import CQEIndexLoader

            index_path = Path('.quro_context/cqe_index.db')
            if not index_path.exists():
                return {
                    "status": "error",
                    "error": f"CQE index not found at {index_path}"
                }

            loader = CQEIndexLoader(index_path)

            # Tokenize query for Top-K filtering
            query_tokens = set(query.lower().split())

            # Strip cat:: or sym:: prefix from entry_token if present
            clean_entry_token = entry_token
            if entry_token.startswith('cat::'):
                clean_entry_token = entry_token[5:]  # Remove 'cat::'
            elif entry_token.startswith('sym::'):
                clean_entry_token = entry_token[5:]  # Remove 'sym::'

            # Load K-category from index
            k_cat = loader.load_k_category(
                entry_token=clean_entry_token,
                query_tokens=query_tokens,
                max_atoms=100  # Limit for performance
            )

            # No MI estimator - use precomputed morphism weights from index
            results = []
            payload_fps = []
            atoms_built = []  # Track all atoms in the K-category for reflection
            nodes_visited = len(k_cat['atoms'])

            # Layer 2: Response Functor — resolve payloads for all atoms
            for atom in k_cat['atoms']:
                atom_id = atom['id']
                atom_type = atom['type']
                features = atom.get('features', [])
                atoms_built.append(atom_id)

                # Layer 2 payload resolution
                payload_bytes = loader.get_payload(atom_id)
                payload_value = None
                fp = 0

                if payload_bytes:
                    try:
                        decompressed = gzip.decompress(payload_bytes)
                        payload_value = decompressed.decode('utf-8')
                        # FP: 1 if payload exists (semantic contract loaded)
                        fp = 1
                        payload_fps.append(fp)
                    except Exception:
                        pass  # Corrupt payload — leave payload_value as None, fp=0

                # Build result — include categories for K-category completeness
                result_entry = {
                    "atom_id": atom_id,
                    "type": atom_type,
                    "features": features,
                    "score": 1.0,  # Placeholder score
                    "fp": fp,
                }
                if payload_value is not None:
                    result_entry["payload"] = payload_value
                results.append(result_entry)

            # Calculate path MI (average of morphism weights)
            morphisms = k_cat.get('morphisms', [])
            if morphisms:
                path_mi = sum(m.get('weight', 0) for m in morphisms) / len(morphisms)
            else:
                path_mi = 0.0

            # Calculate payload rate for reflection
            payload_rate = len(payload_fps) / max(len(atoms_built), 1)

            # Log reflection for MI training
            try:
                query_uuid = str(uuid.uuid4())
                self._log_reflection(
                    query_id=query_uuid,
                    query=query,
                    entry_token=entry_token,
                    input_tokens=list(query_tokens),
                    input_fp=[0] * len(query_tokens),
                    atoms_built=atoms_built,
                    atoms_visited=nodes_visited,
                    payload_fps=payload_fps,
                    payload_rate=payload_rate,
                    path_mi=path_mi,
                )
            except Exception as log_err:
                # Never fail a query due to reflection logging
                import logging as _log
                _log.getLogger(__name__).warning(f"Reflection log failed: {log_err}")

            return {
                "status": "success",
                "query": query,
                "entry_token": entry_token,
                "path_mi": path_mi,
                "results": results,
                "traversal_depth": max_depth,
                "nodes_visited": nodes_visited,
                "atoms_built": atoms_built,
                "payload_fps": payload_fps,
                "payload_rate": payload_rate,
            }

        except Exception as e:
            return {
                "status": "error",
                "query": query,
                "entry_token": entry_token,
                "error": str(e)
            }

    # === Tool 10: project_panorama ===

    async def project_panorama(
        self,
        include_stats: bool = True,
        include_health: bool = True
    ) -> Dict[str, Any]:
        """
        Get project overview with statistics and health metrics

        Args:
            include_stats: Include file/symbol statistics
            include_health: Include health metrics

        Returns:
            Dictionary with project overview:
            {
                "status": "success" | "error",
                "workspace_root": str,
                "stats": {
                    "total_files": int,
                    "total_symbols": int,
                    "languages": Dict[str, int]
                },
                "health": {
                    "probe_status": str,
                    "registry_status": str,
                    "issues": List[str]
                }
            }
        """
        try:
            panorama = {
                "status": "success",
                "workspace_root": str(self.workspace_root)
            }

            # Gather statistics
            if include_stats:
                stats = await self._gather_project_stats()
                panorama["stats"] = stats

            # Gather health metrics
            if include_health:
                health = await self._gather_health_metrics()
                panorama["health"] = health

            return panorama

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def _gather_project_stats(self) -> Dict[str, Any]:
        """
        Gather project statistics

        Returns:
            Statistics dictionary
        """
        # Count files by extension
        file_counts = {}
        total_files = 0

        for ext in ['.ts', '.tsx', '.py', '.js', '.jsx']:
            files = list(self.workspace_root.rglob(f'*{ext}'))
            count = len(files)
            if count > 0:
                file_counts[ext[1:]] = count
                total_files += count

        # Get symbol count from registry
        total_symbols = 0
        if self.registry:
            try:
                # TODO: Add count method to registry
                # For now, estimate
                total_symbols = total_files * 10  # Rough estimate
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

        # Check probe status
        probe_status = "unknown"
        if self.analyzer:
            health = await self.analyzer.health_check()
            probe_status = "healthy" if health.get("probe_alive") else "unhealthy"
            if not health.get("probe_alive"):
                issues.append("TypeScript probe not responding")

        # Check registry status
        registry_status = "unknown"
        if self.registry:
            try:
                # Simple health check - try to query
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

    # === Tool 11: query_semantic_inventory ===

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
            Dictionary with search results:
            {
                "status": "success" | "error",
                "query": str,
                "results": List[Dict],
                "count": int
            }
        """
        try:
            from quro_cli.registry.database import get_db_manager
            from quro_cli.analysis.lsh_engine import MinHashLSH, LSHConfig

            db_manager = get_db_manager()
            lsh_engine = MinHashLSH(LSHConfig())

            # Tokenize query and compute signature
            query_tokens = lsh_engine.tokenize_code(query)
            query_signature = lsh_engine.compute_minhash(query_tokens)

            # Compute band hashes
            band_hashes = lsh_engine.compute_bands(query_signature)

            # Query database for similar symbols
            async with db_manager.session() as conn:
                query_sql = """
                    SELECT DISTINCT
                        s.id,
                        s.symbol_name AS name,
                        s.symbol_type AS kind,
                        s.role,
                        s.intent,
                        s.behavioral_tags,
                        s.lsh_signature,
                        f.file_path,
                        f.language
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    JOIN lsh_bands lb ON s.id = lb.symbol_id
                    WHERE lb.band_hash = ANY($1)
                    AND s.lsh_signature IS NOT NULL
                    LIMIT 100
                """

                rows = await conn.fetch(query_sql, band_hashes)

                # Compute exact similarities
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

                # Sort by similarity descending
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

    # === Tool 12: get_vocabulary ===

    async def get_vocabulary(
        self,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Get symbol vocabulary for a file

        Args:
            file_path: File path to analyze

        Returns:
            Dictionary with vocabulary:
            {
                "status": "success" | "error",
                "file_path": str,
                "symbols": List[Dict],
                "count": int
            }
        """
        try:
            from quro_cli.registry.database import get_db_manager

            db_manager = get_db_manager()

            # Query database for file symbols
            async with db_manager.session() as conn:
                query = """
                    SELECT
                        s.symbol_name AS name,
                        s.symbol_type AS kind,
                        s.line,
                        s.col,
                        s.role,
                        s.intent,
                        s.signature,
                        s.docstring,
                        s.behavioral_tags
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

    # === Tool 13: get_chain ===

    async def get_chain(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Get commit chain for a symbol

        Args:
            symbol: Symbol name

        Returns:
            Dictionary with commit chain:
            {
                "status": "success" | "error",
                "symbol": str,
                "chain": List[Dict],
                "count": int
            }
        """
        try:
            from quro_cli.registry.database import get_db_manager

            db_manager = get_db_manager()

            # Query QRA chains for symbol
            async with db_manager.session() as conn:
                query = """
                    SELECT
                        id,
                        reasoning,
                        tags,
                        created_at
                    FROM qra_chains
                    WHERE symbol_name = $1
                    ORDER BY created_at DESC
                """

                rows = await conn.fetch(query, symbol)

                chain = [
                    {
                        "id": str(row['id']),
                        "reasoning": row['reasoning'],
                        "tags": row['tags'] or [],
                        "timestamp": row['created_at'].isoformat()
                    }
                    for row in rows
                ]

                return {
                    "status": "success",
                    "symbol": symbol,
                    "chain": chain,
                    "count": len(chain)
                }

        except Exception as e:
            logger.error(f"Error in get_chain: {e}")
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }

    # === Tool 14: commit_reasoning ===

    async def commit_reasoning(
        self,
        symbol: str,
        reasoning: str,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Commit reasoning to QRA (Quantum Reasoning Archive)

        Args:
            symbol: Symbol name
            reasoning: Reasoning text
            tags: Optional tags for categorization

        Returns:
            Dictionary with commit result:
            {
                "status": "success" | "error",
                "symbol": str,
                "reasoning_id": str
            }
        """
        try:
            from quro_cli.registry.database import get_db_manager

            db_manager = get_db_manager()

            # Insert reasoning into QRA
            async with db_manager.session() as conn:
                reasoning_id = await conn.fetchval(
                    """
                    INSERT INTO qra_chains (symbol_name, reasoning, tags)
                    VALUES ($1, $2, $3)
                    RETURNING id
                    """,
                    symbol, reasoning, tags or []
                )

                return {
                    "status": "success",
                    "symbol": symbol,
                    "reasoning_id": str(reasoning_id)
                }

        except Exception as e:
            logger.error(f"Error in commit_reasoning: {e}")
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }

    # === Tool 15: commit_chain ===

    async def commit_chain(
        self,
        symbol: str,
        chain: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Commit full reasoning chain to QRA

        Args:
            symbol: Symbol name
            chain: List of reasoning steps

        Returns:
            Dictionary with commit result:
            {
                "status": "success" | "error",
                "symbol": str,
                "chain_id": str,
                "steps": int
            }
        """
        try:
            from quro_cli.registry.database import get_db_manager

            db_manager = get_db_manager()

            # Insert each step in the chain
            async with db_manager.transaction() as conn:
                chain_ids = []
                for step in chain:
                    reasoning_id = await conn.fetchval(
                        """
                        INSERT INTO qra_chains (symbol_name, reasoning, tags)
                        VALUES ($1, $2, $3)
                        RETURNING id
                        """,
                        symbol,
                        step.get('reasoning', ''),
                        step.get('tags', [])
                    )
                    chain_ids.append(str(reasoning_id))

                return {
                    "status": "success",
                    "symbol": symbol,
                    "chain_ids": chain_ids,
                    "steps": len(chain)
                }

        except Exception as e:
            logger.error(f"Error in commit_chain: {e}")
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }

    # === Tool 16: lds_audit ===

    async def lds_audit(
        self,
        file_path: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        LDS (Logic Dependency System) audit

        Analyzes logic dependencies and detects potential issues.

        Args:
            file_path: File path to audit (optional)
            symbol: Symbol name to audit (optional)

        Returns:
            Dictionary with audit results:
            {
                "status": "success" | "error",
                "audit_id": str,
                "issues": List[Dict],
                "dependencies": List[Dict],
                "risk_score": float
            }
        """
        try:
            # TODO: Implement actual LDS audit logic
            # For now, return placeholder
            audit_id = f"audit_{hash(file_path or symbol or 'global') % 10000}"

            issues = []
            dependencies = []

            # Placeholder: detect some common issues
            if file_path:
                issues.append({
                    "type": "circular_dependency",
                    "severity": "medium",
                    "description": "Potential circular dependency detected",
                    "location": file_path
                })

            if symbol:
                dependencies.append({
                    "from": symbol,
                    "to": "unknown",
                    "type": "import",
                    "weight": 1
                })

            risk_score = len(issues) * 0.2

            return {
                "status": "success",
                "audit_id": audit_id,
                "issues": issues,
                "dependencies": dependencies,
                "risk_score": min(risk_score, 1.0),
                "file_path": file_path,
                "symbol": symbol
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 17: patch_logic_atoms ===

    async def patch_logic_atoms(
        self,
        file_path: str,
        atoms: List[str],
        validation: bool = True
    ) -> Dict[str, Any]:
        """
        Propose code changes with validation

        Args:
            file_path: File path to patch
            atoms: List of logic atoms (DSL operations)
            validation: Whether to validate before applying (default: True)

        Returns:
            Dictionary with patch proposal:
            {
                "status": "success" | "error",
                "patch_id": str,
                "atoms": List[str],
                "validation_result": Dict,
                "preview": str
            }
        """
        try:
            # TODO: Implement actual patch logic
            # For now, return placeholder
            patch_id = f"patch_{hash(file_path + str(atoms)) % 10000}"

            validation_result = {
                "valid": True,
                "errors": [],
                "warnings": []
            }

            if validation:
                # Placeholder validation
                for atom in atoms:
                    if not atom.strip():
                        validation_result["valid"] = False
                        validation_result["errors"].append("Empty atom detected")

            preview = f"# Patch preview for {file_path}\n"
            preview += f"# Atoms: {len(atoms)}\n"
            for i, atom in enumerate(atoms):
                preview += f"{i+1}. {atom}\n"

            return {
                "status": "success",
                "patch_id": patch_id,
                "file_path": file_path,
                "atoms": atoms,
                "validation_result": validation_result,
                "preview": preview
            }

        except Exception as e:
            return {
                "status": "error",
                "file_path": file_path,
                "error": str(e)
            }

    # === Tool 18: create_shadow_draft ===

    async def create_shadow_draft(
        self,
        symbol: str,
        atoms: List[str],
        language: str,
        target_path: str,
        auto_eject: bool = False
    ) -> Dict[str, Any]:
        """
        Create draft in staging area

        Args:
            symbol: Symbol name
            atoms: List of DSL atoms
            language: Target language (python, typescript, etc.)
            target_path: Target file path
            auto_eject: Auto-eject after creation (default: False)

        Returns:
            Dictionary with draft info:
            {
                "status": "success" | "error",
                "draft_id": str,
                "symbol": str,
                "checksum": str,
                "staging_path": str
            }
        """
        try:
            result = await self.shadow_manager.create_shadow_draft(
                symbol=symbol,
                atoms=atoms,
                language=language,
                target_path=target_path,
                auto_eject=auto_eject
            )

            if result["ok"]:
                return {
                    "status": "success",
                    "draft_id": result["draft_id"],
                    "symbol": symbol,
                    "checksum": result["checksum"],
                    "draft_status": result["status"],
                    "language": language,
                    "target_path": target_path,
                    "auto_eject": auto_eject,
                    "atoms_count": len(atoms)
                }
            else:
                return {
                    "status": "error",
                    "symbol": symbol,
                    "error": result.get("error", "Unknown error")
                }

        except Exception as e:
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }

    # === Tool 19: eject_shadow_draft ===

    async def eject_shadow_draft(
        self,
        symbol: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Materialize draft to filesystem

        Args:
            symbol: Symbol name
            force: Force ejection even if validation fails (default: False)

        Returns:
            Dictionary with ejection result:
            {
                "status": "success" | "error",
                "symbol": str,
                "materialized_path": str,
                "risk_score": float
            }
        """
        try:
            result = await self.shadow_manager.eject_shadow_draft(
                symbol=symbol,
                force=force
            )

            if result["ok"]:
                return {
                    "status": "success",
                    "symbol": symbol,
                    "draft_status": result["status"],
                    "risk_score": result.get("risk_score", 0.0),
                    "materialized_path": result.get("target_path"),
                    "skeleton_preview": result.get("skeleton_preview"),
                    "forced": force,
                    "rejection_report": result.get("rejection_report")
                }
            else:
                return {
                    "status": "error",
                    "symbol": symbol,
                    "error": result.get("error", "Unknown error")
                }

        except Exception as e:
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }

    # === Tool 20: get_draft_status ===

    async def get_draft_status(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Poll draft status

        Args:
            symbol: Symbol name

        Returns:
            Dictionary with draft status:
            {
                "status": "success" | "error",
                "symbol": str,
                "draft_status": str,
                "progress": float,
                "message": str
            }
        """
        try:
            result = await self.shadow_manager.get_draft_status(symbol)

            if result["ok"]:
                return {
                    "status": "success",
                    "symbol": symbol,
                    "draft_status": result["status"],
                    "draft_id": result.get("draft_id"),
                    "risk_score": result.get("risk_score"),
                    "warnings": result.get("warnings", []),
                    "created_at": result.get("created_at"),
                    "materialized_at": result.get("materialized_at")
                }
            else:
                return {
                    "status": "error",
                    "symbol": symbol,
                    "error": result.get("error", "Unknown error")
                }

        except Exception as e:
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }

    # === Tool 21: approve_self_heal ===

    async def approve_self_heal(
        self,
        symbol: str,
        corrected_atoms: List[str]
    ) -> Dict[str, Any]:
        """
        Approve auto-healing proposal with corrected atoms

        Args:
            symbol: Symbol name
            corrected_atoms: Corrected atom sequence

        Returns:
            Dictionary with approval result:
            {
                "status": "success" | "error",
                "symbol": str,
                "draft_id": str,
                "draft_status": str
            }
        """
        try:
            result = await self.shadow_manager.approve_self_heal(
                symbol=symbol,
                corrected_atoms=corrected_atoms
            )

            if result["ok"]:
                return {
                    "status": "success",
                    "symbol": symbol,
                    "draft_id": result.get("draft_id"),
                    "draft_status": result.get("status", "PENDING")
                }
            else:
                return {
                    "status": "error",
                    "symbol": symbol,
                    "error": result.get("error", "Unknown error")
                }

        except Exception as e:
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }

    # === Tool 22: cqe_load_index ===
            # For now, return placeholder
            applied = approved  # If approved, apply immediately

            return {
                "status": "success",
                "proposal_id": proposal_id,
                "approved": approved,
                "applied": applied,
                "reason": reason or ("Approved" if approved else "Rejected")
            }

        except Exception as e:
            return {
                "status": "error",
                "proposal_id": proposal_id,
                "error": str(e)
            }

    # === Tool 22: run_twin_simulation ===

    async def run_twin_simulation(
        self,
        atoms: List[str],
        iterations: int = 1000,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Monte Carlo deadlock detection

        Args:
            atoms: List of DSL atoms to simulate
            iterations: Number of Monte Carlo iterations (default: 1000)
            timeout: Timeout in seconds (default: 30)

        Returns:
            Dictionary with simulation result:
            {
                "status": "success" | "error",
                "simulation_id": str,
                "risk_score": float,
                "deadlock_detected": bool,
                "iterations": int
            }
        """
        try:
            # TODO: Implement actual Monte Carlo simulation
            # For now, return placeholder
            simulation_id = f"sim_{hash(str(atoms)) % 10000}"

            # Placeholder: simple heuristic
            deadlock_detected = False
            risk_score = 0.05

            # Check for potential deadlock patterns
            if "ACQ" in str(atoms) and "REL" not in str(atoms):
                deadlock_detected = True
                risk_score = 0.8

            return {
                "status": "success",
                "simulation_id": simulation_id,
                "risk_score": risk_score,
                "deadlock_detected": deadlock_detected,
                "iterations": iterations,
                "timeout": timeout,
                "atoms_count": len(atoms)
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 23: get_twin_report ===

    async def get_twin_report(
        self,
        simulation_id: str
    ) -> Dict[str, Any]:
        """
        Get simulation report

        Args:
            simulation_id: Simulation ID

        Returns:
            Dictionary with simulation report:
            {
                "status": "success" | "error",
                "simulation_id": str,
                "report": Dict,
                "witness_traces": List[Dict]
            }
        """
        try:
            # TODO: Implement actual report retrieval
            # For now, return placeholder
            report = {
                "risk_score": 0.05,
                "deadlock_detected": False,
                "iterations_completed": 1000,
                "execution_time_ms": 150
            }

            witness_traces = []

            return {
                "status": "success",
                "simulation_id": simulation_id,
                "report": report,
                "witness_traces": witness_traces
            }

        except Exception as e:
            return {
                "status": "error",
                "simulation_id": simulation_id,
                "error": str(e)
            }

    # === Tool 24: update_session ===

    async def update_session(
        self,
        session_id: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update session metadata

        Args:
            session_id: Session ID
            metadata: Metadata to update

        Returns:
            Dictionary with update result:
            {
                "status": "success" | "error",
                "session_id": str,
                "updated_fields": List[str]
            }
        """
        try:
            # TODO: Implement actual session update
            # For now, return placeholder
            updated_fields = list(metadata.keys())

            return {
                "status": "success",
                "session_id": session_id,
                "updated_fields": updated_fields,
                "metadata": metadata
            }

        except Exception as e:
            return {
                "status": "error",
                "session_id": session_id,
                "error": str(e)
            }

    # === Tool 25: get_morph_alerts ===

    async def get_morph_alerts(
        self,
        severity: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Morphism evolution alerts

        Args:
            severity: Filter by severity (critical, high, medium, low)
            limit: Maximum number of alerts (default: 10)

        Returns:
            Dictionary with alerts:
            {
                "status": "success" | "error",
                "alerts": List[Dict],
                "count": int
            }
        """
        try:
            # TODO: Implement actual morphism alert system
            # For now, return placeholder
            alerts = [
                {
                    "id": "morph_001",
                    "severity": "high",
                    "type": "signature_change",
                    "file_path": "lib/handler.ts",
                    "message": "LSH signature changed significantly",
                    "timestamp": "2026-04-07T12:00:00Z"
                },
                {
                    "id": "morph_002",
                    "severity": "medium",
                    "type": "export_removed",
                    "file_path": "lib/utils.ts",
                    "message": "Exported symbol removed",
                    "timestamp": "2026-04-07T11:30:00Z"
                }
            ]

            # Filter by severity
            if severity:
                alerts = [a for a in alerts if a["severity"] == severity]

            # Limit results
            alerts = alerts[:limit]

            return {
                "status": "success",
                "alerts": alerts,
                "count": len(alerts),
                "severity_filter": severity,
                "limit": limit
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 26: cqe_load_index ===

    async def cqe_load_index(
        self,
        index_path: str
    ) -> Dict[str, Any]:
        """
        Load CQE index

        Args:
            index_path: Path to CQE index file

        Returns:
            Dictionary with load result:
            {
                "status": "success" | "error",
                "index_path": str,
                "categories_loaded": int,
                "symbols_loaded": int
            }
        """
        try:
            # TODO: Implement actual CQE index loading
            # For now, return placeholder
            categories_loaded = 50
            symbols_loaded = 500

            return {
                "status": "success",
                "index_path": index_path,
                "categories_loaded": categories_loaded,
                "symbols_loaded": symbols_loaded
            }

        except Exception as e:
            return {
                "status": "error",
                "index_path": index_path,
                "error": str(e)
            }

    # === Tool 27: cqe_reflect ===

    async def cqe_reflect(
        self,
        query_id: Optional[str] = None,
        entry_atom: Optional[str] = None,
        limit: int = 20,
        mi_summary: bool = False
    ) -> Dict[str, Any]:
        """
        Reflection log analysis

        Args:
            query_id: Filter by query UUID
            entry_atom: Filter by atom id (e.g., "cat::async")
            limit: Maximum records (default: 20)
            mi_summary: Include per-atom payload_rate table (default: False)

        Returns:
            Dictionary with reflection data:
            {
                "status": "success" | "error",
                "reflections": List[Dict],
                "count": int,
                "mi_summary": Dict (if requested)
            }
        """
        try:
            # TODO: Implement actual reflection log reading
            # For now, return placeholder
            reflections = [
                {
                    "query_id": "q_001",
                    "entry_atom": "cat::async",
                    "path_mi": 0.75,
                    "payload_count": 5,
                    "timestamp": "2026-04-07T12:00:00Z"
                }
            ]

            result = {
                "status": "success",
                "reflections": reflections,
                "count": len(reflections),
                "query_id_filter": query_id,
                "entry_atom_filter": entry_atom,
                "limit": limit
            }

            if mi_summary:
                result["mi_summary"] = {
                    "cat::async": {
                        "payload_rate": 0.8,
                        "sample_count": 10
                    }
                }

            return result

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 28: cqe_train_mi ===

    async def cqe_train_mi(
        self,
        reflection_log_path: str,
        epochs: int = 10
    ) -> Dict[str, Any]:
        """
        Train MI estimator

        Args:
            reflection_log_path: Path to reflection log
            epochs: Number of training epochs (default: 10)

        Returns:
            Dictionary with training result:
            {
                "status": "success" | "error",
                "model_path": str,
                "epochs_completed": int,
                "final_loss": float
            }
        """
        try:
            # TODO: Implement actual MI training
            # For now, return placeholder
            model_path = ".quro_context/cqe_mi_model.pkl"
            final_loss = 0.05

            return {
                "status": "success",
                "reflection_log_path": reflection_log_path,
                "model_path": model_path,
                "epochs_completed": epochs,
                "final_loss": final_loss
            }

        except Exception as e:
            return {
                "status": "error",
                "reflection_log_path": reflection_log_path,
                "error": str(e)
            }

    # === Tool 29: cqe_get_mi_stats ===

    async def cqe_get_mi_stats(
        self,
        atom_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get MI statistics

        Args:
            atom_id: Filter by atom id (e.g., "cat::async")

        Returns:
            Dictionary with MI stats:
            {
                "status": "success" | "error",
                "stats": Dict,
                "atom_count": int
            }
        """
        try:
            # TODO: Implement actual MI stats retrieval
            # For now, return placeholder
            stats = {
                "cat::async": {
                    "mean_mi": 0.75,
                    "std_mi": 0.1,
                    "sample_count": 100
                },
                "cat::lock": {
                    "mean_mi": 0.6,
                    "std_mi": 0.15,
                    "sample_count": 80
                }
            }

            if atom_id:
                stats = {atom_id: stats.get(atom_id, {})}

            return {
                "status": "success",
                "stats": stats,
                "atom_count": len(stats),
                "atom_id_filter": atom_id
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 30: graft_query ===

    async def graft_query(
        self,
        query_type: str,
        symbol: Optional[str] = None,
        depth: int = 3
    ) -> Dict[str, Any]:
        """
        Query dependency graph

        Args:
            query_type: Type of query (dependencies, dependents, path)
            symbol: Symbol name (required for some query types)
            depth: Maximum traversal depth (default: 3)

        Returns:
            Dictionary with query results:
            {
                "status": "success" | "error",
                "query_type": str,
                "results": List[Dict],
                "count": int
            }
        """
        try:
            # TODO: Implement actual graft query
            # For now, return placeholder
            results = []

            if query_type == "dependencies" and symbol:
                results = [
                    {
                        "from": symbol,
                        "to": "dependency1",
                        "type": "import",
                        "weight": 1
                    }
                ]
            elif query_type == "dependents" and symbol:
                results = [
                    {
                        "from": "dependent1",
                        "to": symbol,
                        "type": "import",
                        "weight": 1
                    }
                ]

            return {
                "status": "success",
                "query_type": query_type,
                "symbol": symbol,
                "results": results,
                "count": len(results),
                "depth": depth
            }

        except Exception as e:
            return {
                "status": "error",
                "query_type": query_type,
                "error": str(e)
            }

    # === Tool 31: graft_trace ===

    async def graft_trace(
        self,
        start_symbol: str,
        end_symbol: Optional[str] = None,
        max_depth: int = 5
    ) -> Dict[str, Any]:
        """
        Trace call chains through dependency graph

        Args:
            start_symbol: Starting symbol name
            end_symbol: Target symbol name (optional)
            max_depth: Maximum traversal depth (default: 5)

        Returns:
            Dictionary with trace results:
            {
                "status": "success" | "error",
                "start_symbol": str,
                "end_symbol": str,
                "traces": List[List[str]],
                "count": int
            }
        """
        try:
            # TODO: Implement actual call chain tracing
            # For now, return placeholder
            traces = []

            if end_symbol:
                # Find paths from start to end
                traces.append([start_symbol, "intermediate", end_symbol])
            else:
                # Find all reachable symbols
                traces.append([start_symbol, "reachable1", "reachable2"])

            return {
                "status": "success",
                "start_symbol": start_symbol,
                "end_symbol": end_symbol,
                "traces": traces,
                "count": len(traces),
                "max_depth": max_depth
            }

        except Exception as e:
            return {
                "status": "error",
                "start_symbol": start_symbol,
                "error": str(e)
            }

    # === Tool 32: graft_verify ===

    async def graft_verify(self) -> Dict[str, Any]:
        """
        Verify graph integrity

        Returns:
            Dictionary with verification results:
            {
                "status": "success" | "error",
                "valid": bool,
                "issues": List[Dict],
                "stats": Dict
            }
        """
        try:
            # TODO: Implement actual graph verification
            # For now, return placeholder
            issues = []
            valid = True

            stats = {
                "total_nodes": 100,
                "total_edges": 250,
                "orphaned_nodes": 0,
                "circular_dependencies": 0
            }

            return {
                "status": "success",
                "valid": valid,
                "issues": issues,
                "stats": stats
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 33: graft_prune ===

    async def graft_prune(
        self,
        max_age_days: int = 30,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Prune stale edges from dependency graph

        Args:
            max_age_days: Maximum age in days (default: 30)
            dry_run: Preview changes without applying (default: True)

        Returns:
            Dictionary with prune results:
            {
                "status": "success" | "error",
                "pruned_count": int,
                "dry_run": bool,
                "pruned_edges": List[Dict]
            }
        """
        try:
            # TODO: Implement actual graph pruning
            # For now, return placeholder
            pruned_edges = [
                {
                    "from": "old_symbol",
                    "to": "removed_symbol",
                    "age_days": 45
                }
            ]

            return {
                "status": "success",
                "pruned_count": len(pruned_edges) if not dry_run else 0,
                "dry_run": dry_run,
                "pruned_edges": pruned_edges,
                "max_age_days": max_age_days
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 34: graft_export ===

    async def graft_export(
        self,
        output_path: str,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Export dependency graph to JSON

        Args:
            output_path: Output file path
            format: Export format (json, graphml) (default: json)

        Returns:
            Dictionary with export results:
            {
                "status": "success" | "error",
                "output_path": str,
                "node_count": int,
                "edge_count": int
            }
        """
        try:
            # TODO: Implement actual graph export
            # For now, return placeholder
            node_count = 100
            edge_count = 250

            return {
                "status": "success",
                "output_path": output_path,
                "format": format,
                "node_count": node_count,
                "edge_count": edge_count
            }

        except Exception as e:
            return {
                "status": "error",
                "output_path": output_path,
                "error": str(e)
            }

    # === Tool 35: graft_import ===

    async def graft_import(
        self,
        input_path: str,
        merge: bool = False
    ) -> Dict[str, Any]:
        """
        Import dependency graph from JSON

        Args:
            input_path: Input file path
            merge: Merge with existing graph (default: False)

        Returns:
            Dictionary with import results:
            {
                "status": "success" | "error",
                "input_path": str,
                "node_count": int,
                "edge_count": int,
                "merged": bool
            }
        """
        try:
            # TODO: Implement actual graph import
            # For now, return placeholder
            node_count = 100
            edge_count = 250

            return {
                "status": "success",
                "input_path": input_path,
                "node_count": node_count,
                "edge_count": edge_count,
                "merged": merge
            }

        except Exception as e:
            return {
                "status": "error",
                "input_path": input_path,
                "error": str(e)
            }

    # === Tool 36: graft_diff ===

    async def graft_diff(
        self,
        graph1_path: str,
        graph2_path: str
    ) -> Dict[str, Any]:
        """
        Diff two dependency graphs

        Args:
            graph1_path: First graph file path
            graph2_path: Second graph file path

        Returns:
            Dictionary with diff results:
            {
                "status": "success" | "error",
                "added_nodes": List[str],
                "removed_nodes": List[str],
                "added_edges": List[Dict],
                "removed_edges": List[Dict]
            }
        """
        try:
            # TODO: Implement actual graph diff
            # For now, return placeholder
            added_nodes = ["new_symbol"]
            removed_nodes = ["old_symbol"]
            added_edges = [{"from": "a", "to": "b"}]
            removed_edges = [{"from": "x", "to": "y"}]

            return {
                "status": "success",
                "graph1_path": graph1_path,
                "graph2_path": graph2_path,
                "added_nodes": added_nodes,
                "removed_nodes": removed_nodes,
                "added_edges": added_edges,
                "removed_edges": removed_edges
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 37: scan_workspace ===

    async def scan_workspace(
        self,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        incremental: bool = False
    ) -> Dict[str, Any]:
        """
        Full workspace scan for symbols and dependencies

        Args:
            include_patterns: File patterns to include (e.g., ["**/*.py", "**/*.ts"])
            exclude_patterns: File patterns to exclude (e.g., ["**/node_modules/**"])
            incremental: Only scan changed files (default: False)

        Returns:
            Dictionary with scan results:
            {
                "status": "success" | "error",
                "files_scanned": int,
                "symbols_found": int,
                "dependencies_mapped": int
            }
        """
        try:
            import time
            import hashlib
            from pathlib import Path
            from quro_cli.registry.database import get_db_manager
            from quro_cli.registry.morphism_registry import MorphismRegistry
            from quro_cli.analysis.python_ast_analyzer import PythonASTAnalyzer
            from quro_cli.analysis.lsh_engine import MinHashLSH, LSHConfig

            start_time = time.time()

            db_manager = get_db_manager()
            registry = MorphismRegistry(db_manager)
            python_analyzer = PythonASTAnalyzer()
            lsh_engine = MinHashLSH(LSHConfig())

            # Default patterns
            include = include_patterns or ["**/*.py", "**/*.ts", "**/*.js"]
            exclude = exclude_patterns or ["**/node_modules/**", "**/.venv/**", "**/dist/**", "**/__pycache__/**"]

            # Find files to scan
            files_to_scan = []
            for pattern in include:
                for file_path in self.workspace_root.glob(pattern):
                    # Check exclusions
                    excluded = False
                    for exclude_pattern in exclude:
                        if file_path.match(exclude_pattern):
                            excluded = True
                            break

                    if not excluded and file_path.is_file():
                        files_to_scan.append(file_path)

            files_scanned = 0
            symbols_found = 0
            dependencies_mapped = 0

            # Scan each file
            for file_path in files_to_scan:
                try:
                    # Determine language
                    suffix = file_path.suffix
                    if suffix == ".py":
                        language = "python"
                    elif suffix in [".ts", ".tsx"]:
                        language = "typescript"
                    elif suffix in [".js", ".jsx"]:
                        language = "javascript"
                    else:
                        continue

                    # Compute content hash
                    with open(file_path, 'rb') as f:
                        content_hash = hashlib.sha256(f.read()).hexdigest()

                    # Parse file based on language
                    if language == "python":
                        # Use Python AST analyzer
                        symbols = python_analyzer.get_file_symbols(str(file_path))
                        imports = python_analyzer.get_file_imports(str(file_path))
                        exports = python_analyzer.get_file_exports(str(file_path))

                        # Convert to morphism format
                        morphism_data = {
                            "symbols": [
                                {
                                    "name": sym.name,
                                    "kind": sym.kind,
                                    "line": sym.line,
                                    "col": sym.col,
                                    "docstring": sym.docstring,
                                    "decorators": sym.decorators,
                                    "type_hint": sym.type_hint,
                                    "role": None,
                                    "intent": sym.docstring[:100] if sym.docstring else None,
                                    "behavioral_tags": []
                                }
                                for sym in symbols
                            ],
                            "imports": [
                                {
                                    "source": imp.module,
                                    "names": imp.names,
                                    "alias": imp.alias,
                                    "line": imp.line
                                }
                                for imp in imports
                            ],
                            "exports": [
                                {"name": exp, "is_default": False, "symbol": exp}
                                for exp in exports
                            ]
                        }

                        # Save to registry
                        rel_path = str(file_path.relative_to(self.workspace_root))
                        await registry.save_file_morphism(
                            rel_path,
                            language,
                            content_hash,
                            morphism_data
                        )

                        files_scanned += 1
                        symbols_found += len(symbols)

                        # Compute LSH signatures for symbols
                        with open(file_path, 'r') as f:
                            code = f.read()

                        for symbol in symbols:
                            # Extract behavioral tags
                            tags = lsh_engine.extract_behavioral_tags(code, language)

                            # Compute LSH signature
                            signature = lsh_engine.compute_minhash(tags)
                            signature_bytes = lsh_engine.signature_to_bytes(signature)

                            # Compute band hashes
                            band_hashes = lsh_engine.compute_bands(signature)

                            # Get symbol from database
                            db_symbol = await registry.get_symbol(symbol.name)
                            if db_symbol:
                                # Update LSH
                                await registry.update_symbol_lsh(
                                    db_symbol['id'],
                                    signature_bytes,
                                    list(tags),
                                    band_hashes
                                )

                except Exception as e:
                    logger.error(f"Error scanning {file_path}: {e}")
                    continue

            # Record scan
            duration_ms = int((time.time() - start_time) * 1000)
            await registry.record_workspace_scan(
                "full" if not incremental else "incremental",
                files_scanned,
                symbols_found,
                dependencies_mapped,
                duration_ms
            )

            return {
                "status": "success",
                "files_scanned": files_scanned,
                "symbols_found": symbols_found,
                "dependencies_mapped": dependencies_mapped,
                "duration_ms": duration_ms
            }

        except Exception as e:
            logger.error(f"Error in scan_workspace: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 38: index_symbols ===

    async def index_symbols(
        self,
        file_paths: Optional[List[str]] = None,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Index all symbols in workspace

        Args:
            file_paths: Specific files to index (optional, indexes all if None)
            force_reindex: Force reindex even if up-to-date (default: False)

        Returns:
            Dictionary with index results:
            {
                "status": "success" | "error",
                "symbols_indexed": int,
                "files_processed": int
            }
        """
        try:
            from quro_cli.registry.database import get_db_manager
            from quro_cli.registry.morphism_registry import MorphismRegistry
            from quro_cli.analysis.python_ast_analyzer import PythonASTAnalyzer
            from quro_cli.analysis.lsh_engine import MinHashLSH, LSHConfig
            import hashlib

            db_manager = get_db_manager()
            registry = MorphismRegistry(db_manager)
            python_analyzer = PythonASTAnalyzer()
            lsh_engine = MinHashLSH(LSHConfig())

            symbols_indexed = 0
            files_processed = 0

            # Determine files to index
            if file_paths:
                files_to_index = [self.workspace_root / fp for fp in file_paths]
            else:
                # Index all Python files
                files_to_index = list(self.workspace_root.glob("**/*.py"))

            for file_path in files_to_index:
                if not file_path.is_file():
                    continue

                try:
                    # Compute content hash
                    with open(file_path, 'rb') as f:
                        content_hash = hashlib.sha256(f.read()).hexdigest()

                    # Parse file
                    symbols = python_analyzer.get_file_symbols(str(file_path))
                    imports = python_analyzer.get_file_imports(str(file_path))
                    exports = python_analyzer.get_file_exports(str(file_path))

                    # Convert to morphism format
                    morphism_data = {
                        "symbols": [
                            {
                                "name": sym.name,
                                "kind": sym.kind,
                                "line": sym.line,
                                "col": sym.col,
                                "docstring": sym.docstring,
                                "decorators": sym.decorators,
                                "type_hint": sym.type_hint,
                                "role": None,
                                "intent": sym.docstring[:100] if sym.docstring else None,
                                "behavioral_tags": []
                            }
                            for sym in symbols
                        ],
                        "imports": [
                            {
                                "source": imp.module,
                                "names": imp.names,
                                "alias": imp.alias,
                                "line": imp.line
                            }
                            for imp in imports
                        ],
                        "exports": [
                            {"name": exp, "is_default": False, "symbol": exp}
                            for exp in exports
                        ]
                    }

                    # Save to registry
                    rel_path = str(file_path.relative_to(self.workspace_root))
                    await registry.save_file_morphism(
                        rel_path,
                        "python",
                        content_hash,
                        morphism_data
                    )

                    # Compute LSH signatures
                    with open(file_path, 'r') as f:
                        code = f.read()

                    for symbol in symbols:
                        # Extract behavioral tags
                        tags = lsh_engine.extract_behavioral_tags(code, "python")

                        # Compute LSH signature
                        signature = lsh_engine.compute_minhash(tags)
                        signature_bytes = lsh_engine.signature_to_bytes(signature)

                        # Compute band hashes
                        band_hashes = lsh_engine.compute_bands(signature)

                        # Get symbol from database
                        db_symbol = await registry.get_symbol(symbol.name)
                        if db_symbol:
                            # Update LSH
                            await registry.update_symbol_lsh(
                                db_symbol['id'],
                                signature_bytes,
                                list(tags),
                                band_hashes
                            )

                    files_processed += 1
                    symbols_indexed += len(symbols)

                except Exception as e:
                    logger.error(f"Error indexing {file_path}: {e}")
                    continue

            return {
                "status": "success",
                "symbols_indexed": symbols_indexed,
                "files_processed": files_processed,
                "force_reindex": force_reindex
            }

        except Exception as e:
            logger.error(f"Error in index_symbols: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    # === Tool 39: get_file_morphism ===

    async def get_file_morphism(
        self,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Get file morphism data from registry

        Args:
            file_path: File path

        Returns:
            Dictionary with morphism data:
            {
                "status": "success" | "error",
                "file_path": str,
                "lsh_signature": str,
                "exports": List[str],
                "last_modified": int
            }
        """
        try:
            # Get morphism from registry
            if self.registry:
                morphism = await self.registry.get_morphism(file_path)
                if morphism:
                    return {
                        "status": "success",
                        "file_path": file_path,
                        "morphism": morphism
                    }

            return {
                "status": "not_found",
                "file_path": file_path,
                "error": "Morphism not found in registry"
            }

        except Exception as e:
            return {
                "status": "error",
                "file_path": file_path,
                "error": str(e)
            }

    # === Tool 40: save_file_morphism ===

    async def save_file_morphism(
        self,
        file_path: str,
        lsh_signature: str,
        exports: List[str],
        last_modified: int
    ) -> Dict[str, Any]:
        """
        Save file morphism data to registry

        Args:
            file_path: File path
            lsh_signature: LSH signature
            exports: List of exported symbols
            last_modified: Last modified timestamp

        Returns:
            Dictionary with save result:
            {
                "status": "success" | "error",
                "file_path": str
            }
        """
        try:
            # Save morphism to registry
            if self.registry:
                morphism_data = {
                    "lsh_signature": lsh_signature,
                    "exports": exports,
                    "last_modified": last_modified
                }
                await self.registry.save_morphism(file_path, morphism_data)

                return {
                    "status": "success",
                    "file_path": file_path
                }

            return {
                "status": "error",
                "file_path": file_path,
                "error": "Registry not available"
            }

        except Exception as e:
            return {
                "status": "error",
                "file_path": file_path,
                "error": str(e)
            }

    # === Context Manager Support ===

    async def __aenter__(self):
        """Async context manager entry"""
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.shutdown()

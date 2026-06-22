"""
CQE Tools - Categorical Query Engine operations

@module quro_cli.mcp.tools.cqe_tools
@intent Provide CQE query, reflection, and MI training tools
"""
from __future__ import annotations

import asyncio
import ast
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import asyncpg

from quro_sovereign.cqe_daemon import query_daemon

logger = logging.getLogger(__name__)

_STOP_WORDS = frozenset({
    "the", "and", "for", "how", "what", "why", "is", "are", "to",
    "of", "in", "on", "at", "it", "do", "can", "with", "not", "this",
    "that", "from", "or", "an", "be", "by", "my", "me", "we", "you",
})


def _extract_query_tokens(query: str) -> set[str]:
    """Extract lowercase tokens from query for structural matching.

    Strips common stop words and short tokens (< 3 chars).
    No NLP, no lemmatization — pure split + filter.
    """
    return {
        w.lower() for w in query.split()
        if len(w) >= 3 and w.lower() not in _STOP_WORDS
    }


def _atom_signals(atom: dict[str, Any]) -> set[str]:
    """Collect signal set from atom_id components.

    NOTE: behavioral_tags was a v1 LLM artifact — intentionally removed
    from the v2 schema. Structural matching now uses atom_id components only.
    """
    signals: set[str] = set()
    atom_id = atom.get("atom_id", "")
    parts = atom_id.replace("::", "_").replace("-", "_").split("_")
    for p in parts:
        if len(p) >= 3:
            signals.add(p.lower())
    return signals


def _structural_match(atom: dict[str, Any], query_tokens: set[str]) -> bool:
    """Check if atom structurally matches the query.

    Matches against atom_id components. At least 1 token must match
    (conservative threshold for short queries).

    This is NOT intent guessing — it's set intersection on observable tokens.
    """
    if not query_tokens:
        return True  # no tokens = no constraint
    return bool(_atom_signals(atom) & query_tokens)


def _cluster_key(atom: dict[str, Any], query_tokens: set[str]) -> frozenset[str]:
    """Compute cluster key = intersection(atom_tags, query_tokens).

    Used for cluster consistency: primary items should come from
    the same semantic cluster to prevent attention splitting.
    """
    return frozenset(_atom_signals(atom) & query_tokens)


def _build_secondary_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    """Build type summary for secondary atoms.

    Infers type from atom_id prefix (cat::, sym::, pit::, qra::).
    Secondary is background context — AI should not prioritize it.
    Only count per type, no payloads, no individual atoms.
    """
    type_counts: dict[str, int] = {}
    for r in results:
        atom_id = r.get("atom_id", "")
        if atom_id.startswith("cat::"):
            t = "category"
        elif atom_id.startswith("sym::"):
            t = "symbol"
        elif atom_id.startswith("pit::"):
            t = "pitfall"
        elif atom_id.startswith("qra::"):
            t = "qra"
        else:
            t = "unknown"
        type_counts[t] = type_counts.get(t, 0) + 1
    return type_counts


class CQETools:
    """CQE Tools - Query engine and analysis"""

    def __init__(
        self,
        workspace_root: Path,
        db_pool: Optional[asyncpg.Pool] = None
    ):
        self.workspace_root = workspace_root
        self.db_pool = db_pool
        self.cqe_index_path = workspace_root / '.quro_context' / 'cqe_index.db'

        # Telemetry writer (per-atom decision observation)
        from quro_sovereign.cqe_telemetry import TelemetryWriter
        telemetry_path = self.workspace_root / ".quro_context" / "cqe_telemetry.jsonl"
        self._telemetry_writer = TelemetryWriter(telemetry_path)

        # LocalRouter — pure gate: local vs remote based on path_mi + vocab overlap
        # Appends to router_log.jsonl; RouterMIBridge (daemon) tails it for MI training
        from quro_sovereign.local_router import LocalRouter
        self._local_router = LocalRouter(project_root=self.workspace_root)

        # Phase hysteresis for intent-level stability (prevents flip-flopping)
        from quro_sovereign.routing_types import PhaseHysteresis
        self._hysteresis = PhaseHysteresis()

    # ------------------------------------------------------------------
    # Capability metadata — structural guidance for AI consumers
    # ------------------------------------------------------------------

    def _get_total_atoms(self) -> int:
        """Count total atoms in CQE index (mtime-cached).

        Cache is invalidated when cqe_index.db file modification time changes.
        This avoids repeated COUNT(*) on a diagnostic field while keeping
        the number accurate across index rebuilds.
        """
        index_file = Path(self.cqe_index_path)
        if not index_file.exists():
            return 0

        current_mtime = index_file.stat().st_mtime
        cached = getattr(self, '_total_atoms_cache', None)
        cached_mtime = getattr(self, '_total_atoms_mtime', None)

        if cached is not None and cached_mtime == current_mtime:
            return cached

        try:
            import sqlite3
            conn = sqlite3.connect(str(index_file))
            count = conn.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]
            conn.close()
            self._total_atoms_cache = count
            self._total_atoms_mtime = current_mtime
            return count
        except Exception:
            return cached if cached is not None else 0

    _CATEGORY_INVARIANTS: dict[str, tuple[list[str], str]] = {
        "hash": (
            ["hash", "md5", "sha", "checksum", "fingerprint", "deterministic", "collision"],
            "INVARIANT: Hash functions MUST be deterministic — same input always yields same output. "
            "Non-deterministic hashing in distributed systems causes cache incoherence and "
            "logic divergence across replicas. Use stable hash keys for memoization and caching."
        ),
        "vram_control": (
            ["vram", "loadModel", "unloadModel", "useModel", "GPU", "memory", "model"],
            "INVARIANT: VRAM is a finite, exclusive resource. Model loading MUST be serialized "
            "via LlmGuard to prevent VramConflictError. Release model from VRAM immediately after "
            "inference. Re-entrant acquisition is allowed (same PID, same model)."
        ),
        "io_bound": (
            ["read", "write", "network", "disk", "http", "fetch", "stream", "buffer"],
            "INVARIANT: I/O-bound operations MUST be async to avoid blocking the event loop. "
            "Synchronous I/O in async contexts causes throughput collapse. Always use await "
            "for file/network operations. Use streaming for large payloads."
        ),
        "signal": (
            ["SIGINT", "SIGTERM", "process.on", "signal", "handler", "cleanup", "exit"],
            "INVARIANT: Signal handlers MUST be async-safe and non-blocking. Long-running "
            "operations must check for cancellation. Use graceful shutdown: save state → "
            "release resources → exit. Never perform I/O in signal context."
        ),
        "atomic": (
            ["atomic", "lock", "mutex", "CAS", "compare_and_swap", "race_condition", "thread"],
            "INVARIANT: Shared mutable state MUST be protected by atomic operations or locks. "
            "Unprotected concurrent access causes data races. Use asyncio.Lock for async contexts, "
            "threading.Lock for sync. Avoid lock inversion and ensure paired ACQ/REL."
        ),
        "async": (
            ["await", "async", "Promise", "then", "coroutine", "concurrent", "event_loop"],
            "INVARIANT: Async functions MUST always await inner coroutines. Never mix sync "
            "and async without explicit bridging. Async event handlers must not block. Use "
            "asyncio.gather for concurrent operations. Return awaitables, not raw futures."
        ),
        "lock": (
            ["lock", "acquire", "release", "mutex", "RLock", "Semaphore", "critical_section"],
            "INVARIANT: Locks MUST be acquired before accessing shared state and released after. "
            "Use async with for asyncio.Lock (automatic release). Never acquire a lock already "
            "held by the same context (deadlock). Prefer fine-grained locks over global locks."
        ),
        "raii": (
            ["finally", "dispose", "cleanup", "destroy", "context_manager", "exit"],
            "INVARIANT: Resources MUST be released in reverse order of acquisition. Use context "
            "managers (async with) for automatic cleanup. Never suppress exceptions in finally "
            "blocks. RAII prevents resource leaks in both success and failure paths."
        ),
        "memory": (
            ["malloc", "free", "heap", "stack", "allocation", "GC", "leak", "buffer"],
            "INVARIANT: Memory allocations MUST have matching deallocations. Avoid unbounded "
            "growth in data structures. Use weakref for caches. Profile for memory leaks in "
            "long-running processes. Limit buffer sizes for untrusted input."
        ),
        "network": (
            ["http", "tcp", "udp", "socket", "connection", "timeout", "retry", "backoff"],
            "INVARIANT: Network operations MUST handle timeouts and failures gracefully. "
            "Implement exponential backoff for retries. Use connection pooling to avoid "
            "socket exhaustion. Never leave connections open indefinitely."
        ),
        "parse": (
            ["parse", "tokenize", "lex", "grammar", "AST", "regex", "validate"],
            "INVARIANT: Parser input MUST be validated before processing. Reject oversized "
            "input to prevent ReDoS attacks. Use incremental parsing for large inputs. "
            "Report parse errors with line/column context."
        ),
        "security": (
            ["auth", "encrypt", "decrypt", "hash_password", "verify", "token", "session"],
            "INVARIANT: Security-critical operations MUST fail closed (deny by default). "
            "Never log sensitive data. Use constant-time comparison for secrets. Validate "
            "all inputs at system boundaries. Rotate secrets regularly."
        ),
        "error": (
            ["error", "exception", "try", "catch", "throw", "raise", "traceback"],
            "INVARIANT: Error handling MUST be comprehensive at system boundaries. "
            "Never silently swallow exceptions. Log error context for debugging. "
            "Use specific exception types. Fail fast for unrecoverable errors."
        ),
        "database": (
            ["database", "sql", "query", "transaction", "connection", "pool", "orm"],
            "INVARIANT: Database operations MUST use connection pooling. "
            "Always close connections in finally blocks. Use parameterized queries "
            "to prevent SQL injection. Implement retry logic for transient failures."
        ),
        "filesystem": (
            ["file", "path", "read", "write", "directory", "exists", "permission"],
            "INVARIANT: File operations MUST check existence before access. "
            "Use absolute paths to avoid ambiguity. Handle permission errors gracefully. "
            "Close file handles in finally blocks. Validate paths to prevent traversal attacks."
        ),
    }

    def _build_suggestion_catalog(self) -> Dict[str, Any]:
        """Build param-free discovery catalog of available CQE categories.

        Returns all predefined categories with descriptions, risk weights,
        aliases, and atom counts from the CQE index. Also returns top
        dynamic categories discovered by the scanner.
        """
        import json
        import sqlite3

        # Load vocabulary.json for descriptions and aliases
        vocab_path = self.workspace_root / "commons" / "vocabulary.json"
        vocab_tags = {}
        if vocab_path.exists():
            try:
                raw = json.loads(vocab_path.read_text(encoding="utf-8"))
                for tag in raw.get("tags", []):
                    vocab_tags[tag["id"]] = {
                        "description": tag.get("description", ""),
                        "risk_weight": tag.get("risk_weight", 0),
                        "aliases": tag.get("aliases", []),
                    }
            except Exception:
                pass

        # Count atoms per category from CQE index
        atom_counts: Dict[str, int] = {}
        try:
            conn = sqlite3.connect(str(self.cqe_index_path))
            rows = conn.execute(
                "SELECT id FROM atoms WHERE id LIKE 'cat::%'"
            ).fetchall()
            for (atom_id,) in rows:
                tag = atom_id.replace("cat::", "", 1)
                atom_counts[tag] = atom_counts.get(tag, 0) + 1
            conn.close()
        except Exception:
            pass

        # Build predefined categories
        predefined = []
        for tag_id in self._CATEGORY_INVARIANTS:
            vocab = vocab_tags.get(tag_id, {})
            keywords, _ = self._CATEGORY_INVARIANTS[tag_id]
            predefined.append({
                "id": tag_id,
                "entry_token": tag_id,
                "description": vocab.get("description", f"Category: {tag_id}"),
                "risk_weight": vocab.get("risk_weight", 0),
                "aliases": vocab.get("aliases", keywords),
                "atom_count": atom_counts.get(tag_id, 0),
                "example": f"cqe_query(query='problems with {tag_id}', entry_token='{tag_id}')",
            })

        # Dynamic categories: those with atoms but not in predefined set
        dynamic = []
        for tag_id, count in sorted(atom_counts.items(), key=lambda x: -x[1]):
            if tag_id in self._CATEGORY_INVARIANTS:
                continue
            vocab = vocab_tags.get(tag_id, {})
            dynamic.append({
                "id": tag_id,
                "entry_token": tag_id,
                "description": vocab.get("description", f"Auto-discovered category from codebase scanning"),
                "atom_count": count,
                "example": f"cqe_query(query='related to {tag_id}', entry_token='{tag_id}')",
            })
            if len(dynamic) >= 20:
                break

        return {
            "status": "success",
            "mode": "suggest",
            "message": (
                "These are the available category atoms for cqe_query. "
                "Pass one as entry_token to start a semantic traversal. "
                "Predefined categories have design invariants; dynamic categories "
                "were discovered from codebase scanning."
            ),
            "predefined_categories": predefined,
            "dynamic_categories": dynamic,
            "total_categories": len(predefined) + len(dynamic),
            "usage": "cqe_query(query='your question', entry_token='category_name')",
        }

    async def cqe_query(
        self,
        query: str,
        entry_token: Optional[str] = None,
        tau: float = 0.1,
        max_depth: int = 3,
        auto_resolve: bool = True,
        use_semantic_match: bool = True,
        load_bundle: bool = False,
        bundle_top_n: int = 10,
        suggest: bool = False,
    ) -> Dict[str, Any]:
        """CQE query via daemon (fast) or direct (fallback) with automatic token resolution."""
        if suggest:
            return self._build_suggestion_catalog()

        if not entry_token:
            return {
                "status": "error",
                "error": "entry_token is required. Pass suggest=True to discover available categories.",
            }

        original_entry_token = entry_token
        resolution_method = None
        confidence_score = 1.0

        # Auto-resolve token if needed
        if auto_resolve:
            resolved = await self._auto_resolve_token(
                query=query,
                entry_token=entry_token,
                use_semantic_match=use_semantic_match,
            )
            if resolved:
                entry_token = resolved['token']
                resolution_method = resolved['method']
                confidence_score = resolved['confidence']

                logger.info(
                    f"Auto-resolved: '{original_entry_token}' → '{entry_token}' "
                    f"(method: {resolution_method}, confidence: {confidence_score:.2f})"
                )

        try:
            # Try daemon first (fast path)
            result = await query_daemon(
                query=query,
                entry_token=entry_token,
                tau=tau,
                max_depth=max_depth
            )

            # Add resolution info
            if resolution_method:
                result['original_token'] = original_entry_token
                result['resolution_method'] = resolution_method
                result['confidence'] = confidence_score

            # Log token resolution event
            if resolution_method:
                await self._log_token_resolution(
                    query=query,
                    original_token=original_entry_token,
                    resolved_token=entry_token,
                    method=resolution_method,
                    confidence=confidence_score,
                    query_success=True
                )

            return result

        except (FileNotFoundError, ConnectionRefusedError, OSError, asyncio.IncompleteReadError) as exc:
            # Daemon not running or socket corrupted — use direct query (slow path)
            logger.warning("CQE daemon unavailable (%s), using direct query", type(exc).__name__)
            result = await self._direct_cqe_query(query, entry_token, tau, max_depth)

            # Add resolution info
            if resolution_method:
                result['original_token'] = original_entry_token
                result['resolution_method'] = resolution_method
                result['confidence'] = confidence_score

            # Log token resolution event
            if resolution_method:
                await self._log_token_resolution(
                    query=query,
                    original_token=original_entry_token,
                    resolved_token=entry_token,
                    method=resolution_method,
                    confidence=confidence_score,
                    query_success=(result.get('status') == 'success')
                )

            return result

    async def _auto_resolve_token(
        self,
        query: str,
        entry_token: str,
        use_semantic_match: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Automatically resolve entry token using multiple strategies

        Strategy cascade:
        1. Exact match → return None (no resolution needed)
        2. Fuzzy match (Levenshtein distance < 3)
        3. Semantic category match (0.6B model embedding similarity)
        4. Similar atoms (SIMILAR edges)

        Args:
            query: Query text
            entry_token: Original entry token
            use_semantic_match: Enable semantic matching with 0.6B model

        Returns:
            {
                "token": str,
                "method": str,
                "confidence": float
            }
            or None if exact match found
        """
        from quro_sovereign.cqe_index_loader import CQEIndexLoader

        if not self.cqe_index_path.exists():
            return None

        loader = CQEIndexLoader(self.cqe_index_path)

        # Step 1: Exact match
        try:
            k_cat = loader.load_k_category(entry_token, set(), max_atoms=10)
            # If we got here, exact match exists
            return None
        except Exception:
            pass

        # Step 2: Fuzzy match
        fuzzy_result = await self._fuzzy_match_token(loader, entry_token)
        if fuzzy_result:
            return fuzzy_result

        # Step 3: Semantic category match
        if use_semantic_match:
            semantic_result = await self._semantic_match_category(query, entry_token)
            if semantic_result:
                return semantic_result

        # Step 4: Similar atoms (via SIMILAR edges)
        similar_result = await self._similar_atom_match(loader, entry_token)
        if similar_result:
            return similar_result

        # No resolution found
        return None

    async def _fuzzy_match_token(
        self,
        loader,
        entry_token: str,
        max_distance: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Fuzzy match using Levenshtein distance

        Args:
            loader: CQE index loader
            entry_token: Token to match
            max_distance: Maximum edit distance

        Returns:
            Resolution dict or None
        """
        import asyncio

        def compute_distance(s1: str, s2: str) -> int:
            """Levenshtein distance"""
            if len(s1) < len(s2):
                return compute_distance(s2, s1)

            if len(s2) == 0:
                return len(s1)

            previous_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row

            return previous_row[-1]

        # Get category atoms via direct SQLite query instead of loading a full k-category
        # (the old approach hardcoded 'async' as an anchor which is fragile)
        import sqlite3
        db_path = self.cqe_index_path
        if not db_path.exists():
            return None
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT id FROM atoms WHERE id LIKE 'cat::%'",
            ).fetchall()
            all_tokens = [row[0] for row in rows]
        finally:
            conn.close()

        # Extract token names (remove prefixes)
        token_names = []
        for token in all_tokens:
            if '::' in token:
                name = token.split('::')[-1]
            else:
                name = token
            token_names.append((token, name))

        # Find closest match
        best_match = None
        best_distance = max_distance + 1

        for full_token, name in token_names:
            distance = compute_distance(entry_token.lower(), name.lower())
            if distance < best_distance:
                best_distance = distance
                best_match = full_token

        if best_match and best_distance < max_distance:
            confidence = 1.0 - (best_distance / max_distance)
            return {
                'token': best_match,
                'method': 'fuzzy',
                'confidence': confidence
            }

        return None

    async def _semantic_match_category(
        self,
        query: str,
        entry_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Semantic category match using 0.6B model embeddings

        Args:
            query: Query text
            entry_token: Original token (used for logging)

        Returns:
            Resolution dict or None
        """
        try:
            from quro_sovereign.category_embedding_matcher import CategoryEmbeddingMatcher

            matcher = CategoryEmbeddingMatcher(self.cqe_index_path)
            await matcher.load_or_compute_embeddings()

            # Find top categories
            top_categories = await matcher.find_top_categories(
                query=query,
                top_k=3,
                min_similarity=0.65
            )

            if top_categories:
                category_id, similarity = top_categories[0]
                return {
                    'token': category_id,
                    'method': 'semantic_category',
                    'confidence': similarity
                }

        except Exception as e:
            logger.warning(f"Semantic matching failed: {e}")

        return None

    async def _similar_atom_match(
        self,
        loader,
        entry_token: str,
        threshold: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """
        Match via SIMILAR edges (MinHash LSH)

        Args:
            loader: CQE index loader
            entry_token: Token to match
            threshold: Minimum similarity threshold

        Returns:
            Resolution dict or None
        """
        # This would require querying SIMILAR edges from the index
        # For now, return None (can be implemented later)
        return None

    async def _log_token_resolution(
        self,
        query: str,
        original_token: str,
        resolved_token: str,
        method: str,
        confidence: float,
        query_success: bool
    ):
        """
        Log token resolution event to reflection log

        This data will be used for MI training to improve token resolution.

        Args:
            query: Query text
            original_token: Original entry token
            resolved_token: Resolved entry token
            method: Resolution method (fuzzy, semantic_category, similar_atom)
            confidence: Confidence score [0, 1]
            query_success: Whether the query succeeded after resolution
        """
        from datetime import datetime
        import json

        reflection_log = self.workspace_root / '.quro_context' / 'cqe_reflections.jsonl'

        entry = {
            'event': 'token_resolved',
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'original_token': original_token,
            'resolved_token': resolved_token,
            'resolution_method': method,
            'confidence': confidence,
            'query_success': query_success
        }

        # Append to reflection log
        with open(reflection_log, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        logger.info(f"Logged token resolution: {original_token} → {resolved_token}")

    async def _direct_cqe_query(
        self,
        query: str,
        entry_token: str,
        tau: float,
        max_depth: int
    ) -> Dict[str, Any]:
        """Direct CQE query (fallback when daemon not available)"""
        from quro_sovereign.cqe_index_loader import CQEIndexLoader

        if not self.cqe_index_path.exists():
            return {
                "status": "error",
                "error": "CQE index not found. Run 'quro cqe-build' first.",
            }

        # Cold-start bypass: if no MI history, set tau=0
        reflection_log = self.workspace_root / '.quro_context' / 'cqe_reflections.jsonl'
        if not reflection_log.exists() or reflection_log.stat().st_size == 0:
            logger.info("Cold-start detected: bypassing MI-gate (tau=0)")
            tau = 0.0

        # Load index
        loader = CQEIndexLoader(self.cqe_index_path)

        # Use CQE v2 kernel (deterministic Dijkstra)
        from quro_sovereign.cqe_v2 import CQEKernel, CanonicalLayer

        graph = loader.as_graph_protocol()
        symbol_table = loader.get_symbol_table()
        aliases = loader.get_aliases()

        canonical_layer = CanonicalLayer(
            symbol_table=symbol_table,
            aliases=aliases,
            max_edit_distance=1
        )

        # Canonicalize entry token
        canon = canonical_layer.resolve(entry_token)
        if canon.status == "not_found":
            return {
                "status": "error",
                "error": f"Entry token not found: {entry_token}",
                "query": query,
                "entry": entry_token,
                "result": [],
                "exec": {"v": 0},
            }
        if canon.status == "ambiguous":
            return {
                "status": "ambiguous",
                "candidates": canon.candidates,
                "query": query,
                "entry": entry_token,
                "result": [],
                "exec": {"v": 0},
            }

        canonical_entry = canon.token

        # Run CQEKernel
        kernel_result = CQEKernel.query(graph, canonical_entry, tau=tau)

        # Build results
        sorted_atoms = sorted(
            kernel_result.max_weights.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:50]

        result = [
            {"id": atom_id, "w": round(weight, 6)}
            for atom_id, weight in sorted_atoms
            if atom_id != canonical_entry
        ]

        return {
            "status": "success",
            "query": query,
            "entry": canonical_entry,
            "result": result,
            "exec": {"v": len(kernel_result.max_weights)},
        }

    async def cqe_load_index(self, index_path: str) -> Dict[str, Any]:
        """
        Load CQE index

        Args:
            index_path: Path to CQE index database

        Returns:
            {"status": "success", "stats": {...}}
        """
        from quro_sovereign.cqe_index_loader import CQEIndexLoader

        index_path_obj = Path(index_path)
        if not index_path_obj.exists():
            return {
                "status": "error",
                "error": f"Index not found: {index_path}"
            }

        loader = CQEIndexLoader(index_path_obj)
        stats = loader.get_index_stats()

        return {
            "status": "success",
            "index_path": str(index_path),
            "stats": stats
        }

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
            entry_atom: Filter by atom id (e.g., 'cat::async')
            limit: Maximum records (default: 20)
            mi_summary: Include per-atom payload_rate table (default: false)

        Returns:
            {"status": "success", "reflections": [...]}
        """
        reflection_log = self.workspace_root / '.quro_context' / 'cqe_reflections.jsonl'

        if not reflection_log.exists():
            return {
                "status": "error",
                "error": "Reflection log not found"
            }

        import json

        reflections = []
        with open(reflection_log, 'r') as f:
            for line in f:
                entry = json.loads(line)

                # Apply filters
                if query_id and entry.get('query_id') != query_id:
                    continue
                if entry_atom and entry.get('atom_id') != entry_atom:
                    continue

                reflections.append(entry)

                if len(reflections) >= limit:
                    break

        # MI summary
        mi_stats = {}
        if mi_summary:
            atom_stats = {}
            for entry in reflections:
                atom_id = entry.get('atom_id')
                if atom_id:
                    if atom_id not in atom_stats:
                        atom_stats[atom_id] = {
                            'total_queries': 0,
                            'payloads_delivered': 0
                        }
                    atom_stats[atom_id]['total_queries'] += 1
                    if entry.get('payload_delivered'):
                        atom_stats[atom_id]['payloads_delivered'] += 1

            # Calculate payload rate
            for atom_id, stats in atom_stats.items():
                mi_stats[atom_id] = {
                    'payload_rate': stats['payloads_delivered'] / stats['total_queries'],
                    'sample_count': stats['total_queries']
                }

        return {
            "status": "success",
            "reflections": reflections,
            "mi_summary": mi_stats if mi_summary else None
        }

    async def cqe_diagnose(
        self,
        query_id: str,
    ) -> Dict[str, Any]:
        """Diagnose a specific CQE query by ID.

        Correlates reflection log + telemetry to produce an actionable
        diagnostic report.  Designed for Quro developers debugging
        query quality — not for AI consumers.

        Args:
            query_id: The query_id from a cqe_query response (e.g. "cqe::1776125874201")

        Returns:
            Diagnostic report with traversal stats, semantic voids,
            delivery efficiency, and per-atom telemetry breakdown.
        """
        import json

        reflection_log = self.workspace_root / '.quro_context' / 'cqe_reflections.jsonl'
        telemetry_log = self.workspace_root / '.quro_context' / 'cqe_telemetry.jsonl'

        if not reflection_log.exists():
            return {"status": "error", "error": "Reflection log not found"}

        # --- Stage 1: Load reflection record for this query_id ---
        reflection = None
        with open(reflection_log, 'r', encoding='utf-8') as f:
            for line in f:
                entry = json.loads(line)
                if entry.get('query_id') == query_id:
                    reflection = entry
                    break

        if not reflection:
            return {
                "status": "error",
                "error": f"No reflection found for query_id: {query_id}",
                "hint": "query_id must match exactly. Check cqe_query response for the correct ID.",
            }

        # --- Stage 2: Extract traversal data from reflection ---
        atoms_built = reflection.get('atoms_built', [])
        path_mi = reflection.get('path_mi', 0)
        payload_rate = reflection.get('payload_rate', 0)
        entry_atom = reflection.get('entry_atom', 'unknown')
        morphisms_built = reflection.get('morphisms_built', len(atoms_built))

        # Classify atoms by type
        categories = [a for a in atoms_built if a.startswith('cat::')]
        symbols = [a for a in atoms_built if a.startswith('sym::')]
        pitfalls = [a for a in atoms_built if a.startswith('pit::')]
        qras = [a for a in atoms_built if a.startswith('qra::')]
        other = [a for a in atoms_built if not any(a.startswith(p) for p in ('cat::', 'sym::', 'pit::', 'qra::'))]

        # --- Stage 3: Semantic voids ---
        # Categories that were traversed but produced no symbol descendants
        symbol_atom_ids = set(symbols)
        void_categories = []
        for cat in categories:
            cat_tag = cat.replace('cat::', '', 1)
            # Check if any symbol references this category in its tags
            has_symbol = any(cat_tag in s for s in symbols)
            if not has_symbol:
                void_categories.append(cat)

        # --- Stage 4: Load telemetry for this query_id ---
        telemetry_by_atom: Dict[str, list[Dict[str, Any]]] = {}
        if telemetry_log.exists():
            with open(telemetry_log, 'r', encoding='utf-8') as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get('query_id') == query_id:
                        atom_id = entry.get('atom', '')
                        if atom_id:
                            telemetry_by_atom.setdefault(atom_id, []).append(entry)

        # --- Stage 5: Delivery breakdown from telemetry ---
        delivery_counts = {'primary': 0, 'secondary': 0, 'drop': 0, 'ranked': 0, 'unknown': 0}
        rule_counts: Dict[str, int] = {}
        for events in telemetry_by_atom.values():
            for ev in events:
                if ev.get('stage') == 'delivery':
                    decision = ev.get('decision', 'unknown')
                    delivery_counts[decision] = delivery_counts.get(decision, 0) + 1
                    rule_id = ev.get('rule_id', '')
                    if rule_id:
                        rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1

        # --- Stage 6: Build diagnostic report ---
        diagnosis: Dict[str, Any] = {
            "status": "success",
            "query_id": query_id,
            "entry_atom": entry_atom,
            "traversal": {
                "atoms_built": len(atoms_built),
                "categories": len(categories),
                "symbols": len(symbols),
                "pitfalls": len(pitfalls),
                "qras": len(qras),
                "other": len(other),
                "path_mi": path_mi,
                "payload_rate": round(payload_rate, 4) if payload_rate else 0,
            },
            "delivery": {
                "primary": delivery_counts.get('primary', 0),
                "secondary": delivery_counts.get('secondary', 0),
                "drop": delivery_counts.get('drop', 0),
                "rules_applied": rule_counts if rule_counts else None,
            },
            "semantic_voids": void_categories if void_categories else None,
            "atom_breakdown": {
                "categories": categories[:20],
                "symbols": symbols[:20],
                "pitfalls": pitfalls[:20],
            },
        }

        # Truncate long lists
        if len(categories) > 20:
            diagnosis["atom_breakdown"]["categories_truncated"] = len(categories) - 20
        if len(symbols) > 20:
            diagnosis["atom_breakdown"]["symbols_truncated"] = len(symbols) - 20
        if len(pitfalls) > 20:
            diagnosis["atom_breakdown"]["pitfalls_truncated"] = len(pitfalls) - 20

        return diagnosis

    async def cqe_train_mi(
        self,
        reflection_log_path: str,
        iters: int = 100,
        adapter_path: Optional[str] = None,
        batch_size: int = 4,
        learning_rate: float = 1e-5,
        lora_rank: int = 8,
        lora_alpha: int = 16
    ) -> Dict[str, Any]:
        """
        Train MI estimator with incremental training support

        Args:
            reflection_log_path: Path to reflection log
            iters: Number of training iterations (default: 100)
            adapter_path: Path to existing LoRA adapters for incremental training (optional)
            batch_size: Batch size (default: 4)
            learning_rate: Learning rate (default: 1e-5)
            lora_rank: LoRA rank (default: 8)
            lora_alpha: LoRA alpha (default: 16)

        Returns:
            {
                "status": "success",
                "adapter_path": str,
                "metrics": {
                    "accuracy": float,
                    "loss": float,
                    "training_time": float
                }
            }
        """
        from pathlib import Path
        import asyncio

        reflection_log = Path(reflection_log_path)

        if not reflection_log.exists():
            return {
                "status": "error",
                "error": f"Reflection log not found: {reflection_log_path}"
            }

        # Check if CQE index exists
        index_path = self.workspace_root / '.quro_context' / 'cqe_index.db'
        if not index_path.exists():
            return {
                "status": "error",
                "error": "CQE index not found. Run 'quro cqe-build' first."
            }

        try:
            # Step 1: Extract training pairs
            logger.info("Step 1/3: Extracting training pairs from reflection log...")
            from quro_sovereign.mi_path_extractor import MIPathExtractor

            extractor = MIPathExtractor(
                reflection_log_path=reflection_log,
                index_path=index_path
            )

            train_pairs, val_pairs = await asyncio.to_thread(
                extractor.extract_all,
                min_quality=0.6,
                contrastive_ratio=0.3
            )

            if len(train_pairs) == 0:
                return {
                    "status": "error",
                    "error": "No training pairs extracted. Need more reflection log data."
                }

            logger.info(f"Extracted {len(train_pairs)} training pairs, {len(val_pairs)} validation pairs")

            # Save training pairs
            train_jsonl = self.workspace_root / '.quro_context' / 'training_pairs.jsonl'
            val_jsonl = self.workspace_root / '.quro_context' / 'training_pairs_val.jsonl'

            extractor.save_jsonl(train_pairs, train_jsonl)
            extractor.save_jsonl(val_pairs, val_jsonl)

            # Step 2: Initialize trainer
            logger.info("Step 2/3: Initializing MLX trainer...")
            from quro_sovereign.mi_model_trainer import MIModelTrainer

            base_model = '.models/Qwen/Qwen3-0.6B-MLX-4bit'
            output_dir = self.workspace_root / '.quro_context' / 'mi_model'

            trainer = MIModelTrainer(
                base_model_path=base_model,
                output_dir=output_dir
            )

            # Load existing adapters for incremental training
            if adapter_path:
                adapter_path_obj = Path(adapter_path)
                if adapter_path_obj.exists():
                    logger.info(f"Loading existing adapters for incremental training: {adapter_path}")
                    await asyncio.to_thread(trainer.load_trained_model, adapter_path_obj)
                else:
                    logger.warning(f"Adapter path not found: {adapter_path}, starting from scratch")

            # Step 3: Train model
            logger.info("Step 3/3: Training MI model with LoRA...")
            metrics = await asyncio.to_thread(
                trainer.train,
                train_jsonl=train_jsonl,
                val_jsonl=val_jsonl,
                iters=iters,
                batch_size=batch_size,
                learning_rate=learning_rate,
                lora_rank=lora_rank,
                lora_alpha=lora_alpha
            )

            logger.info(f"Training complete! Accuracy: {metrics['eval_results']['accuracy']:.4f}")

            return {
                "status": "success",
                "adapter_path": str(trainer.adapter_path),
                "metrics": {
                    "accuracy": metrics['eval_results']['accuracy'],
                    "loss": metrics['eval_results']['loss'],
                    "training_time": metrics['training_time'],
                    "train_samples": len(train_pairs),
                    "val_samples": len(val_pairs)
                },
                "config": {
                    "iters": iters,
                    "batch_size": batch_size,
                    "learning_rate": learning_rate,
                    "lora_rank": lora_rank,
                    "lora_alpha": lora_alpha,
                    "incremental": adapter_path is not None
                }
            }

        except ImportError as e:
            return {
                "status": "error",
                "error": f"Missing dependency: {e}. Install with: pip install mlx-lm"
            }
        except Exception as e:
            logger.error(f"MI training failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def cqe_get_mi_stats(
        self,
        atom_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get MI statistics from reflection log

        Args:
            atom_id: Filter by atom id (e.g., 'cat::async')

        Returns:
            {
                "status": "success",
                "stats": {
                    "total_queries": int,
                    "atoms_with_data": int,
                    "avg_payload_rate": float,
                    "per_atom": {
                        "atom_id": {
                            "payload_rate": float,
                            "sample_count": int
                        }
                    }
                }
            }
        """
        reflection_log = self.workspace_root / '.quro_context' / 'cqe_reflections.jsonl'

        if not reflection_log.exists():
            return {
                "status": "error",
                "error": "Reflection log not found. Run some CQE queries first."
            }

        import json

        # Aggregate stats by atom
        atom_stats = {}
        total_queries = 0

        with open(reflection_log, 'r') as f:
            for line in f:
                entry = json.loads(line)
                atoms = entry.get('path_taken', [])
                payload_fps = entry.get('payload_fps', [])
                has_payload = len(payload_fps) > 0

                if not atoms:
                    continue

                total_queries += 1

                # Aggregate stats for each atom in the path
                for atom in atoms:
                    # Filter by atom_id if specified
                    if atom_id and atom != atom_id:
                        continue

                    if atom not in atom_stats:
                        atom_stats[atom] = {
                            'total_queries': 0,
                            'payloads_delivered': 0
                        }

                    atom_stats[atom]['total_queries'] += 1
                    if has_payload:
                        atom_stats[atom]['payloads_delivered'] += 1

        # Calculate payload rates
        per_atom_stats = {}
        total_payload_rate = 0.0

        for atom, stats in atom_stats.items():
            payload_rate = stats['payloads_delivered'] / stats['total_queries']
            per_atom_stats[atom] = {
                'payload_rate': payload_rate,
                'sample_count': stats['total_queries']
            }
            total_payload_rate += payload_rate

        avg_payload_rate = total_payload_rate / len(atom_stats) if atom_stats else 0.0

        return {
            "status": "success",
            "stats": {
                "total_queries": total_queries,
                "atoms_with_data": len(atom_stats),
                "avg_payload_rate": avg_payload_rate,
                "per_atom": per_atom_stats
            }
        }

"""
Morphism Registry - PostgreSQL CRUD operations

Provides operations for:
- File morphisms (symbols, imports, exports)
- Symbol metadata (role, intent, tags, LSH signatures)
- Dependencies (cross-file references)
- LSH indexing for semantic search
"""
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


@dataclass
class SymbolMetadata:
    """Symbol metadata structure"""
    uid: str
    file_path: str
    role: str
    tags: List[str]
    lsh_signature: bytes
    confidence: float
    file_fidelity: Optional[float] = None


class MorphismRegistry:
    """PostgreSQL-backed registry for symbol metadata and morphisms"""

    def __init__(self, db_manager):
        """
        Initialize registry

        Args:
            db_manager: DatabaseManager instance
        """
        self.db_manager = db_manager

    # === File Operations ===

    async def get_or_create_file(self, file_path: str, language: str, content_hash: str) -> str:
        """
        Get or create file record

        Args:
            file_path: Relative file path
            language: Programming language
            content_hash: SHA256 hash of file content

        Returns:
            File UUID
        """
        async with self.db_manager.session() as conn:
            # Try to get existing file
            row = await conn.fetchrow(
                "SELECT id FROM files WHERE file_path = $1",
                file_path
            )

            if row:
                # Update hash and timestamp
                await conn.execute(
                    """
                    UPDATE files
                    SET content_hash = $1, last_indexed_at = NOW(), updated_at = NOW()
                    WHERE file_path = $2
                    """,
                    content_hash, file_path
                )
                return row['id']

            # Create new file
            file_id = await conn.fetchval(
                """
                INSERT INTO files (file_path, language, content_hash)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                file_path, language, content_hash
            )
            return file_id

    async def get_file_fingerprint(self, file_path: str) -> Optional[str]:
        """
        Get fingerprint for a file

        Args:
            file_path: Relative file path

        Returns:
            Fingerprint string or None if file not found
        """
        async with self.db_manager.session() as conn:
            row = await conn.fetchrow(
                "SELECT fingerprint FROM files WHERE file_path = $1",
                file_path
            )
            return row['fingerprint'] if row else None

    async def get_file_morphism(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file morphism data (symbols, imports, exports)

        Args:
            file_path: Relative file path

        Returns:
            Morphism data or None
        """
        async with self.db_manager.session() as conn:
            # Get file
            file_row = await conn.fetchrow(
                "SELECT id, fingerprint, fidelity FROM files WHERE file_path = $1",
                file_path
            )

            if not file_row:
                return None

            file_id = file_row['id']

            # Get symbols
            symbol_rows = await conn.fetch(
                """
                SELECT name, kind, line, col, signature, docstring, role, intent, behavioral_tags
                FROM symbols
                WHERE file_id = $1
                ORDER BY line, col
                """,
                file_id
            )

            symbols = [
                {
                    "name": row['name'],
                    "kind": row['kind'],
                    "line": row['line'],
                    "col": row['col'],
                    "signature": row['signature'],
                    "docstring": row['docstring'],
                    "role": row['role'],
                    "intent": row['intent'],
                    "behavioral_tags": row['behavioral_tags'] or []
                }
                for row in symbol_rows
            ]

            # Get imports
            import_rows = await conn.fetch(
                """
                SELECT source_module, imported_names, alias, line
                FROM imports
                WHERE file_id = $1
                ORDER BY line
                """,
                file_id
            )

            imports = [
                {
                    "source": row['source_module'],
                    "names": row['imported_names'],
                    "alias": row['alias'],
                    "line": row['line']
                }
                for row in import_rows
            ]

            # Get exports
            export_rows = await conn.fetch(
                """
                SELECT e.export_name, e.is_default, s.symbol_name as symbol_name
                FROM exports e
                LEFT JOIN symbols s ON e.symbol_id = s.id
                WHERE e.file_id = $1
                """,
                file_id
            )

            exports = [
                {
                    "name": row['export_name'],
                    "is_default": row['is_default'],
                    "symbol": row['symbol_name']
                }
                for row in export_rows
            ]

            return {
                "file_path": file_path,
                "fingerprint": file_row['fingerprint'],
                "fidelity": file_row['fidelity'],
                "symbols": symbols,
                "imports": imports,
                "exports": exports
            }

    async def save_file_morphism(
        self,
        file_path: str,
        language: str,
        content_hash: str,
        morphism_data: Dict[str, Any],
        fingerprint: Optional[str] = None,
        fidelity: float = 1.0
    ) -> None:
        """
        Save file morphism data to registry

        Args:
            file_path: Relative file path
            language: Programming language
            content_hash: SHA256 hash of file content
            morphism_data: Dictionary with symbols, imports, exports
            fingerprint: SHA256(source + normalized_imports) — semantic fingerprint
            fidelity: Method coverage ratio (methods_found / total_methods)
        """
        async with self.db_manager.transaction() as conn:
            # Get or create file
            file_id = await conn.fetchval(
                """
                INSERT INTO files (file_path, language, content_hash, fingerprint, fidelity)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (file_path) DO UPDATE
                SET content_hash = EXCLUDED.content_hash,
                    fingerprint = EXCLUDED.fingerprint,
                    fidelity = EXCLUDED.fidelity,
                    updated_at = NOW()
                RETURNING id
                """,
                file_path, language, content_hash, fingerprint, fidelity
            )

            # Soft-delete existing symbols (RESTRICT FK prevents hard DELETE)
            await conn.execute(
                "UPDATE symbols SET deprecated_at = NOW() WHERE file_id = $1 AND deprecated_at IS NULL",
                file_id
            )

            # Insert symbols
            for symbol in morphism_data.get('symbols', []):
                # Map morphism_data fields to actual DB schema
                symbol_name = symbol.get('name', 'unknown')
                symbol_type = symbol.get('kind', 'function')
                canonical_uid = f"{file_path}::{symbol_name}"
                content_hash_val = content_hash  # Use file's content hash

                # Convert tags list to JSON
                import json
                tags_json = json.dumps(symbol.get('behavioral_tags', []))

                await conn.execute(
                    """
                    INSERT INTO symbols (
                        canonical_uid, file_id, symbol_name, symbol_type,
                        content_hash, canonical_hash, role, intent, tags, confidence
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (file_id, symbol_name) DO UPDATE SET
                        symbol_type = EXCLUDED.symbol_type,
                        content_hash = EXCLUDED.content_hash,
                        canonical_hash = EXCLUDED.canonical_hash,
                        role = EXCLUDED.role,
                        intent = EXCLUDED.intent,
                        tags = EXCLUDED.tags,
                        confidence = EXCLUDED.confidence,
                        deprecated_at = NULL,
                        scan_completed = False,
                        updated_at = NOW()
                    """,
                    canonical_uid,
                    file_id,
                    symbol_name,
                    symbol_type,
                    content_hash_val,
                    content_hash_val,  # canonical_hash = content_hash for now
                    symbol.get('role'),
                    symbol.get('intent'),
                    tags_json,
                    1.0  # confidence
                )

            # Skip imports/exports during dual-write (tables may not exist)
            # Will be enabled when full schema migration completes

    # === Symbol Operations ===

    async def get_symbol(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """
        Get symbol by name

        Args:
            symbol_name: Symbol name

        Returns:
            Symbol data or None
        """
        async with self.db_manager.session() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    s.id, s.symbol_name AS name, s.symbol_type AS kind, s.role, s.intent,
                    s.tags AS behavioral_tags, s.minhash_signature AS lsh_signature,
                    f.file_path, f.language
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.symbol_name = $1
                LIMIT 1
                """,
                symbol_name
            )

            if not row:
                return None

            return {
                "id": row['id'],
                "name": row['name'],
                "kind": row['kind'],
                "role": row['role'],
                "intent": row['intent'],
                "behavioral_tags": row['behavioral_tags'] or [],
                "lsh_signature": row['lsh_signature'],
                "file_path": row['file_path'],
                "language": row['language'],
                # Fields from dual-write schema (not in old schema.sql, but in actual DB)
                "canonical_uid": row.get('canonical_uid'),
                "content_hash": row.get('content_hash'),
                "canonical_hash": row.get('canonical_hash'),
                "confidence": row.get('confidence', 1.0),
            }

    async def update_symbol_lsh(
        self,
        symbol_id: str,
        lsh_signature: bytes,
        behavioral_tags: List[str],
        band_hashes: List[int]
    ) -> None:
        """
        Update symbol LSH signature and tags.

        Args:
            symbol_id: Symbol UUID
            lsh_signature: MinHash signature as bytes
            behavioral_tags: List of behavioral tags (stored in 'tags' JSONB column)
            band_hashes: List of band hashes (NOT stored — lsh_bands table doesn't exist yet)
        """
        import json

        async with self.db_manager.transaction() as conn:
            # Update symbol (uses actual DB column names: minhash_signature, tags)
            # Note: band_hashes are ignored for now — lsh_bands table doesn't exist in dual-write schema
            await conn.execute(
                """
                UPDATE symbols
                SET minhash_signature = $1, tags = $2, updated_at = NOW()
                WHERE id = $3
                """,
                lsh_signature, json.dumps(behavioral_tags), symbol_id
            )

    # === Dependency Operations ===

    async def add_dependency(
        self,
        from_symbol_id: str,
        to_symbol_id: str,
        dependency_type: str,
        line: Optional[int] = None
    ) -> None:
        """
        Add dependency between symbols

        Args:
            from_symbol_id: Source symbol UUID
            to_symbol_id: Target symbol UUID
            dependency_type: Type of dependency ('calls', 'imports', 'inherits', 'uses')
            line: Line number where dependency occurs
        """
        async with self.db_manager.session() as conn:
            await conn.execute(
                """
                INSERT INTO dependencies (from_symbol_id, to_symbol_id, dependency_type, line)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (from_symbol_id, to_symbol_id, dependency_type) DO NOTHING
                """,
                from_symbol_id, to_symbol_id, dependency_type, line
            )

    async def get_dependencies(
        self,
        symbol_id: str,
        direction: str = "outgoing"
    ) -> List[Dict[str, Any]]:
        """
        Get symbol dependencies

        Args:
            symbol_id: Symbol UUID
            direction: "outgoing" (what this symbol depends on) or "incoming" (what depends on this)

        Returns:
            List of dependency records
        """
        async with self.db_manager.session() as conn:
            if direction == "outgoing":
                query = """
                    SELECT
                        d.dependency_type, d.line,
                        s.name as target_name, s.symbol_type as target_kind,
                        f.file_path as target_file
                    FROM dependencies d
                    JOIN symbols s ON d.to_symbol_id = s.id
                    JOIN files f ON s.file_id = f.id
                    WHERE d.from_symbol_id = $1
                """
            else:  # incoming
                query = """
                    SELECT
                        d.dependency_type, d.line,
                        s.name as source_name, s.symbol_type as source_kind,
                        f.file_path as source_file
                    FROM dependencies d
                    JOIN symbols s ON d.from_symbol_id = s.id
                    JOIN files f ON s.file_id = f.id
                    WHERE d.to_symbol_id = $1
                """

            rows = await conn.fetch(query, symbol_id)

            return [
                {
                    "type": row['dependency_type'],
                    "line": row['line'],
                    "symbol": row.get('target_name') or row.get('source_name'),
                    "kind": row.get('target_kind') or row.get('source_kind'),
                    "file": row.get('target_file') or row.get('source_file')
                }
                for row in rows
            ]

    # === Workspace Operations ===

    async def record_workspace_scan(
        self,
        scan_type: str,
        files_scanned: int,
        symbols_found: int,
        dependencies_mapped: int,
        duration_ms: int
    ) -> str:
        """
        Record workspace scan metadata.

        Args:
            scan_type: "full" or "incremental"
            files_scanned: Number of files scanned
            symbols_found: Number of symbols found
            dependencies_mapped: Number of dependencies mapped
            duration_ms: Scan duration in milliseconds

        Returns:
            Scan UUID (dummy ID — workspace_scans table doesn't exist in dual-write schema)
        """
        # NOTE: workspace_scans table doesn't exist in dual-write schema phase
        # Return a dummy scan ID to maintain API contract
        return f"scan-{int(datetime.now().timestamp() * 1000)}"

    # === Dependencies ===

    async def get_dependencies_for_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Get dependencies for a file"""
        async with self.db_manager.session() as conn:
            rows = await conn.fetch("""
                SELECT to_uid AS target_path, edge_type
                FROM dependency_edges
                WHERE from_uid = $1
            """, file_path)

            return [
                {
                    "targetPath": row['target_path'],
                    "symbols": [],
                    "isTypeOnly": row['edge_type'] == 'type_import',
                    "weight": 1
                }
                for row in rows
            ]

    async def save_dependencies(
        self,
        source_path: str,
        dependencies: List[Dict[str, Any]]
    ):
        """Save dependencies for a file"""
        async with self.db_manager.transaction() as conn:
            # Delete existing dependencies
            await conn.execute(
                "DELETE FROM dependency_edges WHERE from_uid = $1",
                source_path
            )

            # Insert new dependencies
            for dep in dependencies:
                edge_type = 'type_import' if dep.get('isTypeOnly') else 'import'
                await conn.execute("""
                    INSERT INTO dependency_edges (from_uid, to_uid, edge_type)
                    VALUES ($1, $2, $3)
                """, source_path, dep['targetPath'], edge_type)

    async def find_callers(self, target_path: str, symbol: str) -> List[Dict[str, Any]]:
        """Find callers of a symbol"""
        async with self.db_manager.session() as conn:
            rows = await conn.fetch("""
                SELECT from_uid AS path, edge_type
                FROM dependency_edges
                WHERE to_uid = $1
            """, target_path)

            return [
                {
                    "path": row['path'],
                    "isTypeOnly": row['edge_type'] == 'type_import'
                }
                for row in rows
            ]

    async def find_collisions(self, lsh: str) -> List[str]:
        """Find files with matching LSH signature"""
        async with self.db_manager.session() as conn:
            rows = await conn.fetch("""
                SELECT uid FROM file_morphisms
                WHERE metadata->>'lsh_signature' = $1
            """, lsh)
            return [row['uid'] for row in rows]

    # === Task Queue ===

    async def add_task(self, task_type: str, payload: Dict[str, Any]) -> int:
        """Add task to queue"""
        async with self.db_manager.session() as conn:
            row = await conn.fetchrow("""
                INSERT INTO task_queue (task_type, status, payload_json, created_at)
                VALUES ($1, 'PENDING', $2, $3)
                RETURNING id
            """, task_type, json.dumps(payload), int(datetime.now().timestamp() * 1000))
            return row['id']

    async def succeed_task(self, task_id: int):
        """Mark task as succeeded"""
        async with self.db_manager.session() as conn:
            await conn.execute("""
                UPDATE task_queue
                SET status = 'SUCCESS', completed_at = $1
                WHERE id = $2
            """, int(datetime.now().timestamp() * 1000), task_id)

    async def fail_task(self, task_id: int, error: str):
        """Mark task as failed"""
        async with self.db_manager.session() as conn:
            await conn.execute("""
                UPDATE task_queue
                SET status = 'FAILED',
                    completed_at = $1,
                    payload_json = payload_json || jsonb_build_object('error', $2::text)
                WHERE id = $3
            """, int(datetime.now().timestamp() * 1000), error, task_id)

    async def get_pending_task_count(self, task_type: Optional[str] = None) -> int:
        """Get count of pending tasks"""
        async with self.db_manager.session() as conn:
            if task_type:
                row = await conn.fetchrow("""
                    SELECT COUNT(*) AS count FROM task_queue
                    WHERE status = 'PENDING' AND task_type = $1
                """, task_type)
            else:
                row = await conn.fetchrow("""
                    SELECT COUNT(*) AS count FROM task_queue
                    WHERE status = 'PENDING'
                """)
            return row['count']

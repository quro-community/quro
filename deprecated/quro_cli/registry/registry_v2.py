"""
RegistryV2: V2 schema write layer.

@module quro_cli.registry.registry_v2
@intent Write symbols and morphism edges to V2 (files/symbols) schema.
         V1 (symbol_metadata) writes removed — all readers migrated to V2.
"""

import asyncpg
import hashlib
import json
from typing import Dict, List, Optional, Any
from datetime import datetime


class RegistryV2:
    """V2 schema write layer."""

    def __init__(self, db_pool: asyncpg.Pool, enable_v2_write: bool = True):
        self.db_pool = db_pool
        self.enable_v2_write = enable_v2_write
        self._morphism_type_cache: Dict[str, int] = {}

    async def setup(self):
        """Initialize morphism type cache."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, type_name FROM morphism_types")
            self._morphism_type_cache = {row['type_name']: row['id'] for row in rows}

    def _compute_canonical_uid(self, file_path: str, symbol_name: str) -> str:
        """
        Compute deterministic canonical UID.
        Format: namespace::type::hash
        """
        # Extract namespace from file path
        namespace = file_path.replace('/', '.').replace('.py', '').replace('.ts', '')

        # Compute stable hash
        content = f"{namespace}::{symbol_name}"
        hash_hex = hashlib.sha256(content.encode()).hexdigest()[:16]

        return f"sym::{namespace}::{symbol_name}::{hash_hex}"

    def _compute_canonical_hash(self, file_path: str, symbol_name: str) -> str:
        """
        Compute canonical hash (stable across file moves).
        Hash of (namespace + name).
        """
        namespace = file_path.replace('/', '.').replace('.py', '').replace('.ts', '')
        content = f"{namespace}::{symbol_name}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def _get_or_create_file(
        self,
        conn: asyncpg.Connection,
        file_path: str,
        language: Optional[str] = None,
        fingerprint: Optional[str] = None,
        fidelity: float = 1.0,
        contract_status: str = "INCOMPLETE",
    ) -> int:
        """Get or create file record, return file_id.

        Always upserts fingerprint, fidelity, and contract_status.
        """
        # Infer language from extension
        if language is None:
            if file_path.endswith('.py'):
                language = 'python'
            elif file_path.endswith(('.ts', '.tsx')):
                language = 'typescript'
            elif file_path.endswith(('.js', '.jsx')):
                language = 'javascript'

        # Upsert: INSERT or UPDATE on conflict
        row = await conn.fetchrow("""
            INSERT INTO files (file_path, language, fingerprint, fidelity, contract_status, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (file_path) DO UPDATE SET fingerprint = EXCLUDED.fingerprint, fidelity = EXCLUDED.fidelity, contract_status = EXCLUDED.contract_status, updated_at = $6
            RETURNING id
        """, file_path, language, fingerprint, fidelity, contract_status, datetime.utcnow())

        return row['id']

    async def insert_symbol(
        self,
        file_path: str,
        symbol_name: str,
        symbol_type: str = 'function',
        role: Optional[str] = None,
        intent: Optional[str] = None,
        tags: Optional[List[str]] = None,
        confidence: float = 0.8,
        scan_completed: bool = False,
        lsh_signature: Optional[str] = None,
        signature: Optional[str] = None,
        fingerprint: Optional[str] = None,
        fidelity: float = 1.0,
        contract_status: str = "INCOMPLETE",
        **metadata
    ) -> Dict[str, Any]:
        """
        Write symbol to V2 schema.

        Returns:
            {
                'v2_id': int,
                'canonical_uid': str
            }
        """
        # Truncate large fields to prevent JSONB overflow (268MB limit)
        MAX_FIELD_LENGTH = 10000  # 10KB per field, safe limit
        MAX_TAGS = 100  # Hard cap on tag count

        # Validate and cap tags to prevent corruption from reaching DB
        if tags is None:
            tags = []
        if not isinstance(tags, list):
            logger.warning(
                "insert_symbol: tags is %s (expected list), resetting to [] for %s::%s",
                type(tags).__name__, file_path, symbol_name,
            )
            tags = []
        if len(tags) > MAX_TAGS:
            logger.warning(
                "insert_symbol: tags count %d exceeds MAX_TAGS=%d, truncating for %s::%s",
                len(tags), MAX_TAGS, file_path, symbol_name,
            )
            tags = tags[:MAX_TAGS]

        if intent and len(intent) > MAX_FIELD_LENGTH:
            intent = intent[:MAX_FIELD_LENGTH] + "... [truncated]"

        if role and len(role) > MAX_FIELD_LENGTH:
            role = role[:MAX_FIELD_LENGTH] + "... [truncated]"

        if signature and len(signature) > MAX_FIELD_LENGTH:
            signature = signature[:MAX_FIELD_LENGTH] + "... [truncated]"

        async with self.db_pool.acquire() as conn:
            v2_id = None
            canonical_uid = None

            if self.enable_v2_write:
                file_id = await self._get_or_create_file(
                    conn, file_path,
                    fingerprint=fingerprint,
                    fidelity=fidelity,
                    contract_status=contract_status,
                )
                canonical_uid = self._compute_canonical_uid(file_path, symbol_name)
                canonical_hash = self._compute_canonical_hash(file_path, symbol_name)
                content_hash = hashlib.sha256(f"{file_path}::{symbol_name}::{role}::{intent}".encode()).hexdigest()[:16]

                row = await conn.fetchrow("""
                    INSERT INTO symbols (
                        canonical_uid, file_id, symbol_name, symbol_type,
                        content_hash, canonical_hash,
                        role, intent, tags, confidence,
                        scan_completed,
                        scanned_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    ON CONFLICT (file_id, symbol_name) DO UPDATE SET
                        canonical_uid = $1,
                        content_hash = $5,
                        canonical_hash = $6,
                        role = $7,
                        intent = $8,
                        tags = $9,
                        confidence = $10,
                        scan_completed = $11,
                        scanned_at = $12,
                        updated_at = $13
                    RETURNING id
                """, canonical_uid, file_id, symbol_name, symbol_type,
                    content_hash, canonical_hash,
                    role, intent, json.dumps(tags or []), confidence,
                    scan_completed,
                    datetime.utcnow(), datetime.utcnow())

                v2_id = row['id']

            return {
                'v2_id': v2_id,
                'canonical_uid': canonical_uid
            }

    async def insert_morphism(
        self,
        from_symbol_name: str,
        to_symbol_name: str,
        morphism_type: str = 'CALLS',
        weight: float = 0.8,
        metadata: Optional[Dict] = None
    ) -> Optional[int]:
        """
        Insert morphism edge in V2 schema.

        Args:
            from_symbol_name: Source symbol name (will be resolved to symbol_id)
            to_symbol_name: Target symbol name (will be resolved to symbol_id)
            morphism_type: Type name from morphism_types table
            weight: Edge weight [0, 1]
            metadata: Optional JSON metadata

        Returns:
            morphism_edge.id or None if V2 disabled
        """
        if not self.enable_v2_write:
            return None

        async with self.db_pool.acquire() as conn:
            # Resolve symbol names to IDs
            from_row = await conn.fetchrow("""
                SELECT id FROM symbols
                WHERE symbol_name = $1
                AND deprecated_at IS NULL
                ORDER BY confidence DESC
                LIMIT 1
            """, from_symbol_name)

            to_row = await conn.fetchrow("""
                SELECT id FROM symbols
                WHERE symbol_name = $1
                AND deprecated_at IS NULL
                ORDER BY confidence DESC
                LIMIT 1
            """, to_symbol_name)

            if not from_row or not to_row:
                return None

            # Get morphism type ID
            morphism_type_id = self._morphism_type_cache.get(morphism_type)
            if not morphism_type_id:
                type_row = await conn.fetchrow("""
                    SELECT id FROM morphism_types WHERE type_name = $1
                """, morphism_type)
                if type_row:
                    morphism_type_id = type_row['id']
                    self._morphism_type_cache[morphism_type] = morphism_type_id
                else:
                    return None

            # Insert edge
            row = await conn.fetchrow("""
                INSERT INTO morphism_edges (
                    from_symbol_id, to_symbol_id, morphism_type_id,
                    weight, metadata, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (from_symbol_id, to_symbol_id, morphism_type_id)
                DO UPDATE SET weight = $4, metadata = $5, updated_at = $6
                RETURNING id
            """, from_row['id'], to_row['id'], morphism_type_id,
                weight, json.dumps(metadata or {}), datetime.utcnow())

            return row['id']

    async def get_symbol_by_name(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Get symbol from V2 schema by name."""
        if not self.enable_v2_write:
            return None

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT s.id, s.canonical_uid, s.symbol_name, s.symbol_type,
                       s.role, s.intent, s.tags, s.confidence,
                       f.file_path, f.language
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.symbol_name = $1
                AND s.deprecated_at IS NULL
                ORDER BY s.confidence DESC
                LIMIT 1
            """, symbol_name)

            if not row:
                return None

            return {
                'id': row['id'],
                'canonical_uid': row['canonical_uid'],
                'symbol_name': row['symbol_name'],
                'symbol_type': row['symbol_type'],
                'role': row['role'],
                'intent': row['intent'],
                'tags': json.loads(row['tags']) if row['tags'] else [],
                'confidence': row['confidence'],
                'file_path': row['file_path'],
                'language': row['language']
            }

    async def build_reverse_index(self) -> Dict[str, List[str]]:
        """
        Build reverse index: bare_name → [canonical_uids].
        Critical for CQE morphism resolution.
        """
        if not self.enable_v2_write:
            return {}

        reverse_index = {}

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT symbol_name, canonical_uid
                FROM symbols
                WHERE deprecated_at IS NULL
            """)

            for row in rows:
                symbol_name = row['symbol_name']
                canonical_uid = row['canonical_uid']

                if symbol_name not in reverse_index:
                    reverse_index[symbol_name] = []
                reverse_index[symbol_name].append(canonical_uid)

        return reverse_index

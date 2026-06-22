"""PostgreSQL Registry Adapter - Concrete implementation.

@module quro.adapters.registry.postgres
@intent Implement RegistryAdapter protocol for PostgreSQL database.
"""

import asyncpg
import hashlib
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from .types import (
    FileRecord,
    SymbolRecord,
    MorphismRecord,
    SymbolInsertRequest,
    MorphismInsertRequest,
    SymbolMetadata,
)


class PostgresRegistry:
    """PostgreSQL implementation of RegistryAdapter.

    Implements V2 schema operations with frozen dataclasses.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self._morphism_type_cache: Dict[str, int] = {}

    async def setup(self) -> None:
        """Initialize morphism type cache."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, type_name FROM morphism_types")
            self._morphism_type_cache = {row['type_name']: row['id'] for row in rows}

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _compute_canonical_uid(self, file_path: str, symbol_name: str) -> str:
        """Compute deterministic canonical UID.

        Format: sym::namespace::symbol_name::hash
        """
        namespace = file_path.replace('/', '.').replace('.py', '').replace('.ts', '')
        content = f"{namespace}::{symbol_name}"
        hash_hex = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"sym::{namespace}::{symbol_name}::{hash_hex}"

    def _compute_canonical_hash(self, file_path: str, symbol_name: str) -> str:
        """Compute canonical hash (stable across file moves)."""
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
        contract_status: str = "INCOMPLETE"
    ) -> int:
        """Get or create file record, return file_id."""
        # Infer language from extension
        if language is None:
            if file_path.endswith('.py'):
                language = 'python'
            elif file_path.endswith(('.ts', '.tsx')):
                language = 'typescript'
            elif file_path.endswith(('.js', '.jsx')):
                language = 'javascript'
            else:
                language = 'unknown'

        # Upsert file
        row = await conn.fetchrow("""
            INSERT INTO files (file_path, language, fingerprint, fidelity, contract_status, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (file_path) DO UPDATE SET
                fingerprint = EXCLUDED.fingerprint,
                fidelity = EXCLUDED.fidelity,
                contract_status = EXCLUDED.contract_status,
                updated_at = $6
            RETURNING id
        """, file_path, language, fingerprint, fidelity, contract_status, datetime.utcnow())

        return row['id']

    # ------------------------------------------------------------------
    # Symbol operations
    # ------------------------------------------------------------------

    async def insert_symbol(
        self,
        request: SymbolInsertRequest
    ) -> SymbolRecord:
        """Insert or update symbol in registry."""
        # Truncate large fields to prevent JSONB overflow
        MAX_FIELD_LENGTH = 10000
        MAX_TAGS = 100

        role = request.role
        intent = request.intent
        tags = list(request.tags) if request.tags else []

        # Validate and cap tags
        if len(tags) > MAX_TAGS:
            tags = tags[:MAX_TAGS]

        if intent and len(intent) > MAX_FIELD_LENGTH:
            intent = intent[:MAX_FIELD_LENGTH] + "... [truncated]"

        if role and len(role) > MAX_FIELD_LENGTH:
            role = role[:MAX_FIELD_LENGTH] + "... [truncated]"

        async with self.db_pool.acquire() as conn:
            # Get or create file
            file_id = await self._get_or_create_file(
                conn,
                request.file_path,
                fingerprint=request.fingerprint,
                fidelity=request.fidelity,
                contract_status=request.contract_status
            )

            # Compute UIDs
            canonical_uid = self._compute_canonical_uid(request.file_path, request.symbol_name)
            canonical_hash = self._compute_canonical_hash(request.file_path, request.symbol_name)
            content_hash = hashlib.sha256(
                f"{request.file_path}::{request.symbol_name}::{role}::{intent}".encode()
            ).hexdigest()[:16]

            # Derive semantic metadata if not provided
            node_type = request.node_type
            is_container = request.is_container
            is_executor = request.is_executor

            if node_type is None:
                metadata = SymbolMetadata.from_symbol_kind(request.symbol_type)
                node_type = metadata.node_type
                is_container = metadata.is_container
                is_executor = metadata.is_executor

            # Upsert symbol
            row = await conn.fetchrow("""
                INSERT INTO symbols (
                    canonical_uid, file_id, symbol_name, symbol_type,
                    content_hash, canonical_hash,
                    role, intent, tags, confidence,
                    scan_completed,
                    node_type, is_container, is_executor,
                    scanned_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                ON CONFLICT (file_id, symbol_name) DO UPDATE SET
                    canonical_uid = $1,
                    content_hash = $5,
                    canonical_hash = $6,
                    role = $7,
                    intent = $8,
                    tags = $9,
                    confidence = $10,
                    scan_completed = $11,
                    node_type = $12,
                    is_container = $13,
                    is_executor = $14,
                    scanned_at = $15,
                    updated_at = $16
                RETURNING id, canonical_uid, content_hash, canonical_hash, scanned_at, updated_at
            """, canonical_uid, file_id, request.symbol_name, request.symbol_type,
                content_hash, canonical_hash,
                role, intent, json.dumps(tags), request.confidence,
                request.scan_completed,
                node_type, is_container, is_executor,
                datetime.utcnow(), datetime.utcnow())

            # Get file info for language
            file_row = await conn.fetchrow("SELECT language FROM files WHERE id = $1", file_id)

            return SymbolRecord(
                id=row['id'],
                canonical_uid=row['canonical_uid'],
                file_id=file_id,
                file_path=request.file_path,
                symbol_name=request.symbol_name,
                symbol_type=request.symbol_type,
                content_hash=row['content_hash'],
                canonical_hash=row['canonical_hash'],
                role=role,
                intent=intent,
                tags=tuple(tags),
                confidence=request.confidence,
                scan_completed=request.scan_completed,
                language=file_row['language'] if file_row else None,
                scanned_at=row['scanned_at'],
                updated_at=row['updated_at'],
                node_type=node_type,
                is_container=is_container,
                is_executor=is_executor
            )

    async def get_symbol_by_name(
        self,
        symbol_name: str
    ) -> Optional[SymbolRecord]:
        """Get symbol by name (highest confidence)."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT s.id, s.canonical_uid, s.file_id, s.symbol_name, s.symbol_type,
                       s.content_hash, s.canonical_hash,
                       s.role, s.intent, s.tags, s.confidence,
                       s.scan_completed, s.scanned_at, s.updated_at,
                       s.node_type, s.is_container, s.is_executor,
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

            return SymbolRecord(
                id=row['id'],
                canonical_uid=row['canonical_uid'],
                file_id=row['file_id'],
                file_path=row['file_path'],
                symbol_name=row['symbol_name'],
                symbol_type=row['symbol_type'],
                content_hash=row['content_hash'],
                canonical_hash=row['canonical_hash'],
                role=row['role'],
                intent=row['intent'],
                tags=tuple(json.loads(row['tags'])) if row['tags'] else (),
                confidence=row['confidence'],
                scan_completed=row['scan_completed'],
                language=row['language'],
                scanned_at=row['scanned_at'],
                updated_at=row['updated_at'],
                node_type=row.get('node_type'),
                is_container=row.get('is_container'),
                is_executor=row.get('is_executor')
            )

    async def get_symbol_by_uid(
        self,
        canonical_uid: str
    ) -> Optional[SymbolRecord]:
        """Get symbol by canonical UID."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT s.id, s.canonical_uid, s.file_id, s.symbol_name, s.symbol_type,
                       s.content_hash, s.canonical_hash,
                       s.role, s.intent, s.tags, s.confidence,
                       s.scan_completed, s.scanned_at, s.updated_at,
                       s.node_type, s.is_container, s.is_executor,
                       f.file_path, f.language
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.canonical_uid = $1
                AND s.deprecated_at IS NULL
            """, canonical_uid)

            if not row:
                return None

            return SymbolRecord(
                id=row['id'],
                canonical_uid=row['canonical_uid'],
                file_id=row['file_id'],
                file_path=row['file_path'],
                symbol_name=row['symbol_name'],
                symbol_type=row['symbol_type'],
                content_hash=row['content_hash'],
                canonical_hash=row['canonical_hash'],
                role=row['role'],
                intent=row['intent'],
                tags=tuple(json.loads(row['tags'])) if row['tags'] else (),
                confidence=row['confidence'],
                scan_completed=row['scan_completed'],
                language=row['language'],
                scanned_at=row['scanned_at'],
                updated_at=row['updated_at'],
                node_type=row.get('node_type'),
                is_container=row.get('is_container'),
                is_executor=row.get('is_executor')
            )

    async def query_symbols(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[SymbolRecord]:
        """Query symbols with filters."""
        # Build WHERE clause from filters
        conditions = []
        params = []
        param_idx = 1

        if 'language' in filters:
            conditions.append(f"f.language = ${param_idx}")
            params.append(filters['language'])
            param_idx += 1

        if 'symbol_type' in filters:
            conditions.append(f"s.symbol_type = ${param_idx}")
            params.append(filters['symbol_type'])
            param_idx += 1

        if 'file_path' in filters:
            conditions.append(f"f.file_path = ${param_idx}")
            params.append(filters['file_path'])
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT s.id, s.canonical_uid, s.file_id, s.symbol_name, s.symbol_type,
                       s.content_hash, s.canonical_hash,
                       s.role, s.intent, s.tags, s.confidence,
                       s.scan_completed, s.scanned_at, s.updated_at,
                       s.node_type, s.is_container, s.is_executor,
                       f.file_path, f.language
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE {where_clause}
                AND s.deprecated_at IS NULL
                ORDER BY s.confidence DESC
                LIMIT ${param_idx}
            """, *params, limit)

            return [
                SymbolRecord(
                    id=row['id'],
                    canonical_uid=row['canonical_uid'],
                    file_id=row['file_id'],
                    file_path=row['file_path'],
                    symbol_name=row['symbol_name'],
                    symbol_type=row['symbol_type'],
                    content_hash=row['content_hash'],
                    canonical_hash=row['canonical_hash'],
                    role=row['role'],
                    intent=row['intent'],
                    tags=tuple(json.loads(row['tags'])) if row['tags'] else (),
                    confidence=row['confidence'],
                    scan_completed=row['scan_completed'],
                    language=row['language'],
                    scanned_at=row['scanned_at'],
                    updated_at=row['updated_at'],
                    node_type=row.get('node_type'),
                    is_container=row.get('is_container'),
                    is_executor=row.get('is_executor')
                )
                for row in rows
            ]

    # ------------------------------------------------------------------
    # Morphism operations
    # ------------------------------------------------------------------

    async def insert_morphism(
        self,
        request: MorphismInsertRequest
    ) -> Optional[MorphismRecord]:
        """Insert or update morphism edge."""
        async with self.db_pool.acquire() as conn:
            # Resolve symbol names to IDs
            from_row = await conn.fetchrow("""
                SELECT id FROM symbols
                WHERE symbol_name = $1
                AND deprecated_at IS NULL
                ORDER BY confidence DESC
                LIMIT 1
            """, request.from_symbol_name)

            to_row = await conn.fetchrow("""
                SELECT id FROM symbols
                WHERE symbol_name = $1
                AND deprecated_at IS NULL
                ORDER BY confidence DESC
                LIMIT 1
            """, request.to_symbol_name)

            if not from_row or not to_row:
                return None

            # Get morphism type ID
            morphism_type_id = self._morphism_type_cache.get(request.morphism_type)
            if not morphism_type_id:
                type_row = await conn.fetchrow("""
                    SELECT id FROM morphism_types WHERE type_name = $1
                """, request.morphism_type)
                if type_row:
                    morphism_type_id = type_row['id']
                    self._morphism_type_cache[request.morphism_type] = morphism_type_id
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
                RETURNING id, updated_at
            """, from_row['id'], to_row['id'], morphism_type_id,
                request.weight, json.dumps(request.metadata or {}), datetime.utcnow())

            return MorphismRecord(
                id=row['id'],
                from_symbol_id=from_row['id'],
                to_symbol_id=to_row['id'],
                morphism_type=request.morphism_type,
                weight=request.weight,
                metadata=request.metadata or {},
                updated_at=row['updated_at']
            )

    async def get_morphisms_from(
        self,
        symbol_name: str,
        morphism_type: Optional[str] = None
    ) -> List[MorphismRecord]:
        """Get outgoing morphisms from symbol."""
        async with self.db_pool.acquire() as conn:
            # Get symbol ID
            symbol_row = await conn.fetchrow("""
                SELECT id FROM symbols
                WHERE symbol_name = $1
                AND deprecated_at IS NULL
                ORDER BY confidence DESC
                LIMIT 1
            """, symbol_name)

            if not symbol_row:
                return []

            # Build query
            if morphism_type:
                morphism_type_id = self._morphism_type_cache.get(morphism_type)
                if not morphism_type_id:
                    return []

                rows = await conn.fetch("""
                    SELECT me.id, me.from_symbol_id, me.to_symbol_id,
                           mt.type_name, me.weight, me.metadata, me.updated_at
                    FROM morphism_edges me
                    JOIN morphism_types mt ON me.morphism_type_id = mt.id
                    WHERE me.from_symbol_id = $1
                    AND me.morphism_type_id = $2
                """, symbol_row['id'], morphism_type_id)
            else:
                rows = await conn.fetch("""
                    SELECT me.id, me.from_symbol_id, me.to_symbol_id,
                           mt.type_name, me.weight, me.metadata, me.updated_at
                    FROM morphism_edges me
                    JOIN morphism_types mt ON me.morphism_type_id = mt.id
                    WHERE me.from_symbol_id = $1
                """, symbol_row['id'])

            return [
                MorphismRecord(
                    id=row['id'],
                    from_symbol_id=row['from_symbol_id'],
                    to_symbol_id=row['to_symbol_id'],
                    morphism_type=row['type_name'],
                    weight=row['weight'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    updated_at=row['updated_at']
                )
                for row in rows
            ]

    async def get_morphisms_to(
        self,
        symbol_name: str,
        morphism_type: Optional[str] = None
    ) -> List[MorphismRecord]:
        """Get incoming morphisms to symbol."""
        async with self.db_pool.acquire() as conn:
            # Get symbol ID
            symbol_row = await conn.fetchrow("""
                SELECT id FROM symbols
                WHERE symbol_name = $1
                AND deprecated_at IS NULL
                ORDER BY confidence DESC
                LIMIT 1
            """, symbol_name)

            if not symbol_row:
                return []

            # Build query
            if morphism_type:
                morphism_type_id = self._morphism_type_cache.get(morphism_type)
                if not morphism_type_id:
                    return []

                rows = await conn.fetch("""
                    SELECT me.id, me.from_symbol_id, me.to_symbol_id,
                           mt.type_name, me.weight, me.metadata, me.updated_at
                    FROM morphism_edges me
                    JOIN morphism_types mt ON me.morphism_type_id = mt.id
                    WHERE me.to_symbol_id = $1
                    AND me.morphism_type_id = $2
                """, symbol_row['id'], morphism_type_id)
            else:
                rows = await conn.fetch("""
                    SELECT me.id, me.from_symbol_id, me.to_symbol_id,
                           mt.type_name, me.weight, me.metadata, me.updated_at
                    FROM morphism_edges me
                    JOIN morphism_types mt ON me.morphism_type_id = mt.id
                    WHERE me.to_symbol_id = $1
                """, symbol_row['id'])

            return [
                MorphismRecord(
                    id=row['id'],
                    from_symbol_id=row['from_symbol_id'],
                    to_symbol_id=row['to_symbol_id'],
                    morphism_type=row['type_name'],
                    weight=row['weight'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    updated_at=row['updated_at']
                )
                for row in rows
            ]

    async def build_reverse_index(self) -> Dict[str, List[str]]:
        """Build reverse index: bare_name → [canonical_uids]."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT symbol_name, canonical_uid
                FROM symbols
                WHERE deprecated_at IS NULL
                ORDER BY symbol_name, confidence DESC
            """)

            reverse_index: Dict[str, List[str]] = {}
            for row in rows:
                bare_name = row['symbol_name']
                canonical_uid = row['canonical_uid']

                if bare_name not in reverse_index:
                    reverse_index[bare_name] = []

                reverse_index[bare_name].append(canonical_uid)

            return reverse_index

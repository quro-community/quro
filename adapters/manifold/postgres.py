"""Manifold Adapter - PostgreSQL implementation.

@module quro.adapters.manifold.postgres
@intent PostgreSQL implementation of ManifoldAdapter protocol.
"""

import json
import time
import asyncpg
from typing import Optional, List
from .types import ManifoldNode, NodeInsertRequest
from .protocol import ManifoldAdapter


class PostgresManifold:
    """PostgreSQL implementation of ManifoldAdapter.

    Converts between v2 database schema (dict) and v3 frozen dataclasses.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        """Initialize with asyncpg connection pool.

        Args:
            db_pool: asyncpg connection pool
        """
        self.db_pool = db_pool

    async def setup(self) -> None:
        """Initialize database schema."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS manifold_nodes (
                    symbol_uid       TEXT PRIMARY KEY,
                    lsh_bands        TEXT NOT NULL,
                    manifold_x       DOUBLE PRECISION DEFAULT 0.0,
                    manifold_y       DOUBLE PRECISION DEFAULT 0.0,
                    behavioral_tags  TEXT,
                    last_convergence TEXT,
                    updated_at       DOUBLE PRECISION NOT NULL
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mn_updated ON manifold_nodes(updated_at)"
            )

    async def upsert_node(
        self,
        request: NodeInsertRequest
    ) -> ManifoldNode:
        """Insert or update manifold node.

        Args:
            request: Node insert request (frozen dataclass)

        Returns:
            ManifoldNode with current state
        """
        async with self.db_pool.acquire() as conn:
            updated_at = time.time()

            await conn.execute("""
                INSERT INTO manifold_nodes (
                    symbol_uid, lsh_bands, manifold_x, manifold_y,
                    behavioral_tags, last_convergence, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (symbol_uid) DO UPDATE SET
                    lsh_bands = EXCLUDED.lsh_bands,
                    manifold_x = EXCLUDED.manifold_x,
                    manifold_y = EXCLUDED.manifold_y,
                    behavioral_tags = EXCLUDED.behavioral_tags,
                    last_convergence = EXCLUDED.last_convergence,
                    updated_at = EXCLUDED.updated_at
            """,
                request.symbol_uid,
                json.dumps(list(request.lsh_bands)),
                request.manifold_x,
                request.manifold_y,
                json.dumps(list(request.behavioral_tags)),
                request.last_convergence,
                updated_at
            )

            return ManifoldNode(
                symbol_uid=request.symbol_uid,
                lsh_bands=request.lsh_bands,
                manifold_x=request.manifold_x,
                manifold_y=request.manifold_y,
                behavioral_tags=request.behavioral_tags,
                last_convergence=request.last_convergence,
                updated_at=updated_at
            )

    async def get_node(
        self,
        symbol_uid: str
    ) -> Optional[ManifoldNode]:
        """Get manifold node by symbol UID.

        Args:
            symbol_uid: Symbol UID to lookup

        Returns:
            ManifoldNode if found, None otherwise
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM manifold_nodes WHERE symbol_uid = $1",
                symbol_uid
            )

            if not row:
                return None

            return ManifoldNode(
                symbol_uid=row['symbol_uid'],
                lsh_bands=tuple(json.loads(row['lsh_bands'])),
                manifold_x=row['manifold_x'],
                manifold_y=row['manifold_y'],
                behavioral_tags=tuple(json.loads(row['behavioral_tags'])),
                last_convergence=row['last_convergence'],
                updated_at=row['updated_at']
            )

    async def get_all_nodes(self) -> List[ManifoldNode]:
        """Get all manifold nodes.

        Returns:
            List of ManifoldNode (empty if none exist)
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM manifold_nodes")

            return [
                ManifoldNode(
                    symbol_uid=row['symbol_uid'],
                    lsh_bands=tuple(json.loads(row['lsh_bands'])),
                    manifold_x=row['manifold_x'],
                    manifold_y=row['manifold_y'],
                    behavioral_tags=tuple(json.loads(row['behavioral_tags'])),
                    last_convergence=row['last_convergence'],
                    updated_at=row['updated_at']
                )
                for row in rows
            ]

    async def delete_node(self, symbol_uid: str) -> bool:
        """Delete manifold node by symbol UID.

        Args:
            symbol_uid: Symbol UID to delete

        Returns:
            True if deleted, False if not found
        """
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM manifold_nodes WHERE symbol_uid = $1",
                symbol_uid
            )
            # result is like "DELETE 1" or "DELETE 0"
            return result.endswith("1")

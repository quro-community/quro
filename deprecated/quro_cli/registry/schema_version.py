"""
Schema version management for dual-write migration.

@module quro_cli.registry.schema_version
@intent Track schema version and coordinate dual-write mode
"""

import asyncpg
from typing import Optional
from datetime import datetime


class SchemaVersion:
    """Manages schema version and migration state."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def get_current_version(self) -> Optional[str]:
        """Get current schema version from database."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT version, applied_at
                FROM schema_migrations
                ORDER BY applied_at DESC
                LIMIT 1
            """)
            return row['version'] if row else None

    async def is_v2_deployed(self) -> bool:
        """Check if V2 schema is deployed."""
        async with self.db_pool.acquire() as conn:
            # Check if files table exists
            row = await conn.fetchrow("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'files'
                )
            """)
            return row['exists'] if row else False

    async def enable_dual_write(self) -> bool:
        """
        Enable dual-write mode.
        Returns True if V2 schema is ready, False otherwise.
        """
        v2_ready = await self.is_v2_deployed()
        if not v2_ready:
            return False

        # Verify all required tables exist
        async with self.db_pool.acquire() as conn:
            tables = await conn.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('files', 'symbols', 'morphism_types', 'morphism_edges')
            """)

            required_tables = {'files', 'symbols', 'morphism_types', 'morphism_edges'}
            existing_tables = {row['table_name'] for row in tables}

            return required_tables.issubset(existing_tables)

    async def record_migration(self, version: str, description: str):
        """Record a migration in schema_migrations table."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO schema_migrations (version, description, applied_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (version) DO NOTHING
            """, version, description, datetime.utcnow())

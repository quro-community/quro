"""
Database connection and session management for Quro registry.

Provides async database connection pooling and session management using asyncpg.
"""
import os
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
import asyncpg
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL database connections and sessions"""

    def __init__(self, db_url: Optional[str] = None):
        """
        Initialize database manager

        Args:
            db_url: PostgreSQL connection URL (default: from QURO_DB_URL env var)
        """
        self.db_url = db_url or os.getenv(
            "QURO_DB_URL",
            "postgresql://localhost/quro"
        )
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Create database connection pool"""
        if self.pool is not None:
            logger.warning("Database pool already exists")
            return

        try:
            self.pool = await asyncpg.create_pool(
                self.db_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connection pool created")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise

    async def disconnect(self) -> None:
        """Close database connection pool"""
        if self.pool is None:
            return

        try:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")
        except Exception as e:
            logger.error(f"Failed to close database pool: {e}")
            raise

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Get database session (connection) from pool

        Yields:
            Database connection

        Example:
            async with db_manager.session() as conn:
                result = await conn.fetch("SELECT * FROM symbols")
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")

        async with self.pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Get database session with transaction

        Yields:
            Database connection with active transaction

        Example:
            async with db_manager.transaction() as conn:
                await conn.execute("INSERT INTO symbols ...")
                await conn.execute("INSERT INTO dependencies ...")
                # Auto-commits on success, rolls back on exception
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def execute_schema(self, schema_path: str) -> None:
        """
        Execute SQL schema file

        Args:
            schema_path: Path to SQL schema file

        Raises:
            FileNotFoundError: If schema file doesn't exist
            RuntimeError: If database pool not initialized
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")

        # Read schema file
        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        # Execute schema
        async with self.session() as conn:
            await conn.execute(schema_sql)
            logger.info(f"Schema executed from {schema_path}")

    async def health_check(self) -> bool:
        """
        Check database connection health

        Returns:
            True if database is accessible, False otherwise
        """
        if self.pool is None:
            return False

        try:
            async with self.session() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(db_url: Optional[str] = None) -> DatabaseManager:
    """
    Get global database manager instance

    Args:
        db_url: PostgreSQL connection URL (only used on first call)

    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_url)
    return _db_manager


async def init_database(db_url: Optional[str] = None, schema_path: Optional[str] = None) -> DatabaseManager:
    """
    Initialize database connection and optionally execute schema

    Args:
        db_url: PostgreSQL connection URL
        schema_path: Path to SQL schema file (optional)

    Returns:
        DatabaseManager instance
    """
    db_manager = get_db_manager(db_url)
    await db_manager.connect()

    if schema_path:
        await db_manager.execute_schema(schema_path)

    return db_manager


async def close_database() -> None:
    """Close global database connection"""
    global _db_manager
    if _db_manager is not None:
        await _db_manager.disconnect()
        _db_manager = None

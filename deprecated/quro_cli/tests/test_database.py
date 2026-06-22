"""
Tests for database operations and connection management.
"""
import pytest
import os
from quro_cli.registry.database import DatabaseManager, get_db_manager, init_database


@pytest.fixture
async def db_manager():
    """Create test database manager"""
    db_url = os.getenv("QURO_TEST_DB_URL", "postgresql://localhost/quro_test")
    manager = DatabaseManager(db_url)
    await manager.connect()
    yield manager
    await manager.disconnect()


@pytest.mark.asyncio
async def test_database_connection(db_manager):
    """Test database connection"""
    assert db_manager.pool is not None
    health = await db_manager.health_check()
    assert health is True


@pytest.mark.asyncio
async def test_database_session(db_manager):
    """Test database session context manager"""
    async with db_manager.session() as conn:
        result = await conn.fetchval("SELECT 1")
        assert result == 1


@pytest.mark.asyncio
async def test_database_transaction(db_manager):
    """Test database transaction context manager"""
    async with db_manager.transaction() as conn:
        # Create test table
        await conn.execute("""
            CREATE TEMP TABLE test_table (
                id SERIAL PRIMARY KEY,
                value TEXT
            )
        """)

        # Insert data
        await conn.execute("INSERT INTO test_table (value) VALUES ($1)", "test")

        # Query data
        result = await conn.fetchval("SELECT value FROM test_table WHERE id = 1")
        assert result == "test"


@pytest.mark.asyncio
async def test_database_transaction_rollback(db_manager):
    """Test transaction rollback on error"""
    try:
        async with db_manager.transaction() as conn:
            await conn.execute("""
                CREATE TEMP TABLE test_rollback (
                    id SERIAL PRIMARY KEY,
                    value TEXT
                )
            """)

            await conn.execute("INSERT INTO test_rollback (value) VALUES ($1)", "test")

            # Force error
            raise ValueError("Test error")
    except ValueError:
        pass

    # Table should not exist after rollback
    async with db_manager.session() as conn:
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_tables
                WHERE tablename = 'test_rollback'
            )
        """)
        assert result is False


@pytest.mark.asyncio
async def test_get_db_manager():
    """Test global database manager singleton"""
    db_url = os.getenv("QURO_TEST_DB_URL", "postgresql://localhost/quro_test")

    manager1 = get_db_manager(db_url)
    manager2 = get_db_manager()

    assert manager1 is manager2


@pytest.mark.asyncio
async def test_init_database():
    """Test database initialization"""
    db_url = os.getenv("QURO_TEST_DB_URL", "postgresql://localhost/quro_test")

    manager = await init_database(db_url)
    assert manager.pool is not None

    health = await manager.health_check()
    assert health is True

    await manager.disconnect()


@pytest.mark.asyncio
async def test_database_health_check_failure():
    """Test health check with disconnected database"""
    manager = DatabaseManager("postgresql://localhost/nonexistent")

    # Should return False without connection
    health = await manager.health_check()
    assert health is False

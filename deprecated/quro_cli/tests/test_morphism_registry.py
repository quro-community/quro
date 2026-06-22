"""
Tests for morphism registry operations.
"""
import pytest
import os
import hashlib
from quro_cli.registry.database import DatabaseManager
from quro_cli.registry.morphism_registry import MorphismRegistry


@pytest.fixture
async def db_manager():
    """Create test database manager"""
    db_url = os.getenv("QURO_TEST_DB_URL", "postgresql://localhost/quro_test")
    manager = DatabaseManager(db_url)
    await manager.connect()

    # Execute schema
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "registry",
        "schema.sql"
    )
    await manager.execute_schema(schema_path)

    yield manager

    # Cleanup
    async with manager.session() as conn:
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")

    await manager.disconnect()


@pytest.fixture
async def registry(db_manager):
    """Create morphism registry"""
    return MorphismRegistry(db_manager)


@pytest.mark.asyncio
async def test_get_or_create_file(registry):
    """Test file creation and retrieval"""
    file_id = await registry.get_or_create_file(
        "test.py",
        "python",
        "abc123"
    )

    assert file_id is not None

    # Get same file again
    file_id2 = await registry.get_or_create_file(
        "test.py",
        "python",
        "abc123"
    )

    assert file_id == file_id2


@pytest.mark.asyncio
async def test_save_and_get_file_morphism(registry):
    """Test saving and retrieving file morphism"""
    morphism_data = {
        "symbols": [
            {
                "name": "test_function",
                "kind": "function",
                "line": 10,
                "col": 0,
                "signature": "def test_function():",
                "docstring": "Test function",
                "role": "utility",
                "intent": "Testing",
                "behavioral_tags": ["function", "test"]
            }
        ],
        "imports": [
            {
                "source": "os",
                "names": ["path"],
                "line": 1
            }
        ],
        "exports": [
            {
                "name": "test_function",
                "is_default": False,
                "symbol": "test_function"
            }
        ]
    }

    await registry.save_file_morphism(
        "test.py",
        "python",
        "abc123",
        morphism_data
    )

    # Retrieve morphism
    result = await registry.get_file_morphism("test.py")

    assert result is not None
    assert result["file_path"] == "test.py"
    assert len(result["symbols"]) == 1
    assert result["symbols"][0]["name"] == "test_function"
    assert len(result["imports"]) == 1
    assert result["imports"][0]["source"] == "os"
    assert len(result["exports"]) == 1


@pytest.mark.asyncio
async def test_get_symbol(registry):
    """Test symbol retrieval"""
    # First save a file with symbols
    morphism_data = {
        "symbols": [
            {
                "name": "MyClass",
                "kind": "class",
                "line": 5,
                "col": 0,
                "role": "model",
                "intent": "Data model",
                "behavioral_tags": ["class"]
            }
        ],
        "imports": [],
        "exports": []
    }

    await registry.save_file_morphism(
        "models.py",
        "python",
        "def456",
        morphism_data
    )

    # Get symbol
    symbol = await registry.get_symbol("MyClass")

    assert symbol is not None
    assert symbol["name"] == "MyClass"
    assert symbol["kind"] == "class"
    assert symbol["role"] == "model"
    assert symbol["file_path"] == "models.py"


@pytest.mark.asyncio
async def test_update_symbol_lsh(registry):
    """Test updating symbol LSH signature"""
    # Create symbol first
    morphism_data = {
        "symbols": [
            {
                "name": "async_function",
                "kind": "function",
                "line": 10,
                "col": 0,
                "behavioral_tags": []
            }
        ],
        "imports": [],
        "exports": []
    }

    await registry.save_file_morphism(
        "async_utils.py",
        "python",
        "ghi789",
        morphism_data
    )

    # Get symbol ID
    symbol = await registry.get_symbol("async_function")
    symbol_id = symbol["id"]

    # Update LSH
    lsh_signature = b"test_signature_bytes"
    behavioral_tags = ["async", "await", "function"]
    band_hashes = [123, 456, 789]

    await registry.update_symbol_lsh(
        symbol_id,
        lsh_signature,
        behavioral_tags,
        band_hashes
    )

    # Verify update
    updated_symbol = await registry.get_symbol("async_function")
    assert updated_symbol["lsh_signature"] == lsh_signature
    assert updated_symbol["behavioral_tags"] == behavioral_tags


@pytest.mark.asyncio
async def test_add_dependency(registry):
    """Test adding dependencies between symbols"""
    # Create two symbols
    morphism_data = {
        "symbols": [
            {
                "name": "caller",
                "kind": "function",
                "line": 5,
                "col": 0
            },
            {
                "name": "callee",
                "kind": "function",
                "line": 10,
                "col": 0
            }
        ],
        "imports": [],
        "exports": []
    }

    await registry.save_file_morphism(
        "functions.py",
        "python",
        "jkl012",
        morphism_data
    )

    # Get symbol IDs
    caller = await registry.get_symbol("caller")
    callee = await registry.get_symbol("callee")

    # Add dependency
    await registry.add_dependency(
        caller["id"],
        callee["id"],
        "calls",
        line=7
    )

    # Get dependencies
    deps = await registry.get_dependencies(caller["id"], "outgoing")

    assert len(deps) == 1
    assert deps[0]["type"] == "calls"
    assert deps[0]["symbol"] == "callee"
    assert deps[0]["line"] == 7


@pytest.mark.asyncio
async def test_get_dependencies_incoming(registry):
    """Test getting incoming dependencies"""
    # Create symbols and dependency
    morphism_data = {
        "symbols": [
            {
                "name": "source",
                "kind": "function",
                "line": 5,
                "col": 0
            },
            {
                "name": "target",
                "kind": "function",
                "line": 10,
                "col": 0
            }
        ],
        "imports": [],
        "exports": []
    }

    await registry.save_file_morphism(
        "deps.py",
        "python",
        "mno345",
        morphism_data
    )

    source = await registry.get_symbol("source")
    target = await registry.get_symbol("target")

    await registry.add_dependency(
        source["id"],
        target["id"],
        "uses"
    )

    # Get incoming dependencies for target
    deps = await registry.get_dependencies(target["id"], "incoming")

    assert len(deps) == 1
    assert deps[0]["type"] == "uses"
    assert deps[0]["symbol"] == "source"


@pytest.mark.asyncio
async def test_record_workspace_scan(registry):
    """Test recording workspace scan metadata"""
    scan_id = await registry.record_workspace_scan(
        scan_type="full",
        files_scanned=100,
        symbols_found=500,
        dependencies_mapped=200,
        duration_ms=5000
    )

    assert scan_id is not None


@pytest.mark.asyncio
async def test_save_morphism_updates_existing(registry):
    """Test that saving morphism updates existing file"""
    # Save initial morphism
    morphism_data_v1 = {
        "symbols": [
            {
                "name": "old_function",
                "kind": "function",
                "line": 5,
                "col": 0
            }
        ],
        "imports": [],
        "exports": []
    }

    await registry.save_file_morphism(
        "update_test.py",
        "python",
        "hash1",
        morphism_data_v1
    )

    # Update with new morphism
    morphism_data_v2 = {
        "symbols": [
            {
                "name": "new_function",
                "kind": "function",
                "line": 10,
                "col": 0
            }
        ],
        "imports": [],
        "exports": []
    }

    await registry.save_file_morphism(
        "update_test.py",
        "python",
        "hash2",
        morphism_data_v2
    )

    # Verify only new symbols exist
    result = await registry.get_file_morphism("update_test.py")

    assert len(result["symbols"]) == 1
    assert result["symbols"][0]["name"] == "new_function"

    # Old symbol should not exist
    old_symbol = await registry.get_symbol("old_function")
    assert old_symbol is None

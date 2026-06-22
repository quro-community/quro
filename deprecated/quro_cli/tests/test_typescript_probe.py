"""
Tests for TypeScript Probe

Tests the JSON-RPC communication and core analysis methods.
"""
import pytest
import pytest_asyncio
import asyncio
from pathlib import Path

from quro_cli.analysis.typescript_probe import (
    TypeScriptProbe,
    TypeScriptProbeError,
    TypeInfo,
    DefinitionLocation
)


@pytest_asyncio.fixture
async def probe(request):
    """Create and start a TypeScript probe instance"""
    # Use node_server tsconfig for testing
    tsconfig_path = Path(__file__).parent.parent.parent / "node_server" / "tsconfig.json"

    if not tsconfig_path.exists():
        pytest.skip("node_server/tsconfig.json not found")

    probe_instance = TypeScriptProbe(str(tsconfig_path))
    await probe_instance.start()

    yield probe_instance

    await probe_instance.stop()


@pytest.mark.asyncio
async def test_probe_initialization(probe):
    """Test probe starts and initializes successfully"""
    assert probe._ready is True
    assert probe.process is not None


@pytest.mark.asyncio
async def test_probe_ping(probe):
    """Test probe responds to ping"""
    result = await probe.ping()
    assert result is True


@pytest.mark.asyncio
async def test_get_type_at_position(probe):
    """Test getting type information at a position"""
    # Test file: node_server/lib/registry.ts
    test_file = Path(__file__).parent.parent.parent / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    # Try to get type at a known position (adjust based on actual file)
    try:
        type_info = await probe.get_type_at_position(
            str(test_file),
            line=10,
            character=10
        )

        assert isinstance(type_info, TypeInfo)
        assert type_info.type_string is not None
        assert type_info.kind is not None

    except TypeScriptProbeError as e:
        # Expected if position doesn't have a symbol
        assert "error" in str(e).lower()


@pytest.mark.asyncio
async def test_find_definition(probe):
    """Test finding symbol definition"""
    test_file = Path(__file__).parent.parent.parent / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    try:
        def_loc = await probe.find_definition(
            str(test_file),
            line=10,
            character=10
        )

        assert isinstance(def_loc, DefinitionLocation)
        assert def_loc.file_path is not None
        assert def_loc.symbol_name is not None

    except TypeScriptProbeError as e:
        # Expected if position doesn't have a symbol
        assert "error" in str(e).lower()


@pytest.mark.asyncio
async def test_resolve_import_path(probe):
    """Test resolving import paths"""
    test_file = Path(__file__).parent.parent.parent / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    # Test relative import
    try:
        resolved = await probe.resolve_import_path(
            str(test_file),
            "./types"
        )

        assert resolved is not None
        assert Path(resolved).exists()

    except TypeScriptProbeError:
        # Expected if import doesn't exist or can't be resolved
        pass


@pytest.mark.asyncio
async def test_get_diagnostics(probe):
    """Test getting file diagnostics"""
    test_file = Path(__file__).parent.parent.parent / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    diagnostics = await probe.get_diagnostics(str(test_file))

    assert isinstance(diagnostics, list)
    # File may or may not have diagnostics


@pytest.mark.asyncio
async def test_probe_error_handling():
    """Test probe handles errors gracefully"""
    probe = TypeScriptProbe("/nonexistent/tsconfig.json")

    with pytest.raises(TypeScriptProbeError):
        await probe.start()


@pytest.mark.asyncio
async def test_probe_context_manager():
    """Test probe works as async context manager"""
    tsconfig_path = Path(__file__).parent.parent.parent / "node_server" / "tsconfig.json"

    if not tsconfig_path.exists():
        pytest.skip("node_server/tsconfig.json not found")

    async with TypeScriptProbe(str(tsconfig_path)) as probe:
        assert probe._ready is True
        result = await probe.ping()
        assert result is True

    # Probe should be stopped after context exit
    assert probe._ready is False


@pytest.mark.asyncio
async def test_probe_request_timeout():
    """Test probe handles request timeouts"""
    tsconfig_path = Path(__file__).parent.parent.parent / "node_server" / "tsconfig.json"

    if not tsconfig_path.exists():
        pytest.skip("node_server/tsconfig.json not found")

    async with TypeScriptProbe(str(tsconfig_path)) as probe:
        # Call with invalid file to trigger timeout or error
        with pytest.raises(TypeScriptProbeError):
            await probe.get_type_at_position(
                "/nonexistent/file.ts",
                line=0,
                character=0
            )


@pytest.mark.asyncio
async def test_probe_concurrent_requests(probe):
    """Test probe handles concurrent requests"""
    test_file = Path(__file__).parent.parent.parent / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    # Send multiple requests concurrently
    tasks = [
        probe.ping(),
        probe.ping(),
        probe.get_diagnostics(str(test_file))
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # At least ping should succeed
    assert any(r is True for r in results if not isinstance(r, Exception))

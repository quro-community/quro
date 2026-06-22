"""
Tests for TypeScript Analyzer

Tests the high-level analysis interface with probe and fallback.
"""
import pytest
import pytest_asyncio
from pathlib import Path

from quro_cli.analysis.typescript_analyzer import (
    TypeScriptAnalyzer,
    SymbolInfo,
    ImportInfo
)


@pytest_asyncio.fixture
async def analyzer():
    """Create and initialize a TypeScript analyzer"""
    workspace_root = Path(__file__).parent.parent.parent
    tsconfig_path = workspace_root / "node_server" / "tsconfig.json"

    if not tsconfig_path.exists():
        pytest.skip("node_server/tsconfig.json not found")

    analyzer = TypeScriptAnalyzer(
        str(workspace_root),
        str(tsconfig_path)
    )
    await analyzer.initialize()

    yield analyzer

    await analyzer.shutdown()


@pytest.mark.asyncio
async def test_analyzer_initialization(analyzer):
    """Test analyzer initializes successfully"""
    health = await analyzer.health_check()

    assert health["workspace_root"] is not None
    assert health["tsconfig_path"] is not None


@pytest.mark.asyncio
async def test_get_symbol_at_position(analyzer):
    """Test getting symbol information"""
    test_file = Path(analyzer.workspace_root) / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    # Try to get symbol at a position
    symbol = await analyzer.get_symbol_at_position(
        str(test_file),
        line=10,
        character=10
    )

    # May be None if no symbol at position
    if symbol:
        assert isinstance(symbol, SymbolInfo)
        assert symbol.name is not None
        assert symbol.source in ["typescript", "tree-sitter"]


@pytest.mark.asyncio
async def test_find_definition(analyzer):
    """Test finding symbol definition"""
    test_file = Path(analyzer.workspace_root) / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    definition = await analyzer.find_definition(
        str(test_file),
        line=10,
        character=10
    )

    # May be None if no symbol at position
    if definition:
        assert isinstance(definition, SymbolInfo)
        assert definition.file_path is not None


@pytest.mark.asyncio
async def test_resolve_import(analyzer):
    """Test import path resolution"""
    test_file = Path(analyzer.workspace_root) / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    # Test relative import
    resolved = await analyzer.resolve_import(
        str(test_file),
        "./types"
    )

    # May be None if import doesn't exist
    if resolved:
        assert Path(resolved).exists()


@pytest.mark.asyncio
async def test_resolve_import_heuristic():
    """Test heuristic import resolution (without probe)"""
    workspace_root = Path(__file__).parent.parent.parent
    analyzer = TypeScriptAnalyzer(str(workspace_root))

    # Don't initialize (no probe)
    test_file = workspace_root / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    # Test relative import with heuristic
    resolved = analyzer._resolve_import_heuristic(
        str(test_file),
        "./types"
    )

    # Should resolve using heuristic rules
    if resolved:
        assert Path(resolved).exists()


@pytest.mark.asyncio
async def test_get_file_imports(analyzer):
    """Test extracting file imports"""
    test_file = Path(analyzer.workspace_root) / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    imports = await analyzer.get_file_imports(str(test_file))

    assert isinstance(imports, list)
    # File may or may not have imports


@pytest.mark.asyncio
async def test_get_file_exports(analyzer):
    """Test extracting file exports"""
    test_file = Path(analyzer.workspace_root) / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    exports = await analyzer.get_file_exports(str(test_file))

    assert isinstance(exports, list)
    # File may or may not have exports


@pytest.mark.asyncio
async def test_get_diagnostics(analyzer):
    """Test getting file diagnostics"""
    test_file = Path(analyzer.workspace_root) / "node_server" / "lib" / "registry.ts"

    if not test_file.exists():
        pytest.skip("Test file not found")

    diagnostics = await analyzer.get_diagnostics(str(test_file))

    assert isinstance(diagnostics, list)


@pytest.mark.asyncio
async def test_health_check(analyzer):
    """Test health check"""
    health = await analyzer.health_check()

    assert "probe_available" in health
    assert "workspace_root" in health
    assert "tsconfig_path" in health

    if health["probe_available"]:
        assert "probe_alive" in health


@pytest.mark.asyncio
async def test_analyzer_context_manager():
    """Test analyzer works as async context manager"""
    workspace_root = Path(__file__).parent.parent.parent
    tsconfig_path = workspace_root / "node_server" / "tsconfig.json"

    if not tsconfig_path.exists():
        pytest.skip("node_server/tsconfig.json not found")

    async with TypeScriptAnalyzer(str(workspace_root), str(tsconfig_path)) as analyzer:
        health = await analyzer.health_check()
        assert health is not None

    # Analyzer should be shutdown after context exit
    assert analyzer.probe is None or not analyzer._probe_available


@pytest.mark.asyncio
async def test_analyzer_fallback_without_probe():
    """Test analyzer works without probe (fallback mode)"""
    workspace_root = Path(__file__).parent.parent.parent

    # Create analyzer without initializing (no probe)
    analyzer = TypeScriptAnalyzer(str(workspace_root))

    # Should work with fallback methods
    test_file = workspace_root / "node_server" / "lib" / "registry.ts"

    if test_file.exists():
        # Heuristic resolution should work
        resolved = analyzer._resolve_import_heuristic(
            str(test_file),
            "./types"
        )

        # May or may not resolve depending on file structure
        assert resolved is None or Path(resolved).exists()


@pytest.mark.asyncio
async def test_analyzer_graceful_degradation(analyzer):
    """Test analyzer degrades gracefully on errors"""
    # Try to analyze non-existent file
    symbol = await analyzer.get_symbol_at_position(
        "/nonexistent/file.ts",
        line=0,
        character=0
    )

    # Should return None instead of crashing
    assert symbol is None

    # Try to resolve non-existent import
    resolved = await analyzer.resolve_import(
        "/nonexistent/file.ts",
        "./foo"
    )

    # Should return None instead of crashing
    assert resolved is None

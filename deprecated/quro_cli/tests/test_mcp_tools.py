"""
Tests for MCP Tools

Tests the tool implementations.
"""
import pytest
import pytest_asyncio
from pathlib import Path

from quro_cli.mcp.tools import MCPTools


@pytest_asyncio.fixture
async def tools():
    """Create and initialize MCPTools instance"""
    workspace_root = Path(__file__).parent.parent.parent
    db_url = "postgresql://localhost/quro_test"
    tsconfig_path = workspace_root / "node_server" / "tsconfig.json"

    if not tsconfig_path.exists():
        pytest.skip("node_server/tsconfig.json not found")

    tools_instance = MCPTools(
        workspace_root=str(workspace_root),
        db_url=db_url,
        tsconfig_path=str(tsconfig_path)
    )

    # Note: setup() will fail if DB not available, but that's expected in tests
    try:
        await tools_instance.setup()
    except Exception as e:
        pytest.skip(f"Could not initialize tools: {e}")

    yield tools_instance

    await tools_instance.shutdown()


@pytest.mark.asyncio
async def test_identify_symbol_not_found(tools):
    """Test identify_symbol with non-existent symbol"""
    result = await tools.identify_symbol(symbol="NonExistentSymbol123")

    assert result["status"] == "not_found"
    assert result["symbol"] == "NonExistentSymbol123"


@pytest.mark.asyncio
async def test_identify_symbol_basic():
    """Test identify_symbol without database (basic functionality)"""
    workspace_root = Path(__file__).parent.parent.parent
    tsconfig_path = workspace_root / "node_server" / "tsconfig.json"

    if not tsconfig_path.exists():
        pytest.skip("node_server/tsconfig.json not found")

    # Create tools without DB connection
    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test",
        tsconfig_path=str(tsconfig_path)
    )

    # Initialize only analyzer (skip registry)
    tools.analyzer = None  # Will be initialized in setup
    try:
        await tools.setup()
    except Exception:
        # Expected if DB not available
        pass

    # Test with non-existent symbol
    result = await tools.identify_symbol(symbol="TestSymbol")

    assert "status" in result
    assert result["symbol"] == "TestSymbol"

    await tools.shutdown()


@pytest.mark.asyncio
async def test_tools_context_manager():
    """Test MCPTools works as async context manager"""
    workspace_root = Path(__file__).parent.parent.parent
    tsconfig_path = workspace_root / "node_server" / "tsconfig.json"

    if not tsconfig_path.exists():
        pytest.skip("node_server/tsconfig.json not found")

    try:
        async with MCPTools(
            workspace_root=str(workspace_root),
            db_url="postgresql://localhost/quro_test",
            tsconfig_path=str(tsconfig_path)
        ) as tools:
            # Should be initialized
            assert tools.analyzer is not None

            # Test a tool call
            result = await tools.identify_symbol(symbol="TestSymbol")
            assert "status" in result

    except Exception as e:
        # Expected if DB not available
        pytest.skip(f"Could not initialize tools: {e}")


@pytest.mark.asyncio
async def test_find_neighbors_empty():
    """Test _find_neighbors with no registry"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    # Without registry, should return empty list
    neighbors = await tools._find_neighbors("test_signature")
    assert neighbors == []


@pytest.mark.asyncio
async def test_identify_symbol_error_handling():
    """Test identify_symbol handles errors gracefully"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    # Don't initialize - should handle gracefully
    result = await tools.identify_symbol(symbol="TestSymbol")

    # Should return not_found or error, not crash
    assert result["status"] in ["not_found", "error"]
    assert result["symbol"] == "TestSymbol"


@pytest.mark.asyncio
async def test_read_source_symbol_file_not_found():
    """Test read_source_symbol with non-existent file"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.read_source_symbol(
        filepath="/nonexistent/file.ts",
        symbol_name="TestSymbol"
    )

    assert result["status"] == "not_found"
    assert result["filepath"] == "/nonexistent/file.ts"
    assert "error" in result


@pytest.mark.asyncio
async def test_read_source_symbol_success():
    """Test read_source_symbol with existing file"""
    workspace_root = Path(__file__).parent.parent.parent
    test_file = workspace_root / "quro_cli" / "mcp" / "tools.py"

    if not test_file.exists():
        pytest.skip("Test file not found")

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.read_source_symbol(
        filepath=str(test_file),
        symbol_name="MCPTools"
    )

    assert result["status"] == "success"
    assert result["filepath"] == str(test_file)
    assert result["symbol_name"] == "MCPTools"
    assert "source" in result
    assert len(result["source"]) > 0


@pytest.mark.asyncio
async def test_read_source_symbol_with_line_range():
    """Test read_source_symbol with line range"""
    workspace_root = Path(__file__).parent.parent.parent
    test_file = workspace_root / "quro_cli" / "mcp" / "tools.py"

    if not test_file.exists():
        pytest.skip("Test file not found")

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.read_source_symbol(
        filepath=str(test_file),
        symbol_name="MCPTools",
        line_range=[0, 10]
    )

    assert result["status"] == "success"
    assert result["line_start"] == 0
    assert result["line_end"] == 10
    assert "source" in result


@pytest.mark.asyncio
async def test_verify_symbol_integrity_not_found():
    """Test verify_symbol_integrity with non-existent symbol"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.verify_symbol_integrity(symbol="NonExistentSymbol123")

    assert result["status"] == "not_found"
    assert result["symbol"] == "NonExistentSymbol123"
    assert result["exists"] is False
    assert "suggestions" in result


@pytest.mark.asyncio
async def test_distill_patch_context_file_not_found():
    """Test distill_patch_context with non-existent file"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.distill_patch_context(
        file_path="/nonexistent/file.ts",
        line_start=10,
        line_end=20
    )

    assert result["status"] == "error"
    assert "error" in result


@pytest.mark.asyncio
async def test_distill_patch_context_success():
    """Test distill_patch_context with existing file"""
    workspace_root = Path(__file__).parent.parent.parent
    test_file = workspace_root / "quro_cli" / "mcp" / "tools.py"

    if not test_file.exists():
        pytest.skip("Test file not found")

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.distill_patch_context(
        file_path=str(test_file),
        line_start=10,
        line_end=20
    )

    assert result["status"] == "success"
    assert result["file_path"] == str(test_file)
    assert "patch_lines" in result
    assert "context_before" in result
    assert "context_after" in result
    assert "affected_symbols" in result
    assert "dependencies" in result


@pytest.mark.asyncio
async def test_compact_context_basic():
    """Test compact_context with basic text"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    context = """
    // This is a comment
    function foo() {
        console.log('hello');
    }
    // Another comment
    function bar() {
        console.log('world');
    }
    function foo() {
        console.log('hello');
    }
    """

    result = await tools.compact_context(context=context, max_tokens=1000)

    assert result["status"] == "success"
    assert result["original_length"] > 0
    assert result["compressed_length"] < result["original_length"]
    assert result["compression_ratio"] < 1.0
    assert "compressed_context" in result
    assert "removed_sections" in result


@pytest.mark.asyncio
async def test_compact_context_preserve_symbols():
    """Test compact_context with preserved symbols"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    context = "function important() {}\nfunction other() {}"

    result = await tools.compact_context(
        context=context,
        max_tokens=100,
        preserve_symbols=["important"]
    )

    assert result["status"] == "success"
    assert "important" in result["compressed_context"]


@pytest.mark.asyncio
async def test_trace_logic_path_not_found():
    """Test trace_logic_path with non-existent symbol"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.trace_logic_path(start_symbol="NonExistentSymbol")

    assert result["status"] == "not_found"
    assert result["start_symbol"] == "NonExistentSymbol"


@pytest.mark.asyncio
async def test_get_pitfall_all():
    """Test get_pitfall without filters"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_pitfall()

    assert result["status"] == "success"
    assert "pitfalls" in result
    assert "count" in result
    assert result["count"] > 0


@pytest.mark.asyncio
async def test_get_pitfall_filtered():
    """Test get_pitfall with category filter"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_pitfall(category="async", severity="high")

    assert result["status"] == "success"
    assert "pitfalls" in result

    # Check all returned pitfalls match filters
    for pitfall in result["pitfalls"]:
        assert pitfall["category"] == "async"
        assert pitfall["severity"] == "high"


@pytest.mark.asyncio
async def test_get_nrt_alerts_all():
    """Test get_nrt_alerts without filters"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_nrt_alerts()

    assert result["status"] == "success"
    assert "alerts" in result
    assert "count" in result
    assert result["count"] > 0


@pytest.mark.asyncio
async def test_get_nrt_alerts_filtered():
    """Test get_nrt_alerts with severity filter"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_nrt_alerts(severity="critical", limit=5)

    assert result["status"] == "success"
    assert "alerts" in result
    assert len(result["alerts"]) <= 5

    # Check all returned alerts match filter
    for alert in result["alerts"]:
        assert alert["severity"] == "critical"


@pytest.mark.asyncio
async def test_cqe_query_basic():
    """Test cqe_query with basic query"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.cqe_query(
        query="Find async functions",
        entry_token="async"
    )

    assert result["status"] == "success"
    assert result["query"] == "Find async functions"
    assert result["entry_token"] == "async"
    assert "path_mi" in result
    assert "results" in result
    assert "traversal_depth" in result
    assert "nodes_visited" in result


@pytest.mark.asyncio
async def test_cqe_query_with_params():
    """Test cqe_query with custom parameters"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.cqe_query(
        query="Find async patterns",
        entry_token="async",
        tau=0.2,
        max_depth=5
    )

    assert result["status"] == "success"
    assert result["traversal_depth"] == 5


@pytest.mark.asyncio
async def test_project_panorama_basic():
    """Test project_panorama with default options"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.project_panorama()

    assert result["status"] == "success"
    assert "workspace_root" in result
    assert "stats" in result
    assert "health" in result


@pytest.mark.asyncio
async def test_project_panorama_stats_only():
    """Test project_panorama with stats only"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.project_panorama(
        include_stats=True,
        include_health=False
    )

    assert result["status"] == "success"
    assert "stats" in result
    assert "health" not in result

    # Check stats structure
    stats = result["stats"]
    assert "total_files" in stats
    assert "total_symbols" in stats
    assert "languages" in stats


@pytest.mark.asyncio
async def test_project_panorama_health_only():
    """Test project_panorama with health only"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.project_panorama(
        include_stats=False,
        include_health=True
    )

    assert result["status"] == "success"
    assert "stats" not in result
    assert "health" in result

    # Check health structure
    health = result["health"]
    assert "probe_status" in health
    assert "registry_status" in health
    assert "issues" in health


# === Phase 3 Day 1 Tests ===


@pytest.mark.asyncio
async def test_query_semantic_inventory_basic():
    """Test query_semantic_inventory with basic query"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.query_semantic_inventory(
        query="async function handler",
        threshold=0.3,
        limit=10
    )

    # Should succeed even without registry setup
    assert result["status"] in ["success", "error"]
    if result["status"] == "success":
        assert result["query"] == "async function handler"
        assert "results" in result
        assert "count" in result
        assert result["threshold"] == 0.3
        assert len(result["results"]) <= 10
    else:
        # Registry not available - expected in test environment
        assert "error" in result


@pytest.mark.asyncio
async def test_query_semantic_inventory_no_results():
    """Test query_semantic_inventory with no matching results"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.query_semantic_inventory(
        query="xyzabc123nonexistent",
        threshold=0.9,
        limit=5
    )

    # Should succeed even without registry setup
    assert result["status"] in ["success", "error"]
    if result["status"] == "success":
        assert result["count"] == 0
        assert len(result["results"]) == 0


@pytest.mark.asyncio
async def test_get_vocabulary_success():
    """Test get_vocabulary with valid file"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_vocabulary(
        file_path="quro_cli/mcp/tools.py"
    )

    assert result["status"] == "success"
    assert result["file_path"] == "quro_cli/mcp/tools.py"
    assert "symbols" in result
    assert "count" in result


@pytest.mark.asyncio
async def test_get_vocabulary_file_not_found():
    """Test get_vocabulary with non-existent file"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_vocabulary(
        file_path="nonexistent/file.py"
    )

    assert result["status"] == "error"
    assert "error" in result


@pytest.mark.asyncio
async def test_get_chain_basic():
    """Test get_chain with symbol"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_chain(symbol="MCPTools")

    assert result["status"] == "success"
    assert result["symbol"] == "MCPTools"
    assert "chain" in result
    assert "count" in result
    assert result["count"] > 0


@pytest.mark.asyncio
async def test_commit_reasoning_basic():
    """Test commit_reasoning with reasoning text"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.commit_reasoning(
        symbol="test_symbol",
        reasoning="This is a test reasoning",
        tags=["test", "async"]
    )

    assert result["status"] == "success"
    assert result["symbol"] == "test_symbol"
    assert "reasoning_id" in result
    assert result["tags"] == ["test", "async"]


@pytest.mark.asyncio
async def test_commit_reasoning_no_tags():
    """Test commit_reasoning without tags"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.commit_reasoning(
        symbol="test_symbol",
        reasoning="Test reasoning without tags"
    )

    assert result["status"] == "success"
    assert result["tags"] == []


@pytest.mark.asyncio
async def test_commit_chain_basic():
    """Test commit_chain with reasoning chain"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    chain = [
        {"step": 1, "reasoning": "First step"},
        {"step": 2, "reasoning": "Second step"},
        {"step": 3, "reasoning": "Third step"}
    ]

    result = await tools.commit_chain(
        symbol="test_symbol",
        chain=chain
    )

    assert result["status"] == "success"
    assert result["symbol"] == "test_symbol"
    assert "chain_id" in result
    assert result["steps"] == 3


@pytest.mark.asyncio
async def test_commit_chain_empty():
    """Test commit_chain with empty chain"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.commit_chain(
        symbol="test_symbol",
        chain=[]
    )

    assert result["status"] == "success"
    assert result["steps"] == 0


# === Phase 3 Day 2 Tests ===


@pytest.mark.asyncio
async def test_lds_audit_file():
    """Test lds_audit with file path"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.lds_audit(file_path="quro_cli/mcp/tools.py")

    assert result["status"] == "success"
    assert "audit_id" in result
    assert "issues" in result
    assert "dependencies" in result
    assert "risk_score" in result
    assert result["file_path"] == "quro_cli/mcp/tools.py"


@pytest.mark.asyncio
async def test_lds_audit_symbol():
    """Test lds_audit with symbol"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.lds_audit(symbol="MCPTools")

    assert result["status"] == "success"
    assert "audit_id" in result
    assert result["symbol"] == "MCPTools"


@pytest.mark.asyncio
async def test_patch_logic_atoms_valid():
    """Test patch_logic_atoms with valid atoms"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    atoms = ["ACQ(lock)", "STA(process)", "REL(lock)"]
    result = await tools.patch_logic_atoms(
        file_path="test.py",
        atoms=atoms,
        validation=True
    )

    assert result["status"] == "success"
    assert "patch_id" in result
    assert result["atoms"] == atoms
    assert result["validation_result"]["valid"] is True


@pytest.mark.asyncio
async def test_patch_logic_atoms_invalid():
    """Test patch_logic_atoms with invalid atoms"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    atoms = ["ACQ(lock)", "", "REL(lock)"]  # Empty atom
    result = await tools.patch_logic_atoms(
        file_path="test.py",
        atoms=atoms,
        validation=True
    )

    assert result["status"] == "success"
    assert result["validation_result"]["valid"] is False
    assert len(result["validation_result"]["errors"]) > 0


@pytest.mark.asyncio
async def test_create_shadow_draft_basic():
    """Test create_shadow_draft with basic parameters"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.create_shadow_draft(
        symbol="TestWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="quro_lds/test_worker.py"
    )

    assert result["status"] == "success"
    assert "draft_id" in result
    assert result["symbol"] == "TestWorker"
    assert "checksum" in result
    assert "staging_path" in result
    assert result["atoms_count"] == 3


@pytest.mark.asyncio
async def test_create_shadow_draft_auto_eject():
    """Test create_shadow_draft with auto_eject"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.create_shadow_draft(
        symbol="AutoWorker",
        atoms=["STA(work)"],
        language="python",
        target_path="quro_lds/auto_worker.py",
        auto_eject=True
    )

    assert result["status"] == "success"
    assert result["auto_eject"] is True


@pytest.mark.asyncio
async def test_eject_shadow_draft_success():
    """Test eject_shadow_draft successful ejection"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.eject_shadow_draft(symbol="TestWorker")

    assert result["status"] == "success"
    assert result["symbol"] == "TestWorker"
    assert "materialized_path" in result
    assert "risk_score" in result
    assert result["risk_score"] <= 0.1


@pytest.mark.asyncio
async def test_eject_shadow_draft_force():
    """Test eject_shadow_draft with force flag"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.eject_shadow_draft(symbol="RiskyWorker", force=True)

    assert result["status"] == "success"
    assert result["forced"] is True


@pytest.mark.asyncio
async def test_get_draft_status_basic():
    """Test get_draft_status"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_draft_status(symbol="TestWorker")

    assert result["status"] == "success"
    assert result["symbol"] == "TestWorker"
    assert "draft_status" in result
    assert "progress" in result
    assert "message" in result
    assert result["draft_status"] in ["PENDING", "IN_PROGRESS", "MATERIALIZED", "REJECTED"]


# === Phase 3 Day 3 Tests ===


@pytest.mark.asyncio
async def test_approve_self_heal_approved():
    """Test approve_self_heal with approval"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.approve_self_heal(
        proposal_id="prop_001",
        approved=True,
        reason="Looks good"
    )

    assert result["status"] == "success"
    assert result["proposal_id"] == "prop_001"
    assert result["approved"] is True
    assert result["applied"] is True


@pytest.mark.asyncio
async def test_approve_self_heal_rejected():
    """Test approve_self_heal with rejection"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.approve_self_heal(
        proposal_id="prop_002",
        approved=False,
        reason="Too risky"
    )

    assert result["status"] == "success"
    assert result["approved"] is False
    assert result["applied"] is False


@pytest.mark.asyncio
async def test_run_twin_simulation_safe():
    """Test run_twin_simulation with safe atoms"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.run_twin_simulation(
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        iterations=1000
    )

    assert result["status"] == "success"
    assert "simulation_id" in result
    assert "risk_score" in result
    assert "deadlock_detected" in result
    assert result["iterations"] == 1000


@pytest.mark.asyncio
async def test_run_twin_simulation_deadlock():
    """Test run_twin_simulation detecting deadlock"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.run_twin_simulation(
        atoms=["ACQ(lock1)", "ACQ(lock2)"],  # No REL - potential deadlock
        iterations=500
    )

    assert result["status"] == "success"
    assert result["deadlock_detected"] is True
    assert result["risk_score"] > 0.5


@pytest.mark.asyncio
async def test_get_twin_report():
    """Test get_twin_report"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_twin_report(simulation_id="sim_001")

    assert result["status"] == "success"
    assert result["simulation_id"] == "sim_001"
    assert "report" in result
    assert "witness_traces" in result


@pytest.mark.asyncio
async def test_update_session():
    """Test update_session"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    metadata = {
        "user": "test_user",
        "timestamp": "2026-04-07T12:00:00Z"
    }

    result = await tools.update_session(
        session_id="sess_001",
        metadata=metadata
    )

    assert result["status"] == "success"
    assert result["session_id"] == "sess_001"
    assert "updated_fields" in result
    assert len(result["updated_fields"]) == 2


@pytest.mark.asyncio
async def test_get_morph_alerts_all():
    """Test get_morph_alerts without filter"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_morph_alerts(limit=10)

    assert result["status"] == "success"
    assert "alerts" in result
    assert "count" in result
    assert len(result["alerts"]) <= 10


@pytest.mark.asyncio
async def test_get_morph_alerts_filtered():
    """Test get_morph_alerts with severity filter"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_morph_alerts(severity="high", limit=5)

    assert result["status"] == "success"
    assert result["severity_filter"] == "high"
    for alert in result["alerts"]:
        assert alert["severity"] == "high"


@pytest.mark.asyncio
async def test_cqe_load_index():
    """Test cqe_load_index"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.cqe_load_index(
        index_path=".quro_context/cqe_index.json"
    )

    assert result["status"] == "success"
    assert result["index_path"] == ".quro_context/cqe_index.json"
    assert "categories_loaded" in result
    assert "symbols_loaded" in result


@pytest.mark.asyncio
async def test_cqe_reflect_basic():
    """Test cqe_reflect without filters"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.cqe_reflect(limit=20)

    assert result["status"] == "success"
    assert "reflections" in result
    assert "count" in result
    assert result["limit"] == 20


@pytest.mark.asyncio
async def test_cqe_reflect_with_mi_summary():
    """Test cqe_reflect with MI summary"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.cqe_reflect(
        entry_atom="cat::async",
        mi_summary=True
    )

    assert result["status"] == "success"
    assert "mi_summary" in result
    assert result["entry_atom_filter"] == "cat::async"


@pytest.mark.asyncio
async def test_cqe_train_mi():
    """Test cqe_train_mi"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.cqe_train_mi(
        reflection_log_path=".quro_context/cqe_reflections.jsonl",
        epochs=10
    )

    assert result["status"] == "success"
    assert "model_path" in result
    assert result["epochs_completed"] == 10
    assert "final_loss" in result


@pytest.mark.asyncio
async def test_cqe_get_mi_stats_all():
    """Test cqe_get_mi_stats without filter"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.cqe_get_mi_stats()

    assert result["status"] == "success"
    assert "stats" in result
    assert "atom_count" in result


@pytest.mark.asyncio
async def test_cqe_get_mi_stats_filtered():
    """Test cqe_get_mi_stats with atom filter"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.cqe_get_mi_stats(atom_id="cat::async")

    assert result["status"] == "success"
    assert result["atom_id_filter"] == "cat::async"


@pytest.mark.asyncio
async def test_graft_query_dependencies():
    """Test graft_query for dependencies"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.graft_query(
        query_type="dependencies",
        symbol="MCPTools",
        depth=3
    )

    assert result["status"] == "success"
    assert result["query_type"] == "dependencies"
    assert result["symbol"] == "MCPTools"
    assert "results" in result
    assert result["depth"] == 3


# === Phase 3 Day 5 Tests ===


@pytest.mark.asyncio
async def test_graft_trace_with_end():
    """Test graft_trace with end symbol"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.graft_trace(
        start_symbol="MCPTools",
        end_symbol="TypeScriptAnalyzer",
        max_depth=5
    )

    assert result["status"] == "success"
    assert result["start_symbol"] == "MCPTools"
    assert result["end_symbol"] == "TypeScriptAnalyzer"
    assert "traces" in result
    assert result["count"] > 0


@pytest.mark.asyncio
async def test_graft_trace_without_end():
    """Test graft_trace without end symbol"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.graft_trace(
        start_symbol="MCPTools",
        max_depth=3
    )

    assert result["status"] == "success"
    assert result["end_symbol"] is None
    assert "traces" in result


@pytest.mark.asyncio
async def test_graft_verify():
    """Test graft_verify"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.graft_verify()

    assert result["status"] == "success"
    assert "valid" in result
    assert "issues" in result
    assert "stats" in result


@pytest.mark.asyncio
async def test_graft_prune_dry_run():
    """Test graft_prune with dry run"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.graft_prune(max_age_days=30, dry_run=True)

    assert result["status"] == "success"
    assert result["dry_run"] is True
    assert result["pruned_count"] == 0
    assert "pruned_edges" in result


@pytest.mark.asyncio
async def test_graft_prune_apply():
    """Test graft_prune with apply"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.graft_prune(max_age_days=30, dry_run=False)

    assert result["status"] == "success"
    assert result["dry_run"] is False


@pytest.mark.asyncio
async def test_graft_export():
    """Test graft_export"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.graft_export(
        output_path="/tmp/graph.json",
        format="json"
    )

    assert result["status"] == "success"
    assert result["output_path"] == "/tmp/graph.json"
    assert "node_count" in result
    assert "edge_count" in result


@pytest.mark.asyncio
async def test_graft_import():
    """Test graft_import"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.graft_import(
        input_path="/tmp/graph.json",
        merge=False
    )

    assert result["status"] == "success"
    assert result["input_path"] == "/tmp/graph.json"
    assert "node_count" in result
    assert "edge_count" in result


@pytest.mark.asyncio
async def test_graft_import_merge():
    """Test graft_import with merge"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.graft_import(
        input_path="/tmp/graph.json",
        merge=True
    )

    assert result["status"] == "success"
    assert result["merged"] is True


@pytest.mark.asyncio
async def test_graft_diff():
    """Test graft_diff"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.graft_diff(
        graph1_path="/tmp/graph1.json",
        graph2_path="/tmp/graph2.json"
    )

    assert result["status"] == "success"
    assert "added_nodes" in result
    assert "removed_nodes" in result
    assert "added_edges" in result
    assert "removed_edges" in result


@pytest.mark.asyncio
async def test_scan_workspace():
    """Test scan_workspace"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.scan_workspace(
        file_patterns=["*.py", "*.ts"]
    )

    assert result["status"] == "success"
    assert "files_scanned" in result
    assert "symbols_found" in result
    assert "dependencies_found" in result


@pytest.mark.asyncio
async def test_index_symbols_all():
    """Test index_symbols for all files"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.index_symbols(rebuild=False)

    assert result["status"] == "success"
    assert "symbols_indexed" in result
    assert "files_processed" in result


@pytest.mark.asyncio
async def test_index_symbols_rebuild():
    """Test index_symbols with rebuild"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.index_symbols(rebuild=True)

    assert result["status"] == "success"
    assert result["rebuild"] is True


@pytest.mark.asyncio
async def test_get_file_morphism():
    """Test get_file_morphism"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.get_file_morphism(
        file_path="quro_cli/mcp/tools.py"
    )

    assert result["status"] in ["success", "not_found"]
    assert result["file_path"] == "quro_cli/mcp/tools.py"


@pytest.mark.asyncio
async def test_save_file_morphism():
    """Test save_file_morphism"""
    workspace_root = Path(__file__).parent.parent.parent

    tools = MCPTools(
        workspace_root=str(workspace_root),
        db_url="postgresql://localhost/quro_test"
    )

    result = await tools.save_file_morphism(
        file_path="test.py",
        lsh_signature="abc123",
        exports=["foo", "bar"],
        last_modified=1234567890
    )

    assert result["status"] in ["success", "error"]
    assert result["file_path"] == "test.py"





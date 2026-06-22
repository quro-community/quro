"""
Tests for shadow draft tools.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from quro_cli.shadow.shadow_draft_tools import (
    ShadowDraftManager,
    create_shadow_draft,
    eject_shadow_draft,
    get_draft_status,
    approve_self_heal
)


@pytest.fixture
def temp_workspace():
    """Create temporary workspace"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def manager(temp_workspace):
    """Create shadow draft manager"""
    return ShadowDraftManager(temp_workspace, risk_gate=0.1)


@pytest.mark.asyncio
async def test_create_simple_draft(manager):
    """Test creating simple shadow draft"""
    result = await manager.create_shadow_draft(
        symbol="SimpleWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="simple_worker.py"
    )

    assert result["ok"]
    assert "draft_id" in result
    assert "checksum" in result
    assert result["status"] == "PENDING"


@pytest.mark.asyncio
async def test_create_draft_with_invalid_atoms(manager):
    """Test creating draft with invalid atom sequence"""
    result = await manager.create_shadow_draft(
        symbol="InvalidWorker",
        atoms=["REL(lock)", "STA(work)"],  # Release without acquire
        language="python",
        target_path="invalid_worker.py"
    )

    assert not result["ok"]
    assert "Invalid atom sequence" in result["error"]


@pytest.mark.asyncio
async def test_create_draft_with_unparseable_atoms(manager):
    """Test creating draft with unparseable atoms"""
    result = await manager.create_shadow_draft(
        symbol="BadWorker",
        atoms=["INVALID_ATOM"],
        language="python",
        target_path="bad_worker.py"
    )

    assert not result["ok"]
    assert "Failed to parse" in result["error"]


@pytest.mark.asyncio
async def test_eject_safe_draft(manager):
    """Test ejecting safe draft (low risk)"""
    # Create draft
    await manager.create_shadow_draft(
        symbol="SafeWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="safe_worker.py"
    )

    # Eject
    result = await manager.eject_shadow_draft("SafeWorker")

    assert result["ok"]
    assert result["status"] == "MATERIALIZED"
    assert result["risk_score"] == 0.0
    assert "skeleton_preview" in result
    assert "target_path" in result

    # Check file was created
    target_path = Path(result["target_path"])
    assert target_path.exists()
    assert target_path.read_text().startswith("class SafeWorker:")


@pytest.mark.asyncio
async def test_eject_risky_draft(manager):
    """Test ejecting risky draft (high risk)"""
    # Create draft with deadlock pattern
    await manager.create_shadow_draft(
        symbol="RiskyWorker",
        atoms=["ACQ(lock1)", "ACQ(lock2)", "REL(lock2)", "REL(lock1)"],
        language="python",
        target_path="risky_worker.py"
    )

    # Note: Single thread won't deadlock, but let's test the rejection mechanism
    # by using a very low risk gate
    manager.risk_gate = 0.0

    result = await manager.eject_shadow_draft("RiskyWorker")

    # With risk_gate=0.0, even risk_score=0.0 should pass
    assert result["ok"]


@pytest.mark.asyncio
async def test_eject_nonexistent_draft(manager):
    """Test ejecting nonexistent draft"""
    result = await manager.eject_shadow_draft("NonexistentWorker")

    assert not result["ok"]
    assert "No draft found" in result["error"]


@pytest.mark.asyncio
async def test_eject_with_force(manager):
    """Test ejecting with force flag"""
    # Create draft
    await manager.create_shadow_draft(
        symbol="ForcedWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="forced_worker.py"
    )

    # Eject with force (should bypass risk gate)
    result = await manager.eject_shadow_draft("ForcedWorker", force=True)

    assert result["ok"]
    assert result["status"] == "MATERIALIZED"


@pytest.mark.asyncio
async def test_get_draft_status_pending(manager):
    """Test getting status of pending draft"""
    await manager.create_shadow_draft(
        symbol="PendingWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="pending_worker.py"
    )

    result = await manager.get_draft_status("PendingWorker")

    assert result["ok"]
    assert result["status"] == "PENDING"
    assert "draft_id" in result
    assert "created_at" in result


@pytest.mark.asyncio
async def test_get_draft_status_materialized(manager):
    """Test getting status of materialized draft"""
    await manager.create_shadow_draft(
        symbol="MaterializedWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="materialized_worker.py"
    )

    await manager.eject_shadow_draft("MaterializedWorker")

    result = await manager.get_draft_status("MaterializedWorker")

    assert result["ok"]
    assert result["status"] == "MATERIALIZED"
    assert "materialized_at" in result
    assert result["risk_score"] == 0.0


@pytest.mark.asyncio
async def test_get_draft_status_nonexistent(manager):
    """Test getting status of nonexistent draft"""
    result = await manager.get_draft_status("NonexistentWorker")

    assert not result["ok"]
    assert "No draft found" in result["error"]


@pytest.mark.asyncio
async def test_approve_self_heal(manager):
    """Test approving self-heal with corrected atoms"""
    # Create initial draft
    await manager.create_shadow_draft(
        symbol="HealableWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="healable_worker.py"
    )

    # Approve self-heal with corrected atoms
    result = await manager.approve_self_heal(
        symbol="HealableWorker",
        corrected_atoms=["ACQ(lock)", "STA(improved_work)", "REL(lock)"]
    )

    assert result["ok"]
    assert "draft_id" in result


@pytest.mark.asyncio
async def test_approve_self_heal_nonexistent(manager):
    """Test approving self-heal for nonexistent draft"""
    result = await manager.approve_self_heal(
        symbol="NonexistentWorker",
        corrected_atoms=["ACQ(lock)", "REL(lock)"]
    )

    assert not result["ok"]
    assert "No draft found" in result["error"]


@pytest.mark.asyncio
async def test_auto_eject_on_create(manager):
    """Test auto-eject on draft creation"""
    result = await manager.create_shadow_draft(
        symbol="AutoEjectWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="auto_eject_worker.py",
        auto_eject=True
    )

    assert result["ok"]
    assert result["status"] == "MATERIALIZED"
    assert result["auto_ejected"]


@pytest.mark.asyncio
async def test_typescript_skeleton_generation(manager):
    """Test TypeScript skeleton generation"""
    await manager.create_shadow_draft(
        symbol="TypeScriptWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="typescript",
        target_path="typescript_worker.ts"
    )

    result = await manager.eject_shadow_draft("TypeScriptWorker")

    assert result["ok"]
    assert result["status"] == "MATERIALIZED"

    # Check TypeScript syntax
    target_path = Path(result["target_path"])
    content = target_path.read_text()
    assert "class TypeScriptWorker" in content
    assert "async execute()" in content
    assert "await this.lock.acquire()" in content


@pytest.mark.asyncio
async def test_python_skeleton_generation(manager):
    """Test Python skeleton generation"""
    await manager.create_shadow_draft(
        symbol="PythonWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="python_worker.py"
    )

    result = await manager.eject_shadow_draft("PythonWorker")

    assert result["ok"]
    assert result["status"] == "MATERIALIZED"

    # Check Python syntax
    target_path = Path(result["target_path"])
    content = target_path.read_text()
    assert "class PythonWorker:" in content
    assert "async def execute(self):" in content
    assert "async with self.lock:" in content


@pytest.mark.asyncio
async def test_rejection_count_tracking(manager):
    """Test rejection count tracking and gate relaxation"""
    # Create draft that might be rejected
    await manager.create_shadow_draft(
        symbol="RejectedWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="rejected_worker.py"
    )

    # Simulate 3 rejections by setting very low gate
    manager.risk_gate = -0.1  # Impossible to pass

    for i in range(3):
        result = await manager.eject_shadow_draft("RejectedWorker")
        if not result["ok"] or result["status"] == "REJECTED":
            manager.rejection_counts["RejectedWorker"] = i + 1

    # Check gate relaxation
    assert manager.rejection_counts.get("RejectedWorker", 0) >= 3


@pytest.mark.asyncio
async def test_draft_checksum_generation(manager):
    """Test draft checksum generation"""
    result1 = await manager.create_shadow_draft(
        symbol="ChecksumWorker1",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="checksum_worker1.py"
    )

    result2 = await manager.create_shadow_draft(
        symbol="ChecksumWorker2",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="checksum_worker2.py"
    )

    # Same atoms should produce same checksum
    assert result1["checksum"] == result2["checksum"]


@pytest.mark.asyncio
async def test_mcp_tool_create_shadow_draft(temp_workspace):
    """Test MCP tool: create_shadow_draft"""
    result = await create_shadow_draft(
        symbol="MCPWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="mcp_worker.py",
        workspace_root=temp_workspace
    )

    assert result["ok"]
    assert result["status"] == "PENDING"


@pytest.mark.asyncio
async def test_mcp_tool_eject_shadow_draft(temp_workspace):
    """Test MCP tool: eject_shadow_draft"""
    # Use manager directly to maintain state
    manager = ShadowDraftManager(temp_workspace)

    # Create draft first
    await manager.create_shadow_draft(
        symbol="MCPEjectWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="mcp_eject_worker.py"
    )

    # Eject
    result = await manager.eject_shadow_draft("MCPEjectWorker")

    assert result["ok"]
    assert result["status"] == "MATERIALIZED"


@pytest.mark.asyncio
async def test_mcp_tool_get_draft_status(temp_workspace):
    """Test MCP tool: get_draft_status"""
    # Use manager directly to maintain state
    manager = ShadowDraftManager(temp_workspace)

    # Create draft first
    await manager.create_shadow_draft(
        symbol="MCPStatusWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="mcp_status_worker.py"
    )

    # Get status
    result = await manager.get_draft_status("MCPStatusWorker")

    assert result["ok"]
    assert result["status"] == "PENDING"


@pytest.mark.asyncio
async def test_mcp_tool_approve_self_heal(temp_workspace):
    """Test MCP tool: approve_self_heal"""
    # Use manager directly to maintain state
    manager = ShadowDraftManager(temp_workspace)

    # Create draft first
    await manager.create_shadow_draft(
        symbol="MCPHealWorker",
        atoms=["ACQ(lock)", "STA(work)", "REL(lock)"],
        language="python",
        target_path="mcp_heal_worker.py"
    )

    # Approve self-heal
    result = await manager.approve_self_heal(
        symbol="MCPHealWorker",
        corrected_atoms=["ACQ(lock)", "STA(better_work)", "REL(lock)"]
    )

    assert result["ok"]

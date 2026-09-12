import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from lxion.tools.registry import registry
from lxion.memory.workspace import workspace

@pytest.mark.asyncio
async def test_unified_kanban_manager():
    tool = registry.get_tool("kanban_manager")
    assert tool is not None

    # 1. Create task
    res = await tool.execute(action="create", title="Test Unified Task", description="Testing manager", priority="high")
    assert res["success"] is True
    task_id = res["task"]["id"]

    # 2. Update task
    up_res = await tool.execute(action="update", task_id=task_id, status="in_progress")
    assert up_res["success"] is True
    assert up_res["task"]["status"] == "in_progress"

    # 3. Breakdown task
    bd_res = await tool.execute(action="breakdown", task_id=task_id, subtasks=["Subtask 1", "Subtask 2"])
    assert bd_res["success"] is True
    assert len(bd_res["task"]["subtasks"]) == 2

    # 4. Get board
    board = await tool.execute(action="get_board")
    assert "in_progress" in board

@pytest.mark.asyncio
async def test_unified_workspace_ops(tmp_path):
    tool = registry.get_tool("workspace_ops")
    assert tool is not None

    # 1. mkdir
    res_mkdir = await tool.execute(action="mkdir", path="unified_test_dir")
    assert res_mkdir["success"] is True

    # Write a test file inside workspace
    workspace.write_file("unified_test_dir/sample.txt", "hello unified")

    # 2. find
    res_find = await tool.execute(action="find", pattern="sample.txt", sub_dir="unified_test_dir")
    assert len(res_find) >= 1

    # 3. list
    res_list = await tool.execute(action="list", sub_dir="unified_test_dir")
    assert any("sample.txt" in f["path"] for f in res_list)

    # 4. create_zip
    res_zip = await tool.execute(action="create_zip", sources=["unified_test_dir"], zip_name="test_bundle.zip")
    assert res_zip["success"] is True

    # 5. delete
    res_del = await tool.execute(action="delete", path="unified_test_dir/sample.txt")
    assert res_del["success"] is True

@pytest.mark.asyncio
async def test_unified_cron_scheduler():
    tool = registry.get_tool("cron_scheduler")
    assert tool is not None

    # 1. Schedule
    res = await tool.execute(
        action="schedule",
        name="test_unified_cron",
        schedule_type="interval",
        schedule_value="10m",
        target="send_channel_message",
        parameters={"channel": "telegram", "message": "hello"}
    )
    assert res["success"] is True
    job_id = res["job"]["id"]

    # 2. List
    jobs = await tool.execute(action="list")
    assert any(j["id"] == job_id for j in jobs)

    # 3. Cancel
    cancel_res = await tool.execute(action="cancel", job_id=job_id)
    assert cancel_res["success"] is True

@pytest.mark.asyncio
async def test_unified_agent_profiles():
    tool = registry.get_tool("agent_profiles")
    assert tool is not None

    # 1. List
    profiles = await tool.execute(action="list")
    assert len(profiles) >= 1

    # 2. Create
    res = await tool.execute(
        action="create",
        id="test_subagent_unified",
        name="Unified Tester",
        description="Testing unified profile tool",
        soul_prompt="You are a tester."
    )
    assert res["success"] is True

    # 3. Delete
    del_res = await tool.execute(action="delete", id="test_subagent_unified")
    assert del_res["success"] is True

@pytest.mark.asyncio
async def test_unified_skill_manager():
    tool = registry.get_tool("skill_manager")
    assert tool is not None

    # 1. List
    skills = await tool.execute(action="list")
    assert isinstance(skills, list)

@pytest.mark.asyncio
async def test_unified_coolify_and_mcp():
    coolify_tool = registry.get_tool("coolify_manager")
    assert coolify_tool is not None
    mcp_tool = registry.get_tool("mcp_client")
    assert mcp_tool is not None

    # MCP list
    mcp_servers = await mcp_tool.execute(action="list")
    assert isinstance(mcp_servers, list)

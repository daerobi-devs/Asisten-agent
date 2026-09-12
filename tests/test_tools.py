import pytest
from lxion.tools.registry import registry

@pytest.mark.asyncio
async def test_tool_registry():
    tools = registry.get_all_tools()
    assert len(tools) >= 5
    
    openai_tools = registry.get_openai_tools()
    assert len(openai_tools) >= 5
    assert all("function" in t for t in openai_tools)

@pytest.mark.asyncio
async def test_execute_tool():
    # Test writing and reading via registry
    write_res = await registry.execute_tool_call(
        "write_file",
        '{"path": "tool_test.txt", "content": "Tool registry testing."}'
    )
    assert "Successfully written" in write_res

    read_res = await registry.execute_tool_call(
        "read_file",
        '{"path": "tool_test.txt"}'
    )
    assert read_res == "Tool registry testing."

    # Clean up
    await registry.execute_tool_call(
        "delete_file",
        '{"path": "tool_test.txt"}'
    )
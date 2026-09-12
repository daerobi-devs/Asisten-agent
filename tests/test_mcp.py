import asyncio
import json
import sys
import pytest
from pathlib import Path
from lxion.mcp.client import MCPClientManager
from lxion.tools.registry import ToolRegistry

MOCK_MCP_SERVER_CODE = """
import sys
import json

def handle():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            method = req.get("method")
            req_id = req.get("id")

            if method == "initialize":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "mock-mcp-server", "version": "1.0.0"}
                    }
                }
                sys.stdout.write(json.dumps(res) + "\\n")
                sys.stdout.flush()

            elif method == "notifications/initialized":
                pass

            elif method == "tools/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "get_weather",
                                "description": "Get current weather for a city",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"city": {"type": "string"}},
                                    "required": ["city"]
                                }
                            }
                        ]
                    }
                }
                sys.stdout.write(json.dumps(res) + "\\n")
                sys.stdout.flush()

            elif method == "tools/call":
                city = req.get("params", {}).get("arguments", {}).get("city", "Unknown")
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Weather in {city}: 27C Sunny"}]
                    }
                }
                sys.stdout.write(json.dumps(res) + "\\n")
                sys.stdout.flush()

        except Exception as e:
            sys.stderr.write(f"Error: {e}\\n")
            sys.stderr.flush()

if __name__ == "__main__":
    handle()
"""

@pytest.mark.asyncio
async def test_mcp_client_stdio(tmp_path):
    server_script = tmp_path / "mock_mcp.py"
    server_script.write_text(MOCK_MCP_SERVER_CODE, encoding="utf-8")

    manager = MCPClientManager()
    custom_registry = ToolRegistry()

    # Register server
    tool_names = await manager.register_server(
        name="weather_srv",
        command=sys.executable,
        args=[str(server_script)],
        tool_registry=custom_registry
    )

    assert "mcp_weather_srv_get_weather" in tool_names
    assert len(manager.list_connected_servers()) == 1

    # Execute tool through registry
    call_res = await custom_registry.execute_tool_call(
        "mcp_weather_srv_get_weather",
        '{"city": "Jakarta"}'
    )
    assert "Weather in Jakarta: 27C Sunny" in call_res

    # Cleanup
    await manager.stop_all()
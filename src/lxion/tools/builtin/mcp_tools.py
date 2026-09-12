from typing import Dict, Any, List, Optional
from lxion.tools.base import BaseTool
from lxion.mcp.client import mcp_manager
from lxion.core.logger import logger

class ConnectMCPServerTool(BaseTool):
    name = "mcp_connect_server"
    description = "Connect to an external MCP (Model Context Protocol) server over stdio and register its tools automatically."
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Identifier name for the MCP server (e.g. 'filesystem' or 'github')."
            },
            "command": {
                "type": "string",
                "description": "Executable command (e.g. 'npx', 'uvx', 'python')."
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Arguments for the command."
            }
        },
        "required": ["name", "command", "args"]
    }

    async def execute(self, name: str, command: str, args: List[str], **kwargs) -> Dict[str, Any]:
        from lxion.tools.registry import registry
        try:
            registered_tools = await mcp_manager.register_server(
                name=name,
                command=command,
                args=args,
                tool_registry=registry
            )
            return {
                "success": True,
                "server_name": name,
                "tools_registered": registered_tools
            }
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {name}: {e}")
            return {"success": False, "error": str(e)}

class ListMCPServersTool(BaseTool):
    name = "mcp_list_servers"
    description = "List all currently connected MCP servers and their available tools."
    parameters = {
        "type": "object",
        "properties": {}
    }

    async def execute(self, **kwargs) -> List[Dict[str, Any]]:
        return mcp_manager.list_connected_servers()

class MCPClientTool(BaseTool):
    name = "mcp_client"
    description = (
        "Unified Model Context Protocol (MCP) manager. Supported actions: "
        "'list' (show all connected MCP servers and their tools), "
        "'connect' (spawn MCP server process over stdio and register tools)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "connect"],
                "description": "MCP operation to perform."
            },
            "name": {
                "type": "string",
                "description": "Identifier name for the MCP server (e.g. 'filesystem' or 'github') for 'connect'."
            },
            "command": {
                "type": "string",
                "description": "Executable command (e.g. 'npx', 'uvx', 'python') for 'connect'."
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Arguments for the command (for 'connect')."
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        name: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        **kwargs
    ) -> Any:
        act = action.strip().lower()
        if act == "list":
            return mcp_manager.list_connected_servers()
        elif act == "connect":
            if not name or not command:
                return {"success": False, "error": "Parameters 'name' and 'command' are required for 'connect' action."}
            from lxion.tools.registry import registry
            try:
                registered_tools = await mcp_manager.register_server(
                    name=name,
                    command=command,
                    args=args or [],
                    tool_registry=registry
                )
                return {
                    "success": True,
                    "server_name": name,
                    "tools_registered": registered_tools
                }
            except Exception as e:
                logger.error(f"Failed to connect to MCP server {name}: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": f"Unknown MCP action: '{action}'. Choose: 'list', 'connect'."}
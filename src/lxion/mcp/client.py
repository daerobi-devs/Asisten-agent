import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional
from lxion.core.logger import logger, AuditLogger
from lxion.tools.base import BaseTool

class MCPToolAdapter(BaseTool):
    def __init__(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        parameters: Dict[str, Any],
        mcp_client: "MCPStdioClient"
    ):
        self.server_name = server_name
        self.original_name = tool_name
        self.name = f"mcp_{server_name}_{tool_name}".replace("-", "_")
        self.description = f"[MCP: {server_name}] {description}"
        self.parameters = parameters or {"type": "object", "properties": {}}
        self.mcp_client = mcp_client

    async def execute(self, **kwargs) -> Any:
        AuditLogger.log_event("MCP_TOOL_CALL", "agent", {
            "server": self.server_name,
            "tool": self.original_name,
            "args": kwargs
        })
        return await self.mcp_client.call_tool(self.original_name, kwargs)

class MCPStdioClient:
    def __init__(self, server_name: str, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        self.server_name = server_name
        self.command = command
        self.args = args
        self.env = env or {}
        self.process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._read_task: Optional[asyncio.Task] = None
        self.discovered_tools: List[Dict[str, Any]] = []

    async def start(self):
        """Spawn the MCP server process over stdio."""
        import os
        full_env = os.environ.copy()
        full_env.update(self.env)

        cmd = [self.command] + self.args
        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env
            )
            self._read_task = asyncio.create_task(self._listen_stdout())
            logger.info(f"✓ Started MCP server '{self.server_name}' [PID {self.process.pid}]")
            
            # Initialize handshake
            await self._initialize()
        except Exception as e:
            logger.error(f"Failed to start MCP server '{self.server_name}': {e}")
            raise

    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self._request_id += 1
        req_id = self._request_id
        req_payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {}
        }
        
        fut = asyncio.get_event_loop().create_future()
        self._pending_requests[req_id] = fut
        
        line = json.dumps(req_payload) + "\n"
        if self.process and self.process.stdin:
            self.process.stdin.write(line.encode("utf-8"))
            await self.process.stdin.drain()
        else:
            raise RuntimeError(f"MCP server '{self.server_name}' stdin not available.")

        try:
            res = await asyncio.wait_for(fut, timeout=30.0)
            return res
        finally:
            self._pending_requests.pop(req_id, None)

    async def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        line = json.dumps(payload) + "\n"
        if self.process and self.process.stdin:
            self.process.stdin.write(line.encode("utf-8"))
            await self.process.stdin.drain()

    async def _listen_stdout(self):
        while self.process and self.process.stdout and not self.process.stdout.at_eof():
            try:
                raw_line = await self.process.stdout.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    req_id = data.get("id")
                    if req_id is not None and req_id in self._pending_requests:
                        fut = self._pending_requests[req_id]
                        if "error" in data:
                            fut.set_exception(RuntimeError(data["error"]))
                        else:
                            fut.set_result(data.get("result"))
                except json.JSONDecodeError:
                    continue
            except Exception as e:
                break

    async def _initialize(self):
        # 1. initialize
        init_res = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "LXION-Agent", "version": "0.3.0"}
        })
        # 2. initialized notification
        await self._send_notification("notifications/initialized")
        logger.info(f"✓ MCP handshake complete for '{self.server_name}'")

    async def list_tools(self) -> List[Dict[str, Any]]:
        res = await self._send_request("tools/list", {})
        self.discovered_tools = res.get("tools", []) if isinstance(res, dict) else []
        return self.discovered_tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        res = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        if isinstance(res, dict) and "content" in res:
            content_items = res.get("content", [])
            texts = [c.get("text", "") for c in content_items if c.get("type") == "text"]
            return "\n".join(texts) if texts else res
        return res

    async def stop(self):
        if self._read_task:
            self._read_task.cancel()
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except Exception:
                pass
            logger.info(f"✓ Stopped MCP server '{self.server_name}'")

class MCPClientManager:
    def __init__(self):
        self.servers: Dict[str, MCPStdioClient] = {}
        self.adapters: Dict[str, MCPToolAdapter] = {}

    async def register_server(
        self,
        name: str,
        command: str,
        args: List[str],
        tool_registry,
        env: Optional[Dict[str, str]] = None
    ) -> List[str]:
        """Start server, discover tools, and register into agent ToolRegistry."""
        client = MCPStdioClient(server_name=name, command=command, args=args, env=env)
        await client.start()
        self.servers[name] = client

        tools_meta = await client.list_tools()
        registered_names = []
        for t in tools_meta:
            t_name = t.get("name")
            desc = t.get("description", "")
            schema = t.get("inputSchema", {})
            adapter = MCPToolAdapter(
                server_name=name,
                tool_name=t_name,
                description=desc,
                parameters=schema,
                mcp_client=client
            )
            tool_registry.register_tool(adapter)
            self.adapters[adapter.name] = adapter
            registered_names.append(adapter.name)

        logger.info(f"✓ Registered {len(registered_names)} MCP tools from server '{name}': {registered_names}")
        return registered_names

    def list_connected_servers(self) -> List[Dict[str, Any]]:
        return [
            {
                "server_name": name,
                "command": s.command,
                "tools_count": len(s.discovered_tools),
                "tools": [t.get("name") for t in s.discovered_tools]
            }
            for name, s in self.servers.items()
        ]

    async def stop_all(self):
        for s in self.servers.values():
            await s.stop()
        self.servers.clear()
        self.adapters.clear()

mcp_manager = MCPClientManager()
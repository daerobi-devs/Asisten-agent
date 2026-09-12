import json
import inspect
from typing import Dict, List, Optional, Any
from lxion.tools.base import BaseTool
from lxion.tools.builtin.file_ops import (
    ReadFileTool, WriteFileTool, ListFilesTool, DeleteFileTool,
    MakeDirectoryTool, FindFilesTool, CreateZipTool, SendFileToChannelTool,
    WorkspaceOpsTool
)
from lxion.tools.builtin.shell_exec import ShellExecTool
from lxion.tools.builtin.web_search import FetchUrlTool
from lxion.tools.builtin.coding import RunCodeTool, EditFileTool, WorkspaceGitTool
from lxion.tools.builtin.skill_tools import (
    InstallSkillTool, ListSkillsTool, ScanSkillTool, SkillManagerTool
)
from lxion.tools.builtin.browser_tools import (
    BrowserNavigateTool, BrowserGetContentTool, BrowserClickTool,
    BrowserFillTool, BrowserScreenshotTool, WebBrowserTool
)
from lxion.tools.builtin.mcp_tools import (
    ConnectMCPServerTool, ListMCPServersTool, MCPClientTool
)
from lxion.tools.builtin.scheduler_tools import (
    ScheduleJobTool, SendChannelMessageTool, ListJobsTool, CancelJobTool, GetJobHistoryTool,
    CronSchedulerTool
)
from lxion.tools.builtin.kanban_tools import (
    KanbanCreateTaskTool, KanbanUpdateTaskTool, KanbanGetBoardTool, KanbanBreakdownTool,
    KanbanManagerTool
)
from lxion.tools.builtin.companion_tools import (
    LaptopStatusTool, LaptopScreenshotTool, LaptopReadFileTool,
    LaptopListFilesTool, LaptopExecCommandTool, LaptopCompanionTool
)
from lxion.tools.builtin.coolify_tools import (
    CoolifyDeployTool, CoolifyListAppsTool, CoolifyManagerTool
)
from lxion.agents.agent_factory import (
    CreateAgentProfileTool, UpdateAgentProfileTool,
    ListAgentProfilesTool, DeleteAgentProfileTool, AgentProfilesTool
)
from lxion.tools.builtin.google_workspace_tool import GoogleWorkspaceTool
from lxion.core.logger import logger

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._legacy_tools: Dict[str, BaseTool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        # 1. Primary Unified & Essential High-Speed Tools (Exposed to LLM Prompt)
        primary_tools = [
            # Core Coding Primitives & File IO
            ReadFileTool(),
            WriteFileTool(),
            EditFileTool(),
            WorkspaceOpsTool(),
            RunCodeTool(),
            ShellExecTool(),
            WorkspaceGitTool(),
            FetchUrlTool(),
            # Multi-Service Unified Tools (Ultra Token-Efficient)
            GoogleWorkspaceTool(),
            KanbanManagerTool(),
            LaptopCompanionTool(),
            WebBrowserTool(),
            AgentProfilesTool(),
            SkillManagerTool(),
            CronSchedulerTool(),
            SendChannelMessageTool(),
            CoolifyManagerTool(),
            MCPClientTool(),
        ]
        for tool in primary_tools:
            self.register_tool(tool)

        # 2. Legacy Standalone Tools (Preserved for backwards compatibility with tests/scripts)
        legacy_tools = [
            ListFilesTool(),
            DeleteFileTool(),
            MakeDirectoryTool(),
            FindFilesTool(),
            CreateZipTool(),
            SendFileToChannelTool(),
            InstallSkillTool(),
            ListSkillsTool(),
            ScanSkillTool(),
            BrowserNavigateTool(),
            BrowserGetContentTool(),
            BrowserClickTool(),
            BrowserFillTool(),
            BrowserScreenshotTool(),
            ConnectMCPServerTool(),
            ListMCPServersTool(),
            ScheduleJobTool(),
            ListJobsTool(),
            CancelJobTool(),
            GetJobHistoryTool(),
            KanbanCreateTaskTool(),
            KanbanUpdateTaskTool(),
            KanbanGetBoardTool(),
            KanbanBreakdownTool(),
            LaptopStatusTool(),
            LaptopScreenshotTool(),
            LaptopReadFileTool(),
            LaptopListFilesTool(),
            LaptopExecCommandTool(),
            CoolifyDeployTool(),
            CoolifyListAppsTool(),
            CreateAgentProfileTool(),
            UpdateAgentProfileTool(),
            ListAgentProfilesTool(),
            DeleteAgentProfileTool(),
        ]
        for tool in legacy_tools:
            self._legacy_tools[tool.name] = tool

    def register_tool(self, tool: BaseTool):
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def unregister_tool(self, name: str):
        if name in self._tools:
            del self._tools[name]
        if name in self._legacy_tools:
            del self._legacy_tools[name]

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name) or self._legacy_tools.get(name)

    def get_all_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_openai_tools(self, filter_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Return tools formatted for OpenAI function calling, optionally filtered for a specific agent profile."""
        if not filter_names or "*" in filter_names or "all" in filter_names:
            return [tool.to_openai_tool() for tool in self._tools.values()]
        
        allowed = set(filter_names)
        return [tool.to_openai_tool() for name, tool in self._tools.items() if name in allowed]

    async def execute_tool_call(
        self,
        name: str,
        arguments_json: str,
        allowed_tools: Optional[List[str]] = None
    ) -> Any:
        if allowed_tools and "*" not in allowed_tools and "all" not in allowed_tools and name not in allowed_tools:
            return {"error": f"Tool '{name}' is not permitted for this agent profile."}

        tool = self.get_tool(name)
        if not tool:
            return {"error": f"Tool '{name}' is not registered."}
        
        try:
            kwargs = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON arguments: {e}"}

        try:
            sig = inspect.signature(tool.execute)
            has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            
            if has_var_keyword:
                call_kwargs = kwargs
            else:
                accepted_params = set(sig.parameters.keys())
                call_kwargs = {k: v for k, v in kwargs.items() if k in accepted_params}

            result = await tool.execute(**call_kwargs)
            return result
        except Exception as e:
            logger.error(f"Error executing tool '{name}': {e}")
            return {"error": str(e)}

registry = ToolRegistry()
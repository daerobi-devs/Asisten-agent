from typing import Dict, Any, Optional
from lxion.tools.base import BaseTool
from lxion.companion.client import laptop_client

class LaptopStatusTool(BaseTool):
    name = "laptop_status"
    description = "Check the health, CPU, RAM, and online status of your Windows laptop companion via Tailscale."
    parameters = {
        "type": "object",
        "properties": {}
    }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        return await laptop_client.get_status()

class LaptopScreenshotTool(BaseTool):
    name = "laptop_screenshot"
    description = "Take a live screenshot of your Windows laptop desktop and save it to the workspace via Tailscale."
    parameters = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Optional custom filename for the saved screenshot (e.g. 'desktop_capture.png')."
            }
        }
    }

    async def execute(self, filename: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        return await laptop_client.capture_screenshot(filename)

class LaptopReadFileTool(BaseTool):
    name = "laptop_read_file"
    description = "Read a file from whitelisted folders (Documents, Desktop, Downloads) on your Windows laptop."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path on the Windows laptop (e.g. 'C:\\Users\\ADVAN\\Documents\\notes.txt')."
            }
        },
        "required": ["path"]
    }

    async def execute(self, path: str, **kwargs) -> Dict[str, Any]:
        return await laptop_client.read_file(path)

class LaptopListFilesTool(BaseTool):
    name = "laptop_list_files"
    description = "List files inside a whitelisted folder on your Windows laptop."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path on Windows laptop (e.g. 'C:\\Users\\ADVAN\\Documents')."
            }
        },
        "required": ["path"]
    }

    async def execute(self, path: str, **kwargs) -> Dict[str, Any]:
        return await laptop_client.list_files(path)

class LaptopExecCommandTool(BaseTool):
    name = "laptop_exec_command"
    description = "Run an allowed whitelist command on your Windows laptop (e.g. 'dir', 'systeminfo', 'git status')."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Whitelisted command to execute on laptop."
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Execution timeout in seconds (default 30)."
            }
        },
        "required": ["command"]
    }

    async def execute(self, command: str, timeout_seconds: int = 30, **kwargs) -> Dict[str, Any]:
        return await laptop_client.execute_command(command, timeout_seconds)

class LaptopCompanionTool(BaseTool):
    name = "laptop_companion"
    description = (
        "All-in-one controller for your Windows companion laptop via Tailscale. "
        "Supported actions: 'status' (health, CPU, RAM, battery), 'screenshot' (capture desktop), "
        "'read_file' (read file from whitelisted path), 'list_files' (list folder contents), "
        "'exec_command' (run whitelisted system/cli command)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "screenshot", "read_file", "list_files", "exec_command"],
                "description": "Operation to perform on the laptop."
            },
            "path": {
                "type": "string",
                "description": "Path on Windows laptop (e.g. 'C:\\Users\\ADVAN\\Documents') for 'read_file' or 'list_files'."
            },
            "command": {
                "type": "string",
                "description": "Whitelisted command to execute on laptop (for 'exec_command')."
            },
            "filename": {
                "type": "string",
                "description": "Optional custom filename for the saved screenshot (for 'screenshot')."
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Command execution timeout in seconds (default 30)."
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        path: Optional[str] = None,
        command: Optional[str] = None,
        filename: Optional[str] = None,
        timeout_seconds: int = 30,
        **kwargs
    ) -> Dict[str, Any]:
        act = action.strip().lower()
        if act == "status":
            return await laptop_client.get_status()
        elif act == "screenshot":
            return await laptop_client.capture_screenshot(filename)
        elif act == "read_file":
            if not path:
                return {"success": False, "error": "Parameter 'path' is required for 'read_file' action."}
            return await laptop_client.read_file(path)
        elif act == "list_files":
            if not path:
                return {"success": False, "error": "Parameter 'path' is required for 'list_files' action."}
            return await laptop_client.list_files(path)
        elif act == "exec_command":
            if not command:
                return {"success": False, "error": "Parameter 'command' is required for 'exec_command' action."}
            return await laptop_client.execute_command(command, timeout_seconds)
        else:
            return {"success": False, "error": f"Unknown laptop action: '{action}'. Choose: 'status', 'screenshot', 'read_file', 'list_files', 'exec_command'."}
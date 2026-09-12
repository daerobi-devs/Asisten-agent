import asyncio
from typing import Dict, Any
from lxion.tools.base import BaseTool
from lxion.core.config import settings
from lxion.core.logger import AuditLogger

class ShellExecTool(BaseTool):
    name = "execute_command"
    description = "Run a terminal/shell command inside the workspace environment with timeout."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to run."
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Timeout in seconds (default 30, max 120)."
            }
        },
        "required": ["command"]
    }

    async def execute(self, command: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        timeout = min(max(timeout_seconds, 1), 120)
        AuditLogger.log_event("SHELL_EXEC", "agent", {"command": command, "timeout": timeout})
        
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=str(settings.WORKSPACE_DIR.resolve()),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_data, stderr_data = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(timeout)
            )
            return {
                "exit_code": proc.returncode,
                "stdout": stdout_data.decode("utf-8", errors="replace"),
                "stderr": stderr_data.decode("utf-8", errors="replace")
            }
        except asyncio.TimeoutError:
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            return {
                "exit_code": -1,
                "error": f"Command timed out after {timeout} seconds."
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "error": str(e)
            }
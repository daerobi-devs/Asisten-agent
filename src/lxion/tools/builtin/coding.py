from typing import Dict, Any, List, Optional
from lxion.tools.base import BaseTool
from lxion.sandbox.runner import sandbox
from lxion.memory.workspace import workspace
from lxion.memory.git_versioning import workspace_git
from lxion.core.logger import AuditLogger

class RunCodeTool(BaseTool):
    name = "run_code"
    description = "Execute a block of code (Python, JavaScript, Bash, PowerShell) inside the isolated workspace sandbox."
    parameters = {
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "enum": ["python", "javascript", "bash", "powershell"],
                "description": "Programming language / runtime interpreter."
            },
            "code": {
                "type": "string",
                "description": "Complete source code string to execute."
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Maximum execution time in seconds (default 30, max 120)."
            }
        },
        "required": ["language", "code"]
    }

    async def execute(self, language: str, code: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        result = await sandbox.execute_code(language=language, code=code, timeout_seconds=timeout_seconds)
        return result.to_dict()

class EditFileTool(BaseTool):
    name = "edit_file"
    description = "Perform a search-and-replace modification on an existing workspace file."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the workspace file."
            },
            "target_content": {
                "type": "string",
                "description": "The exact string block in the file to replace."
            },
            "replacement_content": {
                "type": "string",
                "description": "The new replacement string block."
            }
        },
        "required": ["path", "target_content", "replacement_content"]
    }

    async def execute(self, path: str, target_content: str, replacement_content: str) -> Dict[str, Any]:
        try:
            original = workspace.read_file(path)
            if target_content not in original:
                return {
                    "success": False,
                    "error": f"Target content not found in '{path}'. Please ensure exact whitespace matching."
                }
            
            # Perform single replacement
            updated = original.replace(target_content, replacement_content, 1)
            workspace.write_file(path, updated)
            AuditLogger.log_event("WORKSPACE_EDIT", "agent", {
                "path": path,
                "target_len": len(target_content),
                "replacement_len": len(replacement_content)
            })
            return {
                "success": True,
                "message": f"Successfully updated '{path}'."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

class WorkspaceGitTool(BaseTool):
    name = "workspace_git"
    description = "Manage Git version control in the workspace: status, commit, diff, or history."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "commit", "diff", "history"],
                "description": "Git operation to execute."
            },
            "message": {
                "type": "string",
                "description": "Commit message (required for 'commit' action)."
            },
            "limit": {
                "type": "integer",
                "description": "Limit of commit logs for 'history' (default 10)."
            }
        },
        "required": ["action"]
    }

    async def execute(self, action: str, message: Optional[str] = None, limit: int = 10) -> Any:
        action = action.lower()
        if action == "status":
            return await workspace_git.status()
        elif action == "commit":
            if not message:
                return {"error": "Commit message is required for action 'commit'."}
            return await workspace_git.commit(message)
        elif action == "diff":
            return await workspace_git.diff()
        elif action == "history":
            return await workspace_git.history(limit=limit)
        else:
            return {"error": f"Unknown git action '{action}'."}
import asyncio
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger

class WorkspaceGit:
    def __init__(self, workspace_dir: Optional[Path] = None):
        self.workspace = (workspace_dir or settings.WORKSPACE_DIR).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._ensure_git_init()

    def _ensure_git_init(self):
        git_dir = self.workspace / ".git"
        if not git_dir.exists():
            try:
                import subprocess
                subprocess.run(["git", "init"], cwd=str(self.workspace), capture_output=True, check=True)
                subprocess.run(["git", "config", "user.name", "LXION Agent"], cwd=str(self.workspace), capture_output=True)
                subprocess.run(["git", "config", "user.email", "agent@lxion.local"], cwd=str(self.workspace), capture_output=True)
                logger.info("✓ Workspace internal git tracking initialized.")
            except Exception as e:
                logger.warning(f"Git init skipped or failed in workspace: {e}")

    async def _run_git_cmd(self, args: List[str]) -> Dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", *args,
                cwd=str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return {
                "exit_code": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace").strip(),
                "stderr": stderr.decode("utf-8", errors="replace").strip()
            }
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}

    async def status(self) -> Dict[str, Any]:
        return await self._run_git_cmd(["status", "--short"])

    async def commit(self, message: str) -> Dict[str, Any]:
        await self._run_git_cmd(["add", "-A"])
        res = await self._run_git_cmd(["commit", "-m", message])
        AuditLogger.log_event("WORKSPACE_GIT_COMMIT", "agent", {"message": message, "result": res.get("stdout")})
        return res

    async def diff(self) -> str:
        res = await self._run_git_cmd(["diff"])
        return res.get("stdout", "")

    async def history(self, limit: int = 10) -> List[Dict[str, str]]:
        res = await self._run_git_cmd(["log", f"-n{limit}", "--pretty=format:%h|%an|%ad|%s", "--date=short"])
        output = res.get("stdout", "")
        if not output:
            return []
        commits = []
        for line in output.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3]
                })
        return commits

workspace_git = WorkspaceGit()
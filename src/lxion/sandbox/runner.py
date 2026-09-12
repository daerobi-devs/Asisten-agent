import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger

class SandboxResult:
    def __init__(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        execution_time_ms: float,
        timed_out: bool = False
    ):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.execution_time_ms = execution_time_ms
        self.timed_out = timed_out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "timed_out": self.timed_out
        }

class CodeSandbox:
    def __init__(self, workspace_dir: Optional[Path] = None):
        self.workspace = (workspace_dir or settings.WORKSPACE_DIR).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    async def execute_code(
        self,
        language: str,
        code: str,
        timeout_seconds: int = 30
    ) -> SandboxResult:
        """Execute a code snippet in an isolated subprocess within the workspace."""
        language = language.lower().strip()
        timeout = min(max(timeout_seconds, 1), 120)
        
        # Select runtime interpreter
        if language in ("python", "py", "python3"):
            ext = ".py"
            cmd_prefix = [sys.executable]
        elif language in ("javascript", "js", "node"):
            ext = ".js"
            cmd_prefix = ["node"]
        elif language in ("bash", "sh"):
            ext = ".sh"
            cmd_prefix = ["bash"]
        elif language in ("powershell", "ps1"):
            ext = ".ps1"
            cmd_prefix = ["powershell", "-ExecutionPolicy", "Bypass", "-File"]
        else:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"Unsupported language '{language}'. Supported: python, javascript, bash, powershell.",
                execution_time_ms=0.0
            )

        # Write code to a temporary runner script inside workspace/
        temp_file = self.workspace / f"_sandbox_run_{int(time.time()*1000)}{ext}"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(code)

            AuditLogger.log_event("SANDBOX_EXECUTE", "agent", {
                "language": language,
                "script": temp_file.name,
                "bytes": len(code)
            })

            start_time = time.time()
            # Prepare isolated environment
            safe_env = os.environ.copy()
            safe_env["PYTHONUNBUFFERED"] = "1"
            safe_env["PYTHONDONTWRITEBYTECODE"] = "1"

            cmd = cmd_prefix + [str(temp_file.resolve())]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=safe_env
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(timeout)
                )
                duration_ms = (time.time() - start_time) * 1000
                return SandboxResult(
                    exit_code=proc.returncode or 0,
                    stdout=stdout_bytes.decode("utf-8", errors="replace"),
                    stderr=stderr_bytes.decode("utf-8", errors="replace"),
                    execution_time_ms=duration_ms
                )
            except asyncio.TimeoutError:
                if proc:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                duration_ms = (time.time() - start_time) * 1000
                return SandboxResult(
                    exit_code=-1,
                    stdout="",
                    stderr=f"Execution timed out after {timeout} seconds.",
                    execution_time_ms=duration_ms,
                    timed_out=True
                )
        except Exception as e:
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time_ms=0.0
            )
        finally:
            # Clean up temporary script
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

sandbox = CodeSandbox()
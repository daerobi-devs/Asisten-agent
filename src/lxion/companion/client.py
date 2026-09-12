import time
import httpx
from pathlib import Path
from typing import Dict, Any, Optional
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger

class LaptopCompanionClient:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        auth_token: Optional[str] = None
    ):
        self.host = host or settings.COMPANION_HOST or "127.0.0.1"
        self.port = port or settings.COMPANION_PORT
        self.auth_token = auth_token or settings.COMPANION_AUTH_TOKEN or "lxion_tailscale_secret_2026"
        self.base_url = f"http://{self.host}:{self.port}"

    def _headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "LXION-Core-Tailscale/0.3.0"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def get_status(self) -> Dict[str, Any]:
        url = f"{self.base_url}/status"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=self._headers())
                if res.status_code == 200:
                    return res.json()
                return {"status": "offline", "error": f"HTTP {res.status_code}: {res.text}"}
        except Exception as e:
            return {"status": "offline", "error": str(e)}

    async def capture_screenshot(self, filename: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/screenshot"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url, headers=self._headers())
                if res.status_code == 200:
                    screenshots_dir = settings.WORKSPACE_DIR / "laptop_screenshots"
                    screenshots_dir.mkdir(parents=True, exist_ok=True)
                    fname = filename or f"laptop_screen_{int(time.time()*1000)}.png"
                    if not fname.endswith(".png"):
                        fname += ".png"
                    save_path = screenshots_dir / fname
                    save_path.write_bytes(res.content)
                    
                    rel_path = f"laptop_screenshots/{fname}"
                    AuditLogger.log_event("LAPTOP_SCREENSHOT", "agent", {"path": rel_path})
                    return {
                        "success": True,
                        "saved_path": rel_path,
                        "bytes": len(res.content)
                    }
                return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def list_files(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}/files/list"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=self._headers(), json={"path": path})
                if res.status_code == 200:
                    return res.json()
                return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def read_file(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}/files/read"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=self._headers(), json={"path": path})
                if res.status_code == 200:
                    return res.json()
                return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_command(self, command: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        url = f"{self.base_url}/exec"
        AuditLogger.log_event("LAPTOP_EXEC_COMMAND", "agent", {"command": command})
        try:
            async with httpx.AsyncClient(timeout=float(timeout_seconds + 5)) as client:
                res = await client.post(
                    url,
                    headers=self._headers(),
                    json={"command": command, "timeout_seconds": timeout_seconds}
                )
                if res.status_code == 200:
                    return res.json()
                return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

laptop_client = LaptopCompanionClient()
import os
import httpx
from typing import Dict, Any, List, Optional
from lxion.core.logger import logger, AuditLogger

class CoolifyClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_token: Optional[str] = None
    ):
        self.base_url = (base_url or os.getenv("COOLIFY_BASE_URL", "")).rstrip("/")
        self.api_token = api_token or os.getenv("COOLIFY_API_TOKEN", "")

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_token)

    async def list_applications(self) -> List[Dict[str, Any]]:
        if not self.is_configured():
            return []
        url = f"{self.base_url}/api/v1/applications"
        try:
            async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
                res = await client.get(url, headers=self._headers())
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"Coolify list apps failed: {res.status_code} - {res.text}")
                return []
        except Exception as e:
            logger.error(f"Coolify API error: {e}")
            return []

    async def trigger_deploy(self, app_uuid: str) -> Dict[str, Any]:
        """Trigger deployment of an application by its Coolify UUID."""
        if not self.is_configured():
            return {"success": False, "error": "Coolify credentials not configured (COOLIFY_BASE_URL / COOLIFY_API_TOKEN)."}
        
        url = f"{self.base_url}/api/v1/deploy"
        params = {"uuid": app_uuid}
        AuditLogger.log_event("COOLIFY_DEPLOY_TRIGGER", "agent", {"app_uuid": app_uuid})
        try:
            async with httpx.AsyncClient(timeout=20.0, verify=False) as client:
                res = await client.post(url, headers=self._headers(), params=params)
                if res.status_code in (200, 201, 202):
                    return {"success": True, "data": res.json()}
                return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

coolify_client = CoolifyClient()
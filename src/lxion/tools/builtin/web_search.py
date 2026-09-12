import httpx
from typing import Dict, Any
from lxion.tools.base import BaseTool

class FetchUrlTool(BaseTool):
    name = "fetch_url"
    description = "Fetch webpage content from a public URL."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch."
            }
        },
        "required": ["url"]
    }

    async def execute(self, url: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                res = await client.get(url, headers={"User-Agent": "LXION-Agent/0.3.0"})
                return {
                    "status_code": res.status_code,
                    "text": res.text[:10000],  # Scoped first 10k chars to avoid token explosion
                    "content_type": res.headers.get("content-type", "")
                }
        except Exception as e:
            return {"error": str(e)}
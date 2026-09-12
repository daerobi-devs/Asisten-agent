import asyncio
import time
from pathlib import Path
from typing import Dict, Any, Optional
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger
from lxion.tools.base import BaseTool

class BrowserController:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()

    async def _ensure_page(self):
        from playwright.async_api import async_playwright
        if self._page is None or self._page.is_closed():
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            if self._browser is None:
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            self._page = await self._context.new_page()
        return self._page

    async def navigate(self, url: str) -> Dict[str, Any]:
        async with self._lock:
            try:
                page = await self._ensure_page()
                res = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                title = await page.title()
                AuditLogger.log_event("BROWSER_NAVIGATE", "agent", {"url": url, "title": title})
                return {
                    "success": True,
                    "url": page.url,
                    "title": title,
                    "status": res.status if res else 200
                }
            except Exception as e:
                logger.error(f"Browser navigate error for {url}: {e}")
                return {"success": False, "error": str(e)}

    async def get_content(self, max_length: int = 8000) -> Dict[str, Any]:
        async with self._lock:
            try:
                page = await self._ensure_page()
                title = await page.title()
                text = await page.evaluate("() => document.body.innerText")
                clean_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
                return {
                    "url": page.url,
                    "title": title,
                    "content": clean_text[:max_length]
                }
            except Exception as e:
                return {"error": str(e)}

    async def click(self, selector: str) -> Dict[str, Any]:
        async with self._lock:
            try:
                page = await self._ensure_page()
                await page.click(selector, timeout=10000)
                AuditLogger.log_event("BROWSER_CLICK", "agent", {"selector": selector})
                return {"success": True, "message": f"Clicked element '{selector}'."}
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def fill(self, selector: str, value: str) -> Dict[str, Any]:
        async with self._lock:
            try:
                page = await self._ensure_page()
                await page.fill(selector, value, timeout=10000)
                AuditLogger.log_event("BROWSER_FILL", "agent", {"selector": selector})
                return {"success": True, "message": f"Filled element '{selector}' with value."}
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def screenshot(self, filename: Optional[str] = None) -> Dict[str, Any]:
        async with self._lock:
            try:
                page = await self._ensure_page()
                screenshots_dir = settings.WORKSPACE_DIR / "screenshots"
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                
                fname = filename or f"screenshot_{int(time.time()*1000)}.png"
                if not fname.endswith(".png"):
                    fname += ".png"
                
                target_path = screenshots_dir / fname
                await page.screenshot(path=str(target_path), full_page=False)
                
                rel_path = f"screenshots/{fname}"
                AuditLogger.log_event("BROWSER_SCREENSHOT", "agent", {"path": rel_path})
                return {
                    "success": True,
                    "saved_path": rel_path,
                    "message": f"Screenshot saved to workspace at '{rel_path}'."
                }
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def close(self):
        async with self._lock:
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
            self._browser = None
            self._playwright = None
            self._page = None

browser_controller = BrowserController()
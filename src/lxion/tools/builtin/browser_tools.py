from typing import Dict, Any, Optional
from lxion.tools.base import BaseTool
from lxion.browser.browser_tool import browser_controller

class BrowserNavigateTool(BaseTool):
    name = "browser_navigate"
    description = "Navigate the headless browser to a specified URL."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL including http/https protocol."
            }
        },
        "required": ["url"]
    }

    async def execute(self, url: str, **kwargs) -> Dict[str, Any]:
        return await browser_controller.navigate(url)

class BrowserGetContentTool(BaseTool):
    name = "browser_get_content"
    description = "Extract rendered text content and page title from the current browser page."
    parameters = {
        "type": "object",
        "properties": {
            "max_length": {
                "type": "integer",
                "description": "Maximum characters to extract (default 8000)."
            }
        }
    }

    async def execute(self, max_length: int = 8000, **kwargs) -> Dict[str, Any]:
        return await browser_controller.get_content(max_length=max_length)

class BrowserClickTool(BaseTool):
    name = "browser_click"
    description = "Click an element on the current browser page by CSS selector or text."
    parameters = {
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "CSS selector or text selector (e.g. 'button#submit' or 'text=Sign In')."
            }
        },
        "required": ["selector"]
    }

    async def execute(self, selector: str, **kwargs) -> Dict[str, Any]:
        return await browser_controller.click(selector)

class BrowserFillTool(BaseTool):
    name = "browser_fill"
    description = "Fill out a form field or input on the current page."
    parameters = {
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "CSS selector for input/textarea."
            },
            "value": {
                "type": "string",
                "description": "Text value to enter into the field."
            }
        },
        "required": ["selector", "value"]
    }

    async def execute(self, selector: str, value: str, **kwargs) -> Dict[str, Any]:
        return await browser_controller.fill(selector, value)

class BrowserScreenshotTool(BaseTool):
    name = "browser_screenshot"
    description = "Capture a screenshot of the current page and save it to the workspace for inspection."
    parameters = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Optional custom filename (e.g. 'homepage.png')."
            }
        }
    }

    async def execute(self, filename: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        return await browser_controller.screenshot(filename)

class WebBrowserTool(BaseTool):
    name = "web_browser"
    description = (
        "Unified Playwright web browser controller for modern interactive browsing. "
        "Supported actions: 'navigate' (open URL), 'get_content' (extract text content), "
        "'click' (click element), 'fill' (type text into form field), 'screenshot' (capture visual screenshot)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["navigate", "get_content", "click", "fill", "screenshot"],
                "description": "Browser action to execute."
            },
            "url": {
                "type": "string",
                "description": "Full URL including http/https (for 'navigate')."
            },
            "selector": {
                "type": "string",
                "description": "CSS selector or text selector (for 'click' or 'fill')."
            },
            "value": {
                "type": "string",
                "description": "Text value to type into the field (for 'fill')."
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum characters to extract (for 'get_content', default 8000)."
            },
            "filename": {
                "type": "string",
                "description": "Custom filename to save screenshot (for 'screenshot')."
            }
        },
        "required": ["action"]
    }

    async def execute(
        self,
        action: str,
        url: Optional[str] = None,
        selector: Optional[str] = None,
        value: Optional[str] = None,
        max_length: int = 8000,
        filename: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        act = action.strip().lower()
        if act == "navigate":
            if not url:
                return {"success": False, "error": "Parameter 'url' is required for 'navigate' action."}
            return await browser_controller.navigate(url)
        elif act == "get_content":
            return await browser_controller.get_content(max_length=max_length)
        elif act == "click":
            if not selector:
                return {"success": False, "error": "Parameter 'selector' is required for 'click' action."}
            return await browser_controller.click(selector)
        elif act == "fill":
            if not selector or value is None:
                return {"success": False, "error": "Parameters 'selector' and 'value' are required for 'fill' action."}
            return await browser_controller.fill(selector, value)
        elif act == "screenshot":
            return await browser_controller.screenshot(filename)
        else:
            return {"success": False, "error": f"Unknown browser action: '{action}'. Choose: 'navigate', 'get_content', 'click', 'fill', 'screenshot'."}
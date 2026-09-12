import pytest
from lxion.browser.browser_tool import browser_controller

@pytest.mark.asyncio
async def test_browser_controller_lifecycle():
    # Test navigation to a lightweight data URL
    res = await browser_controller.navigate("data:text/html,<html><head><title>LXION Test</title></head><body><h1>Hello Browser</h1><input id='inp' type='text' /></body></html>")
    assert res.get("success") is True
    assert res.get("title") == "LXION Test"

    # Test content extraction
    content = await browser_controller.get_content()
    assert "Hello Browser" in content.get("content", "")

    # Test fill form
    fill_res = await browser_controller.fill("#inp", "Testing 123")
    assert fill_res.get("success") is True

    # Test screenshot
    ss_res = await browser_controller.screenshot("test_preview.png")
    assert ss_res.get("success") is True
    assert "test_preview.png" in ss_res.get("saved_path", "")

    # Cleanup
    await browser_controller.close()
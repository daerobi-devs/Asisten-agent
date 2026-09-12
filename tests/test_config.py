import pytest
from lxion.core.config import settings

def test_settings_loaded():
    assert settings.AGENT_NAME == "LXION"
    assert settings.NINE_ROUTER_BASE_URL.startswith("http")
    assert settings.WORKSPACE_DIR is not None
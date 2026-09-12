import pytest
from fastapi.testclient import TestClient
from lxion.main import app

client = TestClient(app)

def test_web_ui_dashboard_serving():
    # 1. Test root dashboard
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "LXION" in res_root.text
    assert "Autonomous Agentic Studio" in res_root.text

    # 2. Test /dashboard route
    res_dash = client.get("/dashboard")
    assert res_dash.status_code == 200
    assert "9Router" in res_dash.text

def test_web_api_endpoints():
    # Health
    res_health = client.get("/health")
    assert res_health.status_code == 200
    data = res_health.json()
    assert data["status"] == "healthy"
    assert data["active_tools"] >= 15

    # Tools
    res_tools = client.get("/api/tools")
    assert res_tools.status_code == 200
    assert len(res_tools.json()["tools"]) >= 15

    # Kanban
    res_kanban = client.get("/api/kanban")
    assert res_kanban.status_code == 200
    assert "todo" in res_kanban.json()
    assert "done" in res_kanban.json()
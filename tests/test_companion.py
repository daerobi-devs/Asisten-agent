import pytest
from fastapi.testclient import TestClient
from lxion.companion.windows_agent import app, AUTH_TOKEN

client = TestClient(app)

def test_companion_auth_and_status():
    # Unauthorized without header
    res_unauth = client.get("/status")
    assert res_unauth.status_code == 401

    # Authorized
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    res = client.get("/status", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "os" in data

def test_companion_command_whitelist():
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}

    # 1. Allowed command: echo
    res_ok = client.post("/exec", headers=headers, json={"command": "echo Hello LXION Tailscale"})
    assert res_ok.status_code == 200
    assert "Hello LXION Tailscale" in res_ok.json().get("stdout", "")

    # 2. Blocked command (not in whitelist)
    res_blocked = client.post("/exec", headers=headers, json={"command": "format c:"})
    assert res_blocked.status_code == 403
    assert "not in allowed whitelist" in res_blocked.json().get("detail", "")

def test_companion_path_whitelist():
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}

    # Blocked dangerous path traversal
    res_blocked = client.post("/files/read", headers=headers, json={"path": "C:\\Windows\\System32\\config\\SAM"})
    assert res_blocked.status_code == 403
    assert "Access denied" in res_blocked.json().get("detail", "")

def test_companion_screenshot():
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    res = client.get("/screenshot", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) > 1000
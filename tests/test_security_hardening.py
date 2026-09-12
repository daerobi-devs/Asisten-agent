import pytest
from fastapi.testclient import TestClient
from lxion.security.rate_limiter import SlidingWindowRateLimiter
from lxion.security.sanitizer import sanitize_text, mask_secret
from lxion.companion.windows_agent import app as companion_app, AUTH_TOKEN

def test_sliding_window_rate_limiter_requests():
    limiter = SlidingWindowRateLimiter(max_requests_per_minute=3, max_tokens_per_minute=10000)
    limiter.reset()

    # Request 1, 2, 3 should be allowed
    for _ in range(3):
        allowed, reason = limiter.check_allowed()
        assert allowed is True
        assert reason is None
        limiter.record_request()

    # Request 4 should be rejected
    allowed, reason = limiter.check_allowed()
    assert allowed is False
    assert "Request rate limit exceeded" in reason

def test_sliding_window_rate_limiter_tokens():
    limiter = SlidingWindowRateLimiter(max_requests_per_minute=100, max_tokens_per_minute=1000)
    limiter.reset()

    limiter.record_request(tokens=800)
    allowed, reason = limiter.check_allowed(estimated_tokens=300)
    assert allowed is False
    assert "Token rate limit exceeded" in reason

def test_secret_sanitizer():
    raw_log = "Error connecting with sk-abc1234567890xyz and token 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_12345678"
    sanitized = sanitize_text(raw_log)

    assert "sk-abc1234567890xyz" not in sanitized
    assert "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_12345678" not in sanitized
    assert "[REDACTED" in sanitized

def test_mask_secret():
    assert mask_secret("sk-1234567890abcdef") == "sk-1••••cdef"
    assert mask_secret(None) == "Not Configured"
    assert mask_secret("short") == "••••••••"

def test_companion_command_jail_rejection():
    client = TestClient(companion_app)
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}

    # 1. Normal allowed command works
    res_normal = client.post("/exec", json={"command": "dir"}, headers=headers)
    assert res_normal.status_code == 200

    # 2. Command chaining with & must be blocked with HTTP 403
    res_chain1 = client.post("/exec", json={"command": "dir & echo hacked"}, headers=headers)
    assert res_chain1.status_code == 403
    assert "forbidden" in res_chain1.text.lower()

    # 3. Command chaining with ; must be blocked
    res_chain2 = client.post("/exec", json={"command": "dir; tasklist"}, headers=headers)
    assert res_chain2.status_code == 403

    # 4. Pipe must be blocked
    res_pipe = client.post("/exec", json={"command": "dir | python"}, headers=headers)
    assert res_pipe.status_code == 403

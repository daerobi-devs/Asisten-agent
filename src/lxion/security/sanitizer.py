import re
from typing import Optional

SECRET_PATTERNS = [
    # OpenAI, 9Router, DeepSeek keys (e.g., sk-...)
    (re.compile(r"sk-[a-zA-Z0-9_\-]{8,}", re.IGNORECASE), "sk-••••[REDACTED]"),
    # Telegram Bot tokens (e.g. 1234567890:ABCdef...)
    (re.compile(r"\b\d{8,11}:[a-zA-Z0-9_\-]{25,}\b"), "••••[REDACTED_TELEGRAM_TOKEN]"),
    # Bearer tokens in headers or logs
    (re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]{10,})", re.IGNORECASE), "Bearer ••••[REDACTED]"),
    # DB connection password (postgresql://user:password@host...)
    (re.compile(r"://([^:]+):([^@]+)@"), r"://\1:••••@"),
    # Generic token assignment token=...
    (re.compile(r"(api[_-]?key|auth[_-]?token|secret)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_\-]{10,})[\"']?", re.IGNORECASE), r"\1=••••[REDACTED]")
]

def mask_secret(secret: Optional[str], visible_chars: int = 4) -> str:
    """Mask a secret showing only prefix and suffix characters."""
    if not secret:
        return "Not Configured"
    if len(secret) <= visible_chars * 2:
        return "••••••••"
    return secret[:visible_chars] + "••••" + secret[-visible_chars:]

def sanitize_text(text: str) -> str:
    """Sanitize raw text or traceback by stripping sensitive tokens and API keys."""
    if not text:
        return ""
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized

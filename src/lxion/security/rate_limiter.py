import time
from typing import Dict, Any, List, Tuple, Optional
from collections import deque
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger

class RateLimitError(Exception):
    """Raised when request or token rate limits are exceeded."""
    pass

class SlidingWindowRateLimiter:
    """Sliding-window rate limiter to safeguard token costs and prevent infinite agentic loops."""
    def __init__(
        self,
        max_requests_per_minute: Optional[int] = None,
        max_tokens_per_minute: Optional[int] = None,
        window_seconds: float = 60.0
    ):
        self.max_rpm = max_requests_per_minute or settings.RATE_LIMIT_REQUESTS_PER_MINUTE
        self.max_tpm = max_tokens_per_minute or settings.RATE_LIMIT_TOKENS_PER_MINUTE
        self.window_seconds = window_seconds
        self.request_timestamps: deque = deque()
        self.token_records: deque = deque()  # stores (timestamp, tokens)

    def _cleanup(self, now: float):
        cutoff = now - self.window_seconds
        while self.request_timestamps and self.request_timestamps[0] < cutoff:
            self.request_timestamps.popleft()
        while self.token_records and self.token_records[0][0] < cutoff:
            self.token_records.popleft()

    def check_allowed(self, estimated_tokens: int = 0) -> Tuple[bool, Optional[str]]:
        now = time.time()
        self._cleanup(now)

        # Check request count
        if len(self.request_timestamps) >= self.max_rpm:
            msg = f"Request rate limit exceeded: {len(self.request_timestamps)}/{self.max_rpm} rpm"
            AuditLogger.log_event("RATE_LIMIT_BREACH", "security", {"type": "rpm", "limit": self.max_rpm})
            return False, msg

        # Check token usage
        current_tokens = sum(t for _, t in self.token_records)
        if current_tokens + estimated_tokens > self.max_tpm:
            msg = f"Token rate limit exceeded: {current_tokens + estimated_tokens}/{self.max_tpm} tpm"
            AuditLogger.log_event("RATE_LIMIT_BREACH", "security", {"type": "tpm", "limit": self.max_tpm})
            return False, msg

        return True, None

    def record_request(self, tokens: int = 0):
        now = time.time()
        self.request_timestamps.append(now)
        if tokens > 0:
            self.token_records.append((now, tokens))

    def reset(self):
        self.request_timestamps.clear(  )
        self.token_records.clear()

    def get_status(self) -> Dict[str, Any]:
        now = time.time()
        self._cleanup(now)
        current_tokens = sum(t for _, t in self.token_records)
        return {
            "current_rpm": len(self.request_timestamps),
            "max_rpm": self.max_rpm,
            "current_tpm": current_tokens,
            "max_tpm": self.max_tpm,
            "window_seconds": self.window_seconds
        }

rate_limiter = SlidingWindowRateLimiter()

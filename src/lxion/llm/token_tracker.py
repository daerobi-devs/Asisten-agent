from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class UsageStats:
    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    last_model_used: str = ""
    last_latency_ms: float = 0.0

class TokenTracker:
    def __init__(self):
        self.stats = UsageStats()

    def record_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "",
        latency_ms: float = 0.0
    ):
        self.stats.total_requests += 1
        self.stats.total_prompt_tokens += prompt_tokens
        self.stats.total_completion_tokens += completion_tokens
        self.stats.total_tokens += (prompt_tokens + completion_tokens)
        self.stats.last_model_used = model
        self.stats.last_latency_ms = latency_ms

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_requests": self.stats.total_requests,
            "prompt_tokens": self.stats.total_prompt_tokens,
            "completion_tokens": self.stats.total_completion_tokens,
            "total_tokens": self.stats.total_tokens,
            "last_model": self.stats.last_model_used,
            "last_latency_ms": round(self.stats.last_latency_ms, 2)
        }

tracker = TokenTracker()
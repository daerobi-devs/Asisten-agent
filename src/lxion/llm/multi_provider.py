import time
import httpx
from typing import Dict, Any, List, Optional
from lxion.core.config import settings
from lxion.core.logger import logger, AuditLogger
from lxion.llm.token_tracker import tracker
from lxion.llm.router_client import NineRouterClient

class OpenAIDirectClient:
    """Direct OpenAI API client as an independent fallback provider."""
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 60.0):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = (base_url or settings.OPENAI_BASE_URL).rstrip("/")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def list_models(self) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                if res.status_code == 200:
                    return res.json().get("data", [])
        except Exception as e:
            logger.warning(f"Failed to fetch OpenAI models: {e}")
        return []

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        if not self.is_configured:
            raise RuntimeError("OpenAI Direct API Key not configured")

        target_model = model or "gpt-4o-mini"
        if target_model == "auto" or "wkwk" in target_model:
            target_model = "gpt-4o"

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        start_time = time.time()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            latency_ms = (time.time() - start_time) * 1000

            if res.status_code != 200:
                raise RuntimeError(f"OpenAI HTTP Error {res.status_code}: {res.text}")

            data = res.json()
            usage = data.get("usage", {})
            tracker.record_usage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                model=f"openai/{target_model}",
                latency_ms=latency_ms
            )
            return data


class AnthropicDirectClient:
    """Direct Anthropic API client as an independent fallback provider."""
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 60.0):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.base_url = (base_url or settings.ANTHROPIC_BASE_URL).rstrip("/")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"}
        ]

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        if not self.is_configured:
            raise RuntimeError("Anthropic Direct API Key not configured")

        target_model = model or "claude-3-5-haiku-20241022"
        if "sonnet" in (model or "").lower():
            target_model = "claude-3-7-sonnet-20250219"

        # Transform messages for Anthropic
        system_content = ""
        anthropic_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content", "")
            else:
                anthropic_messages.append({"role": m["role"], "content": m.get("content", "")})

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature
        }
        if system_content:
            payload["system"] = system_content

        start_time = time.time()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            latency_ms = (time.time() - start_time) * 1000

            if res.status_code != 200:
                raise RuntimeError(f"Anthropic HTTP Error {res.status_code}: {res.text}")

            data = res.json()
            # Normalize to OpenAI response structure for seamless agent consumption
            text_blocks = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
            combined_text = "".join(text_blocks)
            usage = data.get("usage", {})

            tracker.record_usage(
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                model=f"anthropic/{target_model}",
                latency_ms=latency_ms
            )

            return {
                "id": data.get("id"),
                "model": target_model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": combined_text,
                        "tool_calls": []
                    },
                    "finish_reason": data.get("stop_reason", "stop")
                }],
                "usage": {
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                    "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                }
            }


class MultiProviderRouter:
    """Orchestrates primary 9Router gateway with automatic failover to direct providers."""
    def __init__(
        self,
        primary_client: Optional[NineRouterClient] = None,
        openai_client: Optional[OpenAIDirectClient] = None,
        anthropic_client: Optional[AnthropicDirectClient] = None
    ):
        self.primary = primary_client or NineRouterClient()
        self.openai = openai_client or OpenAIDirectClient()
        self.anthropic = anthropic_client or AnthropicDirectClient()
        self.last_used_provider: str = "9router"

    def get_providers_status(self) -> Dict[str, Any]:
        """Return configuration and health status across all configured providers."""
        return {
            "9router": {
                "name": "9Router Self-Hosted Gateway",
                "role": "Primary Gateway",
                "configured": bool(self.primary.api_key),
                "base_url": self.primary.base_url,
                "priority": 1
            },
            "openai": {
                "name": "OpenAI Direct API",
                "role": "Tier-1 Fallback",
                "configured": self.openai.is_configured,
                "base_url": self.openai.base_url,
                "priority": 2
            },
            "anthropic": {
                "name": "Anthropic Claude Direct API",
                "role": "Tier-2 Fallback",
                "configured": self.anthropic.is_configured,
                "base_url": self.anthropic.base_url,
                "priority": 3
            }
        }

    async def list_models(self) -> List[Dict[str, Any]]:
        """Fetch available models from 9Router first, supplementing with direct providers."""
        models = []
        try:
            models = await self.primary.list_models()
        except Exception as e:
            logger.warning(f"Could not load models from 9Router: {e}")

        if not models:
            if self.openai.is_configured:
                models.extend(await self.openai.list_models())
            if self.anthropic.is_configured:
                models.extend(await self.anthropic.list_models())

        return models

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send chat completion with automatic resilient multi-provider failover."""
        # 1. Direct routing check: if model explicitly requests a direct provider
        if model and model.startswith("direct/openai") and self.openai.is_configured:
            clean_model = model.replace("direct/openai/", "")
            self.last_used_provider = "openai"
            return await self.openai.chat_completion(messages, model=clean_model, tools=tools, temperature=temperature, max_tokens=max_tokens)

        if model and model.startswith("direct/anthropic") and self.anthropic.is_configured:
            clean_model = model.replace("direct/anthropic/", "")
            self.last_used_provider = "anthropic"
            return await self.anthropic.chat_completion(messages, model=clean_model, tools=tools, temperature=temperature, max_tokens=max_tokens)

        # 2. Try Primary Gateway: 9Router
        errors = []
        try:
            res = await self.primary.chat_completion(
                messages=messages,
                model=model,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens
            )
            self.last_used_provider = "9router"
            return res
        except Exception as exc:
            err_str = str(exc)
            errors.append(f"9Router: {err_str}")
            logger.warning(f"9Router primary failed, evaluating failover chain. Error: {err_str}")
            AuditLogger.log_event("PROVIDER_PRIMARY_FAILURE", "multi_provider", {
                "provider": "9router",
                "error": err_str
            })

        # 3. Fallback Tier 1: Direct OpenAI (if configured)
        if self.openai.is_configured:
            try:
                logger.info("Failing over to Direct OpenAI provider...")
                res = await self.openai.chat_completion(
                    messages=messages,
                    model=model,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                self.last_used_provider = "openai"
                AuditLogger.log_event("PROVIDER_FAILOVER_SUCCESS", "multi_provider", {
                    "from": "9router",
                    "to": "openai"
                })
                return res
            except Exception as exc:
                errors.append(f"OpenAI: {exc}")
                logger.warning(f"OpenAI fallback failed: {exc}")

        # 4. Fallback Tier 2: Direct Anthropic (if configured)
        if self.anthropic.is_configured:
            try:
                logger.info("Failing over to Direct Anthropic Claude provider...")
                res = await self.anthropic.chat_completion(
                    messages=messages,
                    model=model,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                self.last_used_provider = "anthropic"
                AuditLogger.log_event("PROVIDER_FAILOVER_SUCCESS", "multi_provider", {
                    "from": "openai",
                    "to": "anthropic"
                })
                return res
            except Exception as exc:
                errors.append(f"Anthropic: {exc}")
                logger.warning(f"Anthropic fallback failed: {exc}")

        # All providers exhausted
        all_errs = "; ".join(errors)
        raise RuntimeError(f"All LLM providers in failover chain exhausted. Errors: {all_errs}")

# Default global instance
multi_provider_router = MultiProviderRouter()

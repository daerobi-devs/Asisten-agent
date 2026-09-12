import json
import time
import httpx
from typing import Any, AsyncGenerator, Dict, List, Optional
from lxion.core.config import settings
from lxion.core.logger import logger
from lxion.llm.token_tracker import tracker

class NineRouterClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 90.0
    ):
        self.base_url = (base_url or settings.NINE_ROUTER_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.NINE_ROUTER_API_KEY
        self.timeout = timeout

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LXION-Agent/0.3.0"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def list_models(self) -> List[Dict[str, Any]]:
        """Fetch available models from 9Router /models endpoint."""
        url = f"{self.base_url}/models"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url, headers=self._get_headers())
                if res.status_code == 200:
                    data = res.json()
                    models = data.get("data", [])
                    logger.info(f"✓ Fetched {len(models)} models from 9Router")
                    return models
                else:
                    logger.warning(f"Failed to fetch models from 9Router: {res.status_code} - {res.text}")
                    return []
        except Exception as e:
            logger.error(f"Error connecting to 9Router models endpoint: {e}")
            return []

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send chat completion request to 9Router, handling both standard JSON and SSE stream responses."""
        url = f"{self.base_url}/chat/completions"
        target_model = model or settings.DEFAULT_MODEL
        if target_model == "auto":
            target_model = "wkwk"  # Use tested active combo or default

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
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, headers=self._get_headers(), json=payload)
                latency_ms = (time.time() - start_time) * 1000
                
                if res.status_code != 200:
                    error_msg = f"9Router HTTP Error {res.status_code}: {res.text}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                
                content_type = res.headers.get("content-type", "")
                
                # Case 1: Standard JSON Response
                if "application/json" in content_type:
                    data = res.json()
                    usage = data.get("usage", {})
                    tracker.record_usage(
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        model=target_model,
                        latency_ms=latency_ms
                    )
                    return data
                
                # Case 2: SSE Event-Stream Response (Auto reassembly)
                accumulated_content = []
                tool_calls_map: Dict[int, Dict[str, Any]] = {}
                model_id = target_model
                
                for line in res.text.splitlines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        model_id = chunk.get("model", model_id)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                accumulated_content.append(delta["content"])
                            if "tool_calls" in delta:
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls_map:
                                        tool_calls_map[idx] = {
                                            "id": tc.get("id", f"call_{idx}"),
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""}
                                        }
                                    fn = tc.get("function", {})
                                    if "name" in fn and fn["name"]:
                                        tool_calls_map[idx]["function"]["name"] += fn["name"]
                                    if "arguments" in fn and fn["arguments"]:
                                        tool_calls_map[idx]["function"]["arguments"] += fn["arguments"]
                    except json.JSONDecodeError:
                        continue

                final_text = "".join(accumulated_content)
                final_tool_calls = list(tool_calls_map.values()) if tool_calls_map else None

                tracker.record_usage(
                    prompt_tokens=len(str(messages)) // 4,
                    completion_tokens=len(final_text) // 4,
                    model=model_id,
                    latency_ms=latency_ms
                )

                return {
                    "id": f"chatcmpl-reconstructed",
                    "object": "chat.completion",
                    "model": model_id,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": final_text,
                                "tool_calls": final_tool_calls
                            },
                            "finish_reason": "stop"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": len(str(messages)) // 4,
                        "completion_tokens": len(final_text) // 4,
                        "total_tokens": (len(str(messages)) + len(final_text)) // 4
                    }
                }
        except httpx.RequestError as exc:
            logger.error(f"HTTP request error while calling 9Router: {exc}")
            raise

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chat completions chunk by chunk."""
        url = f"{self.base_url}/chat/completions"
        target_model = model or settings.DEFAULT_MODEL
        if target_model == "auto":
            target_model = "wkwk"

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        start_time = time.time()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, headers=self._get_headers(), json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    raise RuntimeError(f"9Router Stream Error {response.status_code}: {err_body.decode('utf-8')}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[len("data: "):].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            yield chunk
                        except json.JSONDecodeError:
                            continue
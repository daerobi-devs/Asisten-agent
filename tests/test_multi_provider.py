import pytest
from unittest.mock import AsyncMock, patch
from lxion.llm.multi_provider import MultiProviderRouter, OpenAIDirectClient, AnthropicDirectClient

@pytest.mark.asyncio
async def test_multi_provider_primary_success():
    mock_primary = AsyncMock()
    mock_primary.chat_completion.return_value = {
        "id": "chat-primary-123",
        "choices": [{"message": {"role": "assistant", "content": "Response from 9Router"}}]
    }

    router = MultiProviderRouter(primary_client=mock_primary)
    res = await router.chat_completion([{"role": "user", "content": "Halo"}])

    assert res["choices"][0]["message"]["content"] == "Response from 9Router"
    assert router.last_used_provider == "9router"
    mock_primary.chat_completion.assert_awaited_once()

@pytest.mark.asyncio
async def test_multi_provider_failover_to_openai():
    mock_primary = AsyncMock()
    mock_primary.chat_completion.side_effect = RuntimeError("9Router 502 Bad Gateway")

    mock_openai = AsyncMock()
    mock_openai.is_configured = True
    mock_openai.chat_completion.return_value = {
        "id": "chat-openai-456",
        "choices": [{"message": {"role": "assistant", "content": "Response from OpenAI Failover"}}]
    }

    router = MultiProviderRouter(primary_client=mock_primary, openai_client=mock_openai)
    res = await router.chat_completion([{"role": "user", "content": "Halo"}])

    assert res["choices"][0]["message"]["content"] == "Response from OpenAI Failover"
    assert router.last_used_provider == "openai"
    mock_primary.chat_completion.assert_awaited_once()
    mock_openai.chat_completion.assert_awaited_once()

@pytest.mark.asyncio
async def test_multi_provider_direct_routing():
    mock_primary = AsyncMock()
    mock_openai = AsyncMock()
    mock_openai.is_configured = True
    mock_openai.chat_completion.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Direct OpenAI"}}]
    }

    router = MultiProviderRouter(primary_client=mock_primary, openai_client=mock_openai)
    res = await router.chat_completion([{"role": "user", "content": "Test"}], model="direct/openai/gpt-4o")

    assert res["choices"][0]["message"]["content"] == "Direct OpenAI"
    assert router.last_used_provider == "openai"
    # Primary shouldn't have been called
    mock_primary.chat_completion.assert_not_awaited()

def test_multi_provider_status():
    router = MultiProviderRouter()
    status = router.get_providers_status()
    assert "9router" in status
    assert "openai" in status
    assert "anthropic" in status
    assert status["9router"]["priority"] == 1

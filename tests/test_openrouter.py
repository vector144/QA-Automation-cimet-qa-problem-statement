"""
tests/test_openrouter.py
TDD tests for the OpenRouter client and JSON parsing utilities.
Run: uv run pytest tests/test_openrouter.py -v
"""

import pytest
from unittest.mock import AsyncMock, patch
from services.openrouter import OpenRouterClient, MockOpenRouterClient, clean_json_response


def test_clean_json_response_handles_raw_json():
    raw = '{"status": "PASS", "confidence": 0.95}'
    parsed = clean_json_response(raw)
    assert parsed["status"] == "PASS"
    assert parsed["confidence"] == 0.95


def test_clean_json_response_handles_markdown_codeblocks():
    raw = '```json\n{"status": "FAIL", "reason": "Did not disclose cooling off"}\n```'
    parsed = clean_json_response(raw)
    assert parsed["status"] == "FAIL"
    assert "cooling off" in parsed["reason"]


def test_clean_json_response_handles_surrounding_text():
    raw = 'Here is your evaluation:\n```json\n{"status": "PASS"}\n```\nHope that helps!'
    parsed = clean_json_response(raw)
    assert parsed["status"] == "PASS"


@pytest.mark.asyncio
async def test_mock_openrouter_client_returns_configured_response():
    mock_client = MockOpenRouterClient(default_response={"status": "PASS", "confidence": 0.99})
    resp = await mock_client.complete_json([{"role": "user", "content": "Evaluate this"}])
    assert resp["status"] == "PASS"
    assert resp["confidence"] == 0.99


@pytest.mark.asyncio
async def test_openrouter_client_formats_request_correctly():
    client = OpenRouterClient(api_key="test-key", model="anthropic/claude-sonnet-4-5")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        import httpx
        req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        mock_post.return_value = httpx.Response(
            200,
            request=req,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"status": "PASS", "confidence": 0.92, "reason": "Compliant"}'
                        }
                    }
                ]
            },
        )

        result = await client.complete_json([{"role": "user", "content": "test prompt"}])

        assert result["status"] == "PASS"
        assert result["confidence"] == 0.92
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-key"

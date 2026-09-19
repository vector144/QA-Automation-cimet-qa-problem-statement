"""
services/openrouter.py
Async OpenRouter HTTP client for LLM-based compliance evaluations.
Supports structured JSON parsing, retry logic, and mock clients for deterministic tests.
"""

import os
import json
import re
from typing import Any, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()


def clean_json_response(raw_text: str) -> dict[str, Any]:
    """
    Extracts and parses JSON from raw LLM output, handling markdown code blocks,
    surrounding chatter, or raw JSON strings.
    """
    cleaned = raw_text.strip()

    # If wrapped in ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        cleaned = match.group(1).strip()
    else:
        # Check if there's any {...} enclosed block in the text
        json_match = re.search(r"(\{[\s\S]*\})", cleaned)
        if json_match:
            cleaned = json_match.group(1).strip()

    return json.loads(cleaned)


class OpenRouterClient:
    """Production async client for OpenRouter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        raw_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.api_key = raw_key.strip()
        self.is_configured = bool(
            self.api_key
            and not self.api_key.startswith("sk-or-your")
            and not self.api_key.startswith("your-")
            and len(self.api_key) > 0
        )
        # Default to high-performance free model on OpenRouter:
        # Options: "openrouter/free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemini-2.0-flash-exp:free"
        self.model = model or os.getenv("DEFAULT_LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        self.base_url = base_url

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Sends chat completion request and parses returned message content as JSON.
        """
        # Fast path: Try Groq API first if available (blazingly fast ~0.8s vs ~12s)
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key and not groq_key.startswith("gsk_your") and len(groq_key) > 10:
            try:
                from groq import Groq
                groq_client = Groq(api_key=groq_key)
                completion = groq_client.chat.completions.create(
                    messages=messages,
                    model="openai/gpt-oss-120b",
                    response_format={"type": "json_object"},
                    temperature=temperature,
                )
                content = completion.choices[0].message.content
                return clean_json_response(content)
            except Exception as e:
                # Fall back to OpenRouter on any Groq error (rate limit, etc.)
                pass

        if not self.is_configured:
            raise ValueError(
                "OPENROUTER_API_KEY is not configured or empty. Using offline deterministic evaluator."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://cimet.com.au",
            "X-Title": "CIMET QA Automation",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
        }
        # Only add response_format for models known to support it (non-free models)
        target_model = model or self.model
        if ":free" not in target_model:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            if resp.is_error:
                print("OpenRouter Error response:", resp.status_code, resp.text)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return clean_json_response(content)


class MockOpenRouterClient:
    """
    Mock client for deterministic, offline testing of evaluation pipelines.
    Returns pre-configured JSON payloads or can use a callback.
    """

    def __init__(
        self,
        default_response: Optional[dict[str, Any]] = None,
        responder_fn: Optional[Any] = None,
    ):
        self.default_response = default_response or {"status": "PASS", "confidence": 1.0, "reason": "Mock pass"}
        self.responder_fn = responder_fn
        self.call_history: list[dict[str, Any]] = []

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        self.call_history.append({"messages": messages, "temperature": temperature, "model": model})
        if self.responder_fn:
            return self.responder_fn(messages)
        return self.default_response


_global_client: Optional[OpenRouterClient] = None


def get_openrouter_client() -> OpenRouterClient:
    """Returns the shared OpenRouter client instance."""
    global _global_client
    if _global_client is None:
        _global_client = OpenRouterClient()
    return _global_client

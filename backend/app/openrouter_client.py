from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT_SECONDS = 20.0


@dataclass
class OpenRouterClientError(Exception):
    message: str
    status_code: int = 502


def _get_openrouter_api_key() -> str:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise OpenRouterClientError(
            message="OpenRouter API key is not configured",
            status_code=500,
        )
    return api_key


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        return "".join(text_parts).strip()

    return ""


def request_openrouter_completion(
    messages: list[dict[str, str]],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    api_key = _get_openrouter_api_key()
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(base_url=OPENROUTER_BASE_URL, timeout=timeout_seconds) as client:
            response = client.post("/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise OpenRouterClientError(
            message="OpenRouter request timed out",
            status_code=504,
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise OpenRouterClientError(
            message=f"OpenRouter request failed with status {exc.response.status_code}",
            status_code=502,
        ) from exc
    except httpx.HTTPError as exc:
        raise OpenRouterClientError(
            message="OpenRouter request failed",
            status_code=502,
        ) from exc

    data = response.json()
    try:
        first_choice = data["choices"][0]
        message_content = first_choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OpenRouterClientError(
            message="OpenRouter response format is invalid",
            status_code=502,
        ) from exc

    reply = _normalize_content(message_content)
    if not reply:
        raise OpenRouterClientError(
            message="OpenRouter returned empty content",
            status_code=502,
        )

    return reply

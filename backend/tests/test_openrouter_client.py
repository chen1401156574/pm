from __future__ import annotations

import json

import httpx
import pytest

from app.openrouter_client import (
    OPENROUTER_MODEL,
    OpenRouterClientError,
    request_openrouter_completion,
)


class _MockResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                message="status error",
                request=self.request,
                response=httpx.Response(
                    status_code=self.status_code,
                    request=self.request,
                    content=json.dumps(self._payload).encode("utf-8"),
                ),
            )

    def json(self) -> dict:
        return self._payload


class _MockClient:
    def __init__(self, response: _MockResponse | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, json: dict, headers: dict) -> _MockResponse:
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def test_request_openrouter_completion_builds_payload_and_parses_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_client = _MockClient(
        response=_MockResponse(
            status_code=200,
            payload={
                "choices": [
                    {"message": {"content": "4"}},
                ],
            },
        ),
    )

    def _client_factory(*args, **kwargs):
        return mock_client

    monkeypatch.setattr("app.openrouter_client.httpx.Client", _client_factory)
    reply = request_openrouter_completion(messages=[{"role": "user", "content": "2+2"}])

    assert reply == "4"
    assert len(mock_client.calls) == 1
    sent_payload = mock_client.calls[0]["json"]
    assert sent_payload["model"] == OPENROUTER_MODEL
    assert sent_payload["messages"] == [{"role": "user", "content": "2+2"}]


def test_request_openrouter_completion_timeout_maps_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_client = _MockClient(error=httpx.TimeoutException("timeout"))
    monkeypatch.setattr("app.openrouter_client.httpx.Client", lambda *args, **kwargs: mock_client)

    with pytest.raises(OpenRouterClientError) as exc:
        request_openrouter_completion(messages=[{"role": "user", "content": "2+2"}])

    assert exc.value.status_code == 504
    assert "timed out" in exc.value.message


def test_request_openrouter_completion_non_2xx_maps_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_client = _MockClient(
        response=_MockResponse(
            status_code=502,
            payload={"error": {"message": "bad gateway"}},
        ),
    )
    monkeypatch.setattr("app.openrouter_client.httpx.Client", lambda *args, **kwargs: mock_client)

    with pytest.raises(OpenRouterClientError) as exc:
        request_openrouter_completion(messages=[{"role": "user", "content": "2+2"}])

    assert exc.value.status_code == 502
    assert "status 502" in exc.value.message

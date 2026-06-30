"""Ollama LLM backend (local dev).

Talks to a local Ollama server's /api/chat endpoint over HTTP. `httpx` is the
only dependency (already required by the service extra). The model and host are
config-driven; a client can be injected for tests (httpx.MockTransport), so the
request/response handling is covered without a running server.
"""

from __future__ import annotations

from .structured_llm import StructuredLLMProvider


class OllamaLLM(StructuredLLMProvider):
    def __init__(
        self,
        model: str = "llama3.1",
        host: str = "http://localhost:11434",
        *,
        client=None,
        timeout: float = 120.0,
        max_claims: int = 4,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = timeout
        self._client = client  # injected for tests; lazily created otherwise
        self.max_claims = max_claims

    def _http(self):
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def complete(self, system: str, user: str, *, want_json: bool = True) -> str:
        payload: dict = {
            "model": self._model,
            "stream": False,
            "options": {"temperature": 0.0},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if want_json:
            payload["format"] = "json"
        resp = self._http().post(f"{self._host}/api/chat", json=payload)
        resp.raise_for_status()
        body = resp.json()
        return (body.get("message") or {}).get("content", "") or ""

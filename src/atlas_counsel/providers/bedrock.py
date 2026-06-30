"""Bedrock LLM backend (prod).

Uses the Bedrock Runtime Converse API, which gives a uniform message/ system
shape across model families (Claude, Titan text, Llama, …). `boto3` is imported
lazily on first use and is an opt-in extra; a client can be injected for tests so
request/response handling is covered without AWS.
"""

from __future__ import annotations

from .structured_llm import StructuredLLMProvider


class BedrockLLM(StructuredLLMProvider):
    def __init__(
        self,
        model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0",
        region: str = "us-east-1",
        *,
        client=None,
        max_tokens: int = 1024,
        max_claims: int = 4,
    ) -> None:
        self._model_id = model_id
        self._region = region
        self._client = client  # injected for tests; lazily created otherwise
        self._max_tokens = max_tokens
        self.max_claims = max_claims

    def _bedrock(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("bedrock-runtime", region_name=self._region)
        return self._client

    def complete(self, system: str, user: str, *, want_json: bool = True) -> str:
        if want_json:
            user = user + (
                "\n\nRespond with ONLY a single JSON object. No prose, no markdown."
            )
        resp = self._bedrock().converse(
            modelId=self._model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": self._max_tokens, "temperature": 0.0},
        )
        return resp["output"]["message"]["content"][0]["text"]

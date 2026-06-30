"""Titan embedder (Bedrock, prod).

amazon.titan-embed-text-v2 returns a dense vector only, so we pair it with the
deterministic `lexical_sparse` channel to keep hybrid retrieval intact. boto3 is
lazily imported; a client can be injected for tests so the invoke→Embedding
mapping is covered without AWS.

space_id = "titan-v2" — a distinct space from bge-m3, its own collection.
"""

from __future__ import annotations

import json

from ..embeddings import Embedding, lexical_sparse


class TitanEmbedder:
    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v2:0",
        region: str = "us-east-1",
        *,
        client=None,
        dim: int = 1024,
        space_id: str = "titan-v2",
    ) -> None:
        self._model_id = model_id
        self._region = region
        self._client = client  # injected for tests; lazily created otherwise
        self._dim = dim
        self._space_id = space_id

    @property
    def space_id(self) -> str:
        return self._space_id

    @property
    def dense_dim(self) -> int:
        return self._dim

    def _bedrock(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("bedrock-runtime", region_name=self._region)
        return self._client

    def embed(self, texts: list[str]) -> list[Embedding]:
        client = self._bedrock()
        result: list[Embedding] = []
        for text in texts:
            body = json.dumps(
                {"inputText": text, "dimensions": self._dim, "normalize": True})
            resp = client.invoke_model(modelId=self._model_id, body=body)
            payload = json.loads(resp["body"].read())
            dense = [float(x) for x in payload["embedding"]]
            result.append(Embedding(dense=dense, sparse=lexical_sparse(text)))
        return result

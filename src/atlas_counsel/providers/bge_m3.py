"""bge-m3 embedder (local, hybrid-native).

BAAI/bge-m3 produces a dense vector AND learned lexical (sparse) weights in one
pass, which maps directly onto the hybrid `Embedding(dense, sparse)` contract —
no separate lexical channel needed. The model is loaded lazily via FlagEmbedding
on first `embed`; a preloaded model can be injected for tests, so the dict→
Embedding mapping is covered without downloading weights.

space_id = "bge-m3" — its own Qdrant collection, never mixed with Titan's.
"""

from __future__ import annotations

from ..embeddings import Embedding, SparseVector


class BGEM3Embedder:
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str = "",
        *,
        model=None,
        dim: int = 1024,
        space_id: str = "bge-m3",
        use_fp16: bool = True,
    ) -> None:
        self._model_name = model_name
        self._device = device or None
        self._model = model  # injected for tests; lazily loaded otherwise
        self._dim = dim
        self._space_id = space_id
        self._use_fp16 = use_fp16

    @property
    def space_id(self) -> str:
        return self._space_id

    @property
    def dense_dim(self) -> int:
        return self._dim

    def _load(self):
        if self._model is None:
            from FlagEmbedding import BGEM3FlagModel
            self._model = BGEM3FlagModel(
                self._model_name, use_fp16=self._use_fp16, device=self._device)
        return self._model

    def embed(self, texts: list[str]) -> list[Embedding]:
        out = self._load().encode(
            texts, return_dense=True, return_sparse=True, return_colbert_vecs=False)
        dense_vecs = out["dense_vecs"]
        lexical = out["lexical_weights"]
        result: list[Embedding] = []
        for i in range(len(texts)):
            dense = [float(x) for x in list(dense_vecs[i])]
            weights = lexical[i] or {}
            items = sorted((int(k), float(v)) for k, v in weights.items())
            sparse = SparseVector(indices=[k for k, _ in items],
                                  values=[v for _, v in items])
            result.append(Embedding(dense=dense, sparse=sparse))
        return result

"""Unit coverage for the Qdrant retriever using an injected fake client.

The server round-trip lives in test_qdrant_integration.py (skipped without a
running Qdrant). This file instead injects a fake client through the
constructor's `client=` hook, so the index/search wiring — collection naming,
point construction, payload round-trip, and result parsing — is exercised in
CI whenever the qdrant extra is installed. It skips when it isn't, matching the
project convention.
"""

from __future__ import annotations

import pytest

pytest.importorskip("qdrant_client", reason="qdrant-client not installed")

from atlas_counsel.chunking import chunk_corpus  # noqa: E402
from atlas_counsel.corpus import build_corpus  # noqa: E402
from atlas_counsel.embeddings import HashingEmbedder  # noqa: E402
from atlas_counsel.qdrant_store import QdrantHybridRetriever  # noqa: E402


class _FakePoint:
    def __init__(self, payload, score):
        self.payload = payload
        self.score = score


class _FakeResponse:
    def __init__(self, points):
        self.points = points


class FakeQdrantClient:
    """Minimal stand-in: records upserts, returns them ranked on query."""

    def __init__(self):
        self.collections: dict[str, list] = {}

    def collection_exists(self, name):
        return name in self.collections

    def create_collection(self, collection_name, vectors_config=None,
                          sparse_vectors_config=None):
        self.collections[collection_name] = []

    def upsert(self, collection_name, points):
        self.collections.setdefault(collection_name, []).extend(points)

    def query_points(self, collection_name, prefetch=None, query=None,
                     limit=5, with_payload=True):
        pts = self.collections.get(collection_name, [])
        n = len(pts)
        out = [_FakePoint(payload=p.payload, score=float(n - rank))
               for rank, p in enumerate(pts[:limit])]
        return _FakeResponse(out)


def test_index_and_search_roundtrip_preserves_citations():
    provider = HashingEmbedder(space_id="faketest")
    client = FakeQdrantClient()
    retriever = QdrantHybridRetriever(provider, client=client)

    chunks = chunk_corpus(build_corpus())
    retriever.index(chunks)

    # Collection name is derived from the embedding space, and every chunk lands.
    assert client.collection_exists("counsel_faketest")
    assert len(client.collections["counsel_faketest"]) == len(chunks)

    results = retriever.search("single-source justification threshold", top_k=3)
    assert len(results) == 3
    for rc in results:
        # Payload survived the round-trip as a real Chunk with a citation id.
        assert "#S" in rc.chunk.span_id
        assert rc.chunk.doc_id


def test_collection_name_encodes_space():
    r = QdrantHybridRetriever(HashingEmbedder(space_id="bge-m3"), client=FakeQdrantClient())
    assert r.collection_name == "counsel_bge-m3"


def test_ensure_collection_is_idempotent():
    client = FakeQdrantClient()
    r = QdrantHybridRetriever(HashingEmbedder(space_id="x"), client=client)
    r.ensure_collection()
    r.ensure_collection()  # must not raise or recreate
    assert client.collection_exists("counsel_x")

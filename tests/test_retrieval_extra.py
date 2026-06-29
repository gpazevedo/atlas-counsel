"""Extra retrieval tests beyond the core fusion proof in test_retrieval.py.

These cover behaviours the original suite left implicit: empty-state handling,
the observability fields on a result, re-indexing semantics, and an RRF
property check.
"""

from __future__ import annotations

from atlas_counsel.chunking import chunk_corpus
from atlas_counsel.corpus import build_corpus
from atlas_counsel.embeddings import HashingEmbedder
from atlas_counsel.retrieval import (
    InMemoryHybridRetriever,
    reciprocal_rank_fusion,
)


def _retriever() -> InMemoryHybridRetriever:
    r = InMemoryHybridRetriever(HashingEmbedder())
    r.index(chunk_corpus(build_corpus()))
    return r


def test_empty_index_returns_no_results():
    r = InMemoryHybridRetriever(HashingEmbedder())
    assert r.search("anything at all", top_k=5) == []


def test_results_expose_channel_ranks_for_observability():
    r = _retriever()
    results = r.search("single-source justification threshold", top_k=3)
    assert results
    # Every chunk is scored in both channels, so both ranks are populated.
    for rc in results:
        assert rc.dense_rank is not None and rc.dense_rank >= 1
        assert rc.sparse_rank is not None and rc.sparse_rank >= 1


def test_reindex_replaces_previous_contents():
    r = InMemoryHybridRetriever(HashingEmbedder())
    chunks = chunk_corpus(build_corpus())
    r.index(chunks[:2])
    assert len(r.search("threshold", top_k=10)) <= 2
    r.index(chunks)  # full re-index
    assert len(r.search("threshold", top_k=100)) == len(chunks)


def test_top_k_caps_result_count():
    r = _retriever()
    assert len(r.search("approval", top_k=2)) == 2


def test_rrf_rewards_agreement_across_channels():
    # A chunk top-ranked by both channels must beat one top in only a single
    # channel, regardless of the dampening constant k.
    for k in (1, 60, 1000):
        fused = reciprocal_rank_fusion(
            dense_order=["x", "y", "z"],
            sparse_order=["x", "z", "y"],
            k=k,
        )
        assert max(fused, key=fused.get) == "x"

"""Tests for the composed retrieval pipeline, the production reranker wiring,
and the ablation CLI — the parts test_rerank_decompose.py leaves uncovered.

test_rerank_decompose.py proves the rerank/decompose stages in isolation; here
we prove they compose correctly inside RetrievalPipeline (passthrough, merge
dedupe, reranker delegation), that CrossEncoderReranker drives an injected
model, and that the ablation entrypoint runs end to end.
"""

from __future__ import annotations

from atlas_counsel.chunking import Chunk, chunk_corpus
from atlas_counsel.corpus import build_corpus
from atlas_counsel.corpus.models import DocCategory
from atlas_counsel.embeddings import HashingEmbedder
from atlas_counsel.pipeline import RetrievalPipeline, default_pipeline
from atlas_counsel.rerank import CrossEncoderReranker, TokenInteractionReranker
from atlas_counsel.retrieval import InMemoryHybridRetriever, RetrievedChunk


def _rc(span_id: str, text: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(
            chunk_id=span_id, span_id=span_id, doc_id=span_id.split("#")[0],
            category=DocCategory.POLICY, title="T", text=text,
        ),
        score=score,
    )


def _base():
    r = InMemoryHybridRetriever(HashingEmbedder())
    r.index(chunk_corpus(build_corpus()))
    return r


# --- pipeline composition ---------------------------------------------------

def test_pipeline_passthrough_matches_base():
    base = _base()
    pipe = RetrievalPipeline(base)  # no stages
    q = "single-source justification threshold"
    assert [rc.chunk.span_id for rc in pipe.search(q, top_k=3)] == \
           [rc.chunk.span_id for rc in base.search(q, top_k=3)]


def test_pipeline_decomposition_recovers_both_vendors():
    base = _base()
    from atlas_counsel.decompose import HeuristicDecomposer

    pipe = RetrievalPipeline(base, decomposer=HeuristicDecomposer())
    results = pipe.search(
        "Compare the uptime guarantees of AcmeCloud and NorthLink", top_k=5
    )
    ids = {rc.chunk.span_id for rc in results}
    # The multi-hop answer needs both contracts' uptime spans.
    assert "CON-001#S0" in ids and "CON-002#S0" in ids


class _FakeDecomposer:
    def decompose(self, query):
        return ["sub-a", "sub-b"]


class _FakeBase:
    """Returns the same chunk for two sub-queries with different scores."""
    def search(self, query, top_k=5):
        score = 0.9 if query == "sub-a" else 0.3
        return [_rc("X#S0", "shared chunk", score)]


def test_pipeline_merge_dedupes_keeping_max_score():
    pipe = RetrievalPipeline(_FakeBase(), decomposer=_FakeDecomposer())
    results = pipe.search("anything", top_k=5)
    assert len(results) == 1                 # deduped, not double-counted
    assert results[0].score == 0.9           # max score across sub-queries kept


class _ReverseReranker:
    def rerank(self, query, candidates, top_k):
        return list(reversed(candidates))[:top_k]


class _FixedBase:
    """Deterministic candidates so reranker delegation is unambiguous."""
    def search(self, query, top_k=5):
        return [_rc("A#S0", "a", 0.9), _rc("B#S0", "b", 0.5), _rc("C#S0", "c", 0.1)]


def test_pipeline_delegates_to_reranker():
    pipe = RetrievalPipeline(_FixedBase(), reranker=_ReverseReranker())
    out = pipe.search("q", top_k=3)
    # merge sorts by score desc -> [A, B, C]; reverse reranker -> [C, B, A].
    assert [r.chunk.span_id for r in out] == ["C#S0", "B#S0", "A#S0"]


def test_default_pipeline_wires_both_stages():
    base = _base()
    pipe = default_pipeline(base, TokenInteractionReranker())
    assert pipe._decomposer is not None
    assert pipe._reranker is not None
    assert pipe.search("approval authority", top_k=3)  # runs end to end


# --- production reranker (injected model, no sentence-transformers needed) ---

class _FakeCrossEncoder:
    """Scores by length so the order is deterministic and != input order."""
    def predict(self, pairs):
        return [float(len(doc)) for _, doc in pairs]


def test_cross_encoder_reranker_uses_injected_model():
    reranker = CrossEncoderReranker(model=_FakeCrossEncoder())
    cands = [
        _rc("A#S0", "short", 0.9),
        _rc("B#S0", "a considerably longer passage of text", 0.1),
    ]
    out = reranker.rerank("q", cands, top_k=2)
    # Fake model scores by length, so the longer doc (B) ranks first.
    assert out[0].chunk.span_id == "B#S0"


def test_cross_encoder_reranker_empty_input():
    assert CrossEncoderReranker(model=_FakeCrossEncoder()).rerank("q", [], top_k=5) == []


# --- ablation CLI -----------------------------------------------------------

def test_ablation_cli_runs_all_configs(capsys):
    from atlas_counsel import ablation

    ablation.main()
    out = capsys.readouterr().out
    for cfg in ("baseline", "+rerank", "+decompose", "+both"):
        assert cfg in out
    assert "no net gain" in out

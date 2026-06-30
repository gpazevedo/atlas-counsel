"""Direct unit tests for the agent's LLM provider and the pieces the
control-flow suite in test_agent.py exercises only through the graph.

test_agent.py drives TemplateLLM end to end via build_counsel_graph; here we
pin its synthesize/verify behaviour in isolation (the citation-grounding
mechanism), plus the validate router and the refusal-answer shape.
"""

from __future__ import annotations

from atlas_counsel.agent.llm import TemplateLLM
from atlas_counsel.agent.nodes import route_after_validate
from atlas_counsel.agent.schemas import Claim, CounselAnswer, DraftAnswer
from atlas_counsel.chunking import chunk_corpus
from atlas_counsel.corpus import build_corpus
from atlas_counsel.embeddings import HashingEmbedder
from atlas_counsel.retrieval import InMemoryHybridRetriever


def _hits(question: str, k: int = 5):
    r = InMemoryHybridRetriever(HashingEmbedder())
    r.index(chunk_corpus(build_corpus()))
    return r.search(question, top_k=k)


# --- TemplateLLM.synthesize -------------------------------------------------

def test_synthesize_cites_only_retrieved_spans():
    hits = _hits("single-source justification threshold")
    retrieved_ids = {rc.chunk.span_id for rc in hits}
    draft = TemplateLLM().synthesize("q", hits, None)
    assert draft.claims
    # Never invents a citation — every cited span was actually retrieved.
    assert set(draft.cited_span_ids) <= retrieved_ids


def test_synthesize_honors_guidance_toward_a_doc():
    # Pull a broad set, then steer toward POL-003 specifically.
    hits = _hits("approval authority and conflict of interest", k=8)
    assert any(rc.chunk.doc_id == "POL-003" for rc in hits), "need POL-003 in pool"
    draft = TemplateLLM().synthesize("q", hits, guidance="POL-003")
    assert draft.claims
    assert all(cid.startswith("POL-003") for cid in draft.cited_span_ids)


# --- TemplateLLM.verify (the hallucination-catch mechanism) -----------------

def test_verify_flags_citation_to_unretrieved_span():
    hits = _hits("single-source justification threshold")
    bad = DraftAnswer(claims=[Claim(text="fabricated", span_id="ZZZ-999#S0")])
    verdict = TemplateLLM().verify("q", bad, hits)
    assert not verdict.faithful
    assert "ZZZ-999#S0" in verdict.unsupported_span_ids


def test_verify_flags_text_drift_on_a_real_span():
    hits = _hits("single-source justification threshold")
    real_span = hits[0].chunk.span_id
    drifted = DraftAnswer(claims=[
        Claim(text="this text was never in that span whatsoever", span_id=real_span)
    ])
    verdict = TemplateLLM().verify("q", drifted, hits)
    assert not verdict.faithful
    assert real_span in verdict.unsupported_span_ids


def test_verify_passes_for_grounded_claims():
    hits = _hits("single-source justification threshold")
    draft = TemplateLLM().synthesize("q", hits, None)  # claims drawn from spans
    verdict = TemplateLLM().verify("q", draft, hits)
    assert verdict.faithful
    assert verdict.unsupported_span_ids == []


# --- validate router --------------------------------------------------------

def test_route_after_validate():
    assert route_after_validate({"grounded": True}) == "synthesize"
    # Ungrounded now tries gap-analysis first, escalating only once exhausted.
    assert route_after_validate({"grounded": False}) == "gap_analyze"
    assert route_after_validate({}) == "gap_analyze"  # default: ungrounded, gaps left


# --- refusal answer shape ---------------------------------------------------

def test_counsel_answer_refusal_shape():
    ans = CounselAnswer.refusal(attempts=2, escalated=True)
    assert ans.refused is True
    assert ans.citations == []
    assert ans.attempts == 2 and ans.escalated is True
    assert ans.text  # carries a non-empty refusal message

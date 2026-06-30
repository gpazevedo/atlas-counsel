"""StructuredLLMProvider tests — the provider-agnostic parse + citation logic.

Driven by a FakeLLM that returns canned completions, so the hard part (prompt ->
JSON -> schema, hardened against malformed output and hallucinated citations) is
covered with no network and no real model.
"""

from __future__ import annotations

from atlas_counsel.agent.schemas import Claim, DraftAnswer
from atlas_counsel.chunking import Chunk
from atlas_counsel.corpus.models import DocCategory
from atlas_counsel.providers.structured_llm import StructuredLLMProvider
from atlas_counsel.retrieval import RetrievedChunk


class FakeLLM(StructuredLLMProvider):
    def __init__(self, scripted: str) -> None:
        self.scripted = scripted
        self.systems: list[str] = []

    def complete(self, system: str, user: str, *, want_json: bool = True) -> str:
        self.systems.append(system)
        return self.scripted


def _rc(span_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(chunk_id=span_id, span_id=span_id, doc_id=span_id.split("#")[0],
                    category=DocCategory.CONTRACT, title="t", text=text, tokens=[]),
        score=1.0)


CTX = [_rc("CON-002#S1", "Payment terms are net-30."),
       _rc("CON-003#S3", "Liability is capped at $1M.")]


def test_synthesize_parses_claims_from_fenced_json_with_prose():
    llm = FakeLLM('Here you go:\n```json\n{"claims":['
                  '{"text":"Net-30 terms.","span_id":"CON-002#S1"},'
                  '{"text":"Cap $1M.","span_id":"CON-003#S3"}]}\n```')
    draft = llm.synthesize("terms?", CTX, None)
    assert [(c.text, c.span_id) for c in draft.claims] == [
        ("Net-30 terms.", "CON-002#S1"), ("Cap $1M.", "CON-003#S3")]


def test_synthesize_drops_entries_missing_text_or_span():
    llm = FakeLLM('{"claims":[{"text":"ok","span_id":"CON-002#S1"},'
                  '{"text":"","span_id":"CON-003#S3"},{"span_id":"X"}]}')
    draft = llm.synthesize("q", CTX, None)
    assert len(draft.claims) == 1 and draft.claims[0].span_id == "CON-002#S1"


def test_synthesize_caps_at_max_claims():
    llm = FakeLLM('{"claims":[' + ",".join(
        '{"text":"t","span_id":"CON-002#S1"}' for _ in range(10)) + "]}")
    llm.max_claims = 3
    assert len(llm.synthesize("q", CTX, None).claims) == 3


def test_verify_passes_when_supported():
    draft = DraftAnswer(claims=[Claim(text="Net-30 terms.", span_id="CON-002#S1")])
    verdict = FakeLLM('{"faithful":true,"unsupported_span_ids":[]}').verify("q", draft, CTX)
    assert verdict.faithful and not verdict.unsupported_span_ids


def test_verify_catches_hallucinated_citation_even_if_model_says_faithful():
    # Model claims faithful, but the cited span is not in context -> overruled.
    draft = DraftAnswer(claims=[Claim(text="made up", span_id="FAKE#S9")])
    verdict = FakeLLM('{"faithful":true,"unsupported_span_ids":[]}').verify("q", draft, CTX)
    assert verdict.faithful is False and "FAKE#S9" in verdict.unsupported_span_ids


def test_verify_empty_draft_is_unfaithful():
    verdict = FakeLLM('{"faithful":true}').verify("q", DraftAnswer(claims=[]), CTX)
    assert verdict.faithful is False


def test_gap_analyze_parses_and_limits():
    llm = FakeLLM('{"follow_up_queries":["uptime","exceptions","liability","extra"]}')
    assert llm.gap_analyze("q", CTX) == ["uptime", "exceptions", "liability"]


def test_reflect_parses_facts_and_skills():
    llm = FakeLLM('{"semantic_facts":["NorthLink net-30."],"episodic_summary":"asked terms",'
                  '"skills":[{"name":"cite-terms","fragment":"quote the span",'
                  '"when_to_use":"payment Qs"}]}')
    result = llm.reflect("q", "a", "th")
    assert result.semantic_facts == ["NorthLink net-30."]
    assert result.episodic_summary == "asked terms"
    assert result.skills[0].name == "cite-terms" and result.skills[0].when_to_use == "payment Qs"


def test_malformed_json_yields_safe_defaults():
    junk = FakeLLM("I'm sorry, I cannot output JSON.")
    assert junk.synthesize("q", CTX, None).claims == []
    assert junk.gap_analyze("q", CTX) == []
    assert junk.reflect("q", "a", "th").semantic_facts == []
    # an unparseable verify defaults to NOT faithful (fail-closed)
    draft = DraftAnswer(claims=[Claim(text="Net-30 terms.", span_id="CON-002#S1")])
    assert junk.verify("q", draft, CTX).faithful is False

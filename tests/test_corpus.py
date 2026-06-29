"""Tests for the corpus generator and its models.

These guard the properties the eval harness depends on:
  1. determinism      — same inputs => identical corpus
  2. integrity        — every golden span id exists in some document
  3. shape            — the documented 8 docs / 24 spans / 8 golden hold
  4. hard cases       — the planted traps are actually present and tagged
  5. validation       — malformed documents/golden items are rejected at build
"""

from __future__ import annotations

import pytest

from atlas_counsel.corpus import build_corpus
from atlas_counsel.corpus.models import (
    AnswerType,
    Corpus,
    DocCategory,
    Document,
    GoldenItem,
    Span,
)


def test_determinism():
    a = build_corpus().model_dump_json()
    b = build_corpus().model_dump_json()
    assert a == b


def test_seed_does_not_change_output():
    # `seed` is reserved for a future randomized expansion; today the corpus is
    # template-driven, so varying it must not change the bytes.
    assert build_corpus(seed=1).model_dump_json() == build_corpus(seed=999).model_dump_json()


def test_corpus_shape_counts():
    """Locks the documented shape so a future edit can't silently drift it."""
    corpus = build_corpus()
    spans = [s for d in corpus.documents for s in d.spans]
    assert len(corpus.documents) == 8
    assert len(spans) == 24
    assert len(corpus.golden) == 8


def test_referential_integrity_holds():
    corpus = build_corpus()
    known = {s.span_id for d in corpus.documents for s in d.spans}
    for item in corpus.golden:
        assert set(item.supporting_span_ids) <= known


def test_span_ids_are_stable_and_unique():
    corpus = build_corpus()
    ids = [s.span_id for d in corpus.documents for s in d.spans]
    assert len(ids) == len(set(ids)), "span ids must be unique"
    assert "POL-001#S1" in ids


def test_full_text_includes_headings():
    corpus = build_corpus()
    pol = next(d for d in corpus.documents if d.doc_id == "POL-001")
    assert "## Threshold" in pol.full_text
    assert "$50,000" in pol.full_text


def test_unanswerable_item_has_no_spans():
    corpus = build_corpus()
    unanswerable = [g for g in corpus.golden if g.answer_type == AnswerType.UNANSWERABLE]
    assert unanswerable, "corpus must contain at least one unanswerable item"
    for item in unanswerable:
        assert item.supporting_span_ids == []


def test_contradiction_pair_present():
    """AcmeCloud (99.9%) vs NorthLink (99.5%) must both exist and disagree."""
    corpus = build_corpus()
    # Key on (vendor, category): a vendor can own both a contract and a log,
    # so vendor name alone does not identify a document.
    contracts = {
        d.vendor: d
        for d in corpus.documents
        if d.category == DocCategory.CONTRACT
    }
    acme = contracts["AcmeCloud"].spans[0].text
    north = contracts["NorthLink"].spans[0].text
    assert "99.9%" in acme and "99.5%" in north


def test_threshold_precision_trap_present():
    """POL-001 ($50k) and POL-002 ($25k) are surface-similar but distinct."""
    corpus = build_corpus()
    by_id = {d.doc_id: d for d in corpus.documents}
    assert "$50,000" in by_id["POL-001"].spans[1].text
    assert "$25,000" in by_id["POL-002"].spans[1].text


def test_golden_covers_each_answer_type():
    corpus = build_corpus()
    types = {g.answer_type for g in corpus.golden}
    assert AnswerType.GROUNDED in types
    assert AnswerType.UNANSWERABLE in types
    assert AnswerType.MULTI_HOP in types


def test_invalid_golden_rejected():
    """A grounded item with no spans must fail validation."""
    with pytest.raises(ValueError):
        GoldenItem(
            qid="Q-999",
            question="x",
            answer_type=AnswerType.GROUNDED,
            supporting_span_ids=[],
            reference_answer="y",
        )


def test_document_rejects_misordered_span_ordinals():
    """The Document validator enforces ordinal == position."""
    with pytest.raises(ValueError):
        Document(
            doc_id="POL-009",
            category=DocCategory.POLICY,
            title="Bad ordinals",
            spans=[
                Span(ordinal=0, text="first"),
                Span(ordinal=5, text="ordinal does not match position"),
            ],
        )


def test_corpus_rejects_golden_referencing_unknown_span():
    """Corpus-level referential integrity rejects dangling citations."""
    doc = Document(
        doc_id="POL-010",
        category=DocCategory.POLICY,
        title="Lone policy",
        spans=[Span(ordinal=0, text="only span")],
    )
    bad = GoldenItem(
        qid="Q-010",
        question="cites a span that does not exist?",
        answer_type=AnswerType.GROUNDED,
        supporting_span_ids=["POL-010#S9"],
        reference_answer="should fail",
    )
    with pytest.raises(ValueError):
        Corpus(documents=[doc], golden=[bad])

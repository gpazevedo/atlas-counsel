"""Extra eval-harness tests beyond the regression gate in test_eval.py.

The original suite proves metric math, the grounding-based refusal, and the
end-to-end regression numbers. These cover the pieces it left untested: the
HeuristicJudge directly, refusal-marker detection, the report renderers, the
Langfuse no-op path, and the CLI entrypoint.
"""

from __future__ import annotations

import sys

from atlas_counsel.chunking import chunk_corpus
from atlas_counsel.corpus import build_corpus
from atlas_counsel.embeddings import HashingEmbedder
from atlas_counsel.eval import evaluate, render_ab_table, render_by_tag
from atlas_counsel.eval.judge import HeuristicJudge, looks_like_refusal
from atlas_counsel.eval.report import maybe_log_to_langfuse
from atlas_counsel.retrieval import InMemoryHybridRetriever


def _report(label="ci", dense_dim=256):
    r = InMemoryHybridRetriever(HashingEmbedder(space_id=label, dense_dim=dense_dim))
    r.index(chunk_corpus(build_corpus()))
    return evaluate(r, build_corpus().golden, label=label, k=5)


# --- HeuristicJudge ---------------------------------------------------------

def test_judge_faithfulness_high_when_answer_grounded_in_context():
    j = HeuristicJudge()
    res = j.judge(
        question="What is the single-source threshold?",
        answer="single-source purchases at or above $50,000 need justification",
        context=["Any single-source purchase at or above $50,000 requires written justification"],
    )
    assert res.faithfulness >= 0.8


def test_judge_faithfulness_low_when_answer_invents_tokens():
    j = HeuristicJudge()
    res = j.judge(
        question="What is the threshold?",
        answer="purchases above $999,999 require blockchain notarization quantum approval",
        context=["Any single-source purchase at or above $50,000 requires justification"],
    )
    assert res.faithfulness < 0.5


def test_judge_relevancy_tracks_question_overlap():
    j = HeuristicJudge()
    on = j.judge("uptime guarantee for NorthLink", "NorthLink uptime guarantee is 99.5%", ["NorthLink uptime 99.5%"])
    off = j.judge("uptime guarantee for NorthLink", "the cafeteria serves lunch at noon", ["cafeteria lunch noon"])
    assert on.answer_relevancy > off.answer_relevancy


def test_looks_like_refusal_detects_markers():
    assert looks_like_refusal("I cannot answer this from the corpus")
    assert not looks_like_refusal("The threshold is $50,000 per POL-001")


# --- report rendering -------------------------------------------------------

def test_render_by_tag_lists_planted_hard_cases():
    out = render_by_tag(_report())
    assert "Per-tag breakdown" in out
    for tag in ("threshold-precision", "contradiction", "unanswerable"):
        assert tag in out


def test_render_ab_table_has_both_labels_and_delta():
    a = _report("hashing-256", 256)
    b = _report("hashing-512", 512)
    out = render_ab_table(a, b)
    assert "hashing-256" in out and "hashing-512" in out
    assert "Δ(B-A)" in out
    for metric in ("hit_at_k", "context_precision", "refusal_accuracy"):
        assert metric in out


# --- langfuse no-op ---------------------------------------------------------

def test_langfuse_is_noop_without_config(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    assert maybe_log_to_langfuse(_report()) is False


# --- CLI --------------------------------------------------------------------

def test_eval_cli_prints_aggregate_and_breakdown(capsys, monkeypatch):
    from atlas_counsel.eval import __main__ as eval_cli

    monkeypatch.setattr(sys, "argv", ["atlas-eval"])
    eval_cli.main()
    out = capsys.readouterr().out
    assert "Aggregate:" in out
    assert "Per-tag breakdown" in out


def test_eval_cli_ab_flag_renders_table(capsys, monkeypatch):
    from atlas_counsel.eval import __main__ as eval_cli

    monkeypatch.setattr(sys, "argv", ["atlas-eval", "--ab"])
    eval_cli.main()
    out = capsys.readouterr().out
    assert "A/B eval" in out

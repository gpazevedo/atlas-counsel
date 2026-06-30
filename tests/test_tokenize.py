"""Tests for the shared tokenizer and precomputed chunk tokens.

PR #8 centralizes tokenization in `_tokenize` and precomputes each Chunk's
tokens so downstream stages reuse them instead of re-running regex. These tests
pin the tokenizer's contract and that chunking populates the precomputed field;
the behaviour-preservation of the refactor itself is covered by the existing
eval/rerank/judge suites continuing to pass.
"""

from __future__ import annotations

from atlas_counsel._tokenize import STOPWORDS, content_tokens, tokenize
from atlas_counsel.chunking import chunk_corpus
from atlas_counsel.corpus import build_corpus


def test_tokenize_lowercases_and_keeps_numeric_units():
    toks = tokenize("Any purchase at or above $25,000 needs 99.5% uptime")
    # $25,000 and 99.5% survive as single lexical units (the trap tokens).
    assert "$25,000" in toks
    assert "99.5%" in toks
    assert toks == [t.lower() for t in toks]


def test_content_tokens_filters_stopwords_and_short_tokens():
    ct = content_tokens("the value of a single-source purchase")
    assert "the" not in ct and "of" not in ct and "a" not in ct  # stopwords
    assert all(len(t) >= 3 for t in ct)                          # min length
    assert "single" in ct and "source" in ct


def test_content_tokens_honours_extra_stop():
    ct = content_tokens("supplier gift policy", extra_stop={"policy"})
    assert "policy" not in ct
    assert "supplier" in ct and "gift" in ct


def test_min_len_is_configurable():
    assert "is" not in content_tokens("is it ok", min_len=3)
    assert "it" in content_tokens("it ok", min_len=2)


def test_stopwords_includes_expected_function_words():
    for w in ("the", "of", "and", "is", "what"):
        assert w in STOPWORDS


def test_chunk_corpus_precomputes_tokens():
    chunks = chunk_corpus(build_corpus())
    assert chunks
    for c in chunks:
        # Every chunk carries tokens, and they equal a fresh tokenize() of its text.
        assert c.tokens == tokenize(c.text)
        assert c.tokens  # non-empty for real spans

"""Tests for the corpus writer.

The writer turns a validated Corpus into on-disk artifacts the ingest pipeline
and eval harness consume. These tests cover what the generator tests do not:
that the files land, the manifest indexes every span, the golden set serializes
one-item-per-line, span ids are recoverable from the markdown, and the whole
emission is deterministic.
"""

from __future__ import annotations

import json

from atlas_counsel.corpus import build_corpus, write_corpus


def test_write_corpus_emits_expected_files_and_stats(tmp_path):
    corpus = build_corpus()
    stats = write_corpus(corpus, tmp_path)

    corpus_dir = tmp_path / "data" / "corpus"
    eval_dir = tmp_path / "data" / "eval"

    assert (corpus_dir / "manifest.json").exists()
    assert (eval_dir / "golden.jsonl").exists()
    md_files = list(corpus_dir.glob("*.md"))
    assert len(md_files) == len(corpus.documents)

    assert stats == {
        "documents": len(corpus.documents),
        "spans": sum(len(d.spans) for d in corpus.documents),
        "golden_items": len(corpus.golden),
    }


def test_manifest_indexes_every_span(tmp_path):
    corpus = build_corpus()
    write_corpus(corpus, tmp_path)
    manifest = json.loads((tmp_path / "data" / "corpus" / "manifest.json").read_text())

    expected = {s.span_id for d in corpus.documents for s in d.spans}
    indexed = {row["span_id"] for row in manifest["spans"]}
    assert indexed == expected
    assert {row["doc_id"] for row in manifest["documents"]} == {
        d.doc_id for d in corpus.documents
    }


def test_golden_jsonl_round_trips_one_item_per_line(tmp_path):
    corpus = build_corpus()
    write_corpus(corpus, tmp_path)
    lines = (tmp_path / "data" / "eval" / "golden.jsonl").read_text().splitlines()

    assert len(lines) == len(corpus.golden)
    qids = {json.loads(line)["qid"] for line in lines}
    assert qids == {g.qid for g in corpus.golden}


def test_span_anchor_recoverable_from_markdown(tmp_path):
    corpus = build_corpus()
    write_corpus(corpus, tmp_path)
    corpus_dir = tmp_path / "data" / "corpus"

    for doc in corpus.documents:
        md = (corpus_dir / f"{doc.doc_id}.md").read_text()
        for span in doc.spans:
            assert f"<!-- span:{span.span_id} -->" in md


def test_writer_is_deterministic(tmp_path):
    corpus = build_corpus()
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    write_corpus(corpus, root_a)
    write_corpus(corpus, root_b)

    files_a = sorted((root_a / "data").rglob("*"))
    rel = [p.relative_to(root_a) for p in files_a if p.is_file()]
    assert rel, "expected files to be written"
    for r in rel:
        assert (root_a / r).read_bytes() == (root_b / r).read_bytes()

"""Ingest CLI smoke test.

Exercises the offline `--dry-run` path end to end (build -> chunk -> index ->
search) without touching Qdrant, so the CLI wiring is covered in CI.
"""

from __future__ import annotations

import sys

from atlas_counsel import ingest


def test_ingest_dry_run_indexes_and_searches(capsys, monkeypatch):
    monkeypatch.setattr(
        sys, "argv",
        ["atlas-ingest", "--dry-run", "--query", "single-source justification threshold"],
    )
    ingest.main()
    out = capsys.readouterr().out

    assert "[dry-run] indexed 24 chunks" in out
    assert "counsel_hashing-v1" in out          # collection name encodes the space
    assert "#S" in out                          # results print a citable span id

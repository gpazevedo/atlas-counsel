# ATLAS Counsel

**Citation-grounded agentic RAG over a synthetic procurement corpus.**

A LangGraph agent that answers procurement-policy and contract questions, grounds
every claim in a retrievable source span, refuses when the corpus doesn't cover the
question, and pauses for a human when it isn't sure.

The project is built to be *measured*: it runs offline and reproducibly in CI, then
swaps to real models and a real vector store in production via config, not code
changes. This README grows alongside the implementation, one pull request at a time.

## Quickstart

```bash
uv sync --extra dev
atlas-corpus          # generate the corpus under ./data
uv run python -m atlas_counsel.ingest --dry-run   # in-memory retrieval demo
uv run python -m atlas_counsel.eval               # offline eval + per-tag breakdown
uv run pytest
```

## The corpus and golden set

The corpus is **fully seeded and template-driven — no LLM calls, no network**. Same
inputs in, byte-identical corpus out. That determinism is what makes the downstream
evaluation numbers trustworthy and keeps the repo public-safe.

- **8 documents / 24 citable spans**: procurement policies, vendor MSAs, and a
  negotiation log. Each span carries a stable id (e.g. `POL-001#S1`) so the golden
  set and the retriever can cite it directly — the citation contract holds end to end.
- **8 golden Q/A items** across three answer types: `grounded` (answer lives in
  specific spans), `multi_hop` (combine spans across documents), and `unanswerable`
  (absent by design — the agent must refuse).

Every artifact is a validated Pydantic model, and the `Corpus` model enforces
referential integrity: a golden item cannot reference a span that no document
contains.

### Planted hard cases

| Trap                | Where                                           | What it tests            |
| ------------------- | ----------------------------------------------- | ------------------------ |
| Contradiction       | AcmeCloud 99.9% vs NorthLink 99.5% uptime       | cross-document reasoning |
| Threshold precision | POL-001 ($50k) vs near-duplicate POL-002 ($25k) | reranker precision       |
| Unanswerable        | supplier-gift question (Q-006)                  | refuse-if-ungrounded     |
| Anti-splitting      | $120k split question (Q-007)                    | policy reasoning         |

`atlas-corpus` writes one markdown file per document (with recoverable
`<!-- span:ID -->` anchors), a `manifest.json` span index, and `golden.jsonl` for
the eval harness.

## Retrieval design

- **Hybrid, native.** Each chunk carries a dense vector and a sparse (lexical)
  vector; queries fuse both channels with Reciprocal Rank Fusion (RRF). The sparse
  channel rescues exact tokens — `$25,000`, `99.5%` — that a semantic dense model
  smears together. `tests/test_retrieval.py` proves a real fusion win on a query
  where the two channels disagree.
- **Vector-space safety by construction.** Each embedding provider declares a
  `space_id`, and the collection name is derived from it (`counsel_bge-m3`,
  `counsel_titan-v2`). A local-dev index and a prod index are physically separate
  collections — you cannot query one space against the other by accident.
- **Provider abstraction.** `EmbeddingProvider` is a Protocol yielding dense +
  sparse per text. `HashingEmbedder` is a deterministic, offline stand-in for CI;
  real bge-m3 (dev) and Titan (prod) providers implement the same interface, so
  dev/prod is a config swap, not a code branch.

Two backends implement the same `Retriever` protocol: `InMemoryHybridRetriever`
(reference RRF fusion, no services, used in CI) and `QdrantHybridRetriever`
(Qdrant named vectors + server-side RRF via the Query API). Both return chunks
carrying their `span_id`, so downstream citation checking is identical regardless
of backend.

### Running against a real Qdrant

```bash
docker compose up -d
uv sync --extra qdrant
uv run python -m atlas_counsel.ingest --url http://localhost:6333
uv run pytest tests/test_qdrant_integration.py -v
```

The integration test skips automatically when `qdrant-client` is absent or no
server is reachable, so the default offline suite never depends on it.

## Evaluation harness

Measured *before* the agent exists, so every later change is regression-checked
rather than asserted.

```bash
uv run python -m atlas_counsel.eval        # aggregate + per-tag breakdown
uv run python -m atlas_counsel.eval --ab   # A/B two embedding configs
```

- **Retrieval metrics** (no LLM, exact): hit@k, context recall, AP-style context
  precision, and MRR — scored against the golden set's known `supporting_span_ids`.
- **Answer metrics** behind an `LLMJudge` protocol: a deterministic `HeuristicJudge`
  runs in CI; inject an LLM-backed judge locally for faithfulness / answer-relevancy
  at full fidelity.
- **Refuse-if-ungrounded** is a scored dimension in its own right. The decision uses
  *lexical grounding overlap*, not retrieval score — RRF fusion scores are rank-based
  and carry no absolute relevance signal, so a score threshold can't tell answerable
  from unanswerable.
- **Per-tag slicing** reports each planted hard case separately, proving the hard ones
  are handled, not just the easy ones.
- **A/B table** across two embedding providers is the harness's native output — the
  artifact the provider abstraction exists to produce.
- A **regression gate** (`tests/test_eval.py`) locks in current aggregate quality so
  future changes fail loudly instead of degrading silently.
- **Langfuse** export is optional (`uv sync --extra langfuse`, set `LANGFUSE_*`); a
  silent no-op otherwise, so CI never depends on it.

## License

GNU AGPL v3 — see [LICENSE](LICENSE).

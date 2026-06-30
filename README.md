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

Tokenization is centralized in a single `_tokenize` module, and each `Chunk`
carries its tokens precomputed at chunking time — so the reranker, judge, and
answerer reuse them instead of re-running regex over the same text on the hot path.

### Advanced stages: rerank + query decomposition

Two optional stages compose around the base retriever via `RetrievalPipeline`,
each independently toggleable so the eval harness can attribute any metric change
to a specific stage:

```text
query --(decompose?)--> sub-queries --retrieve + merge--> --(rerank?)--> top_k
```

- **Reranking** — `TokenInteractionReranker` is a deterministic offline proxy for
  CI (token interaction + a phrase-adjacency bonus, scored without ever consulting
  golden spans). `CrossEncoderReranker` wraps bge-reranker-v2-m3 for production.
- **Query decomposition** — conditional by design: a query is split only when it
  names ≥ 2 known entities *and* carries a comparison cue, so simple queries pass
  through untouched. Multi-hop questions retrieve per-entity and merge, recovering
  the starved side.

```bash
uv run python -m atlas_counsel.ablation   # baseline vs +rerank vs +decompose vs +both
```

On this small corpus, first-stage hybrid nearly saturates retrieval, so the offline
lexical proxies show **no net gain** — and that's reported, not hidden. The stages
ship as correct, unit-tested infrastructure; the production cross-encoder and an LLM
decomposer are the implementations expected to win, confirmed through this same
harness. The proxies are deliberately *not* tuned toward the golden spans to
manufacture an improvement.

## The agent: LangGraph StateGraph

A compiled `StateGraph` with conditional routing, a checkpointed human-gate, and
a bounded verify/retry loop.

```bash
uv run python -m atlas_counsel.agent --q "who approves a $60,000 purchase?"
uv run python -m atlas_counsel.agent --q "policy on supplier gifts?" --decline
```

```text
plan -> retrieve -> validate --grounded--> synthesize -> verify --pass--> finalize
                            \--insufficient--> human_gate          \--unfaithful--/ (bounded retry)
                                                                      \--exhausted--> human_gate
```

- **Structured outputs / citation grounding.** `synthesize` emits a Pydantic
  `DraftAnswer` whose every `Claim` carries a `span_id`; `verify` rejects any claim
  citing a span that wasn't retrieved (or whose text drifted from it) — proven by
  `test_hallucination_is_bounded_and_escalates`. A hallucinated citation is caught
  before it ships, by the type system and a verify node, not by prompt politeness.
- **Human-assisted decisions.** `human_gate` uses LangGraph `interrupt()`; the run
  pauses and the caller resumes with `Command(resume=...)` to steer or decline. State
  survives the pause via the injected checkpointer.
- **Bounded loops.** The verify -> synthesize retry is capped at `MAX_ATTEMPTS`, then
  escalates — no unbounded LLM spinning.
- **Provider abstraction.** An `LLMProvider` protocol with an offline `TemplateLLM`
  for CI (cites only retrieved spans, never fabricates) and real Ollama/Bedrock
  injected locally. The checkpointer is injected too: `MemorySaver` (dev) or a
  Sqlite saver (prod), without changing the graph topology.

### Gap-aware iterative retrieval

When `validate` finds the retrieved spans don't sufficiently ground the
question, the graph doesn't escalate immediately: a `gap_analyze` node asks the
LLM which of the question's content tokens are still uncovered, issues those as
follow-up queries, and loops back through `retrieve` — whose results *merge into*
(rather than replace) the existing set, so coverage accumulates. The loop is
bounded by `MAX_GAP_ITERATIONS`; once exhausted without sufficient grounding, it
falls through to the human gate. A genuinely unanswerable question therefore
still escalates, just after exhausting cheap self-help first.

### Optional human-in-the-loop

The human gate is on by default, but unattended deployments can disable it:
`build_counsel_graph(..., hitl_enabled=False)` (or `CounselService(hitl_enabled=False)`,
or the agent CLI's `--no-hitl`). With it off, a run that would otherwise pause —
exhausted gap-analysis or exhausted synthesis retries — instead routes straight
to `finalize` and returns a plain refusal rather than blocking on a human. User-
facing refusal text and the MCP tool descriptions are domain-neutral (no
hard-coded "procurement" wording), so the same service fronts any corpus.

## Runtime: FastAPI + MCP

The graph is exposed over two transports, both thin wrappers over one
`CounselService` — so HTTP and MCP behave identically (proven by
`test_mcp_and_http_agree`).

```bash
uv sync --extra service
uv run uvicorn atlas_counsel.service.api:app        # HTTP on :8000
uv run python -m atlas_counsel.service.mcp_server   # MCP stdio server
```

**REST**

- `POST /ask {question}` -> `{status, thread_id, answer, citations[]}`
- `POST /resume {thread_id, action, guidance?}` -> same shape
- `WS /ws/ask` -> streams `{event:"node", node}` per step, then a terminal
  `result` / `needs_input` frame

**Interrupt across stateless calls.** The agent pauses at the human-gate via
LangGraph `interrupt()`, but HTTP/MCP are request/response. So a paused run returns
`status="needs_input"` plus a `thread_id`; a second `/resume` call continues it. The
checkpointer carries state across those two otherwise-independent calls — the core
integration design.

### Buyer Team integration

The compiled graph is exposed as MCP tools — `counsel_ask`, `counsel_resume`,
`counsel_brief` — so Buyer Team's orchestrator calls it as one tool among its own.
Run locally over stdio; see `buyer-team-mcp.example.json` for the client entry. A
`Dockerfile` packages the FastAPI service and MCP server in one image.

## Multi-tier memory

An optional `memory/` layer gives the agent cross-session recall across three
tiers, each with its own access pattern:

- **Semantic** — durable facts written explicitly, retrieved by embedding similarity.
- **Episodic** — one rolling per-thread summary, upserted and retrieved by similarity.
- **Procedural** — learned prompt fragments with `when_to_use` cues, retrieved just in time.

`MemoryStore` is a Protocol with two implementations: `InMemoryMemoryStore`
(dict-based, embedder-driven, for CI) and `SqliteMemoryStore` (per-tenant SQLite
with JSON embeddings, similarity computed in Python — fine at per-tenant scale).
When a `memory_store` is injected, `build_counsel_graph` inserts a `load_memory`
node before `plan` (which folds recalled facts/episodes/skills into the question)
and a `save_memory` node after `finalize` (which reflects on the answer and
persists new memories). Without one, the graph is unchanged — memory is strictly
additive and backward compatible. The service wires a per-tenant
`SqliteMemoryStore` automatically, so recall is tenant-scoped like checkpoints.

## Resilience

Production hardening so transient failures degrade gracefully instead of erroring:

- **Durable checkpointer.** `CounselService` defaults to a SQLite-backed
  `SqliteSaver` (path via `COUNSEL_CHECKPOINT_DB`), so a paused human-gate run
  survives a process restart and is still resumable.
- **Qdrant retry + timeout.** The Qdrant retriever's `ensure_collection`, `index`,
  and `search` are wrapped with exponential-backoff retries on connection/timeout
  errors (and only those), with a bounded client timeout.
- **In-memory fallback.** A `FallbackRetriever` wraps the primary retriever; if it
  fails, requests silently degrade to the pre-indexed in-memory index, with a
  `try_restore` probe to recover.
- **Input validation.** Request models bound question length and constrain the
  resume `action`; oversize or malformed input is rejected with 422.
- **Deep health.** `GET /health` (and the `counsel_health` MCP tool) probe the
  graph and checkpointer, not just liveness, returning `degraded` when a
  dependency is unhealthy. An unhandled error returns a structured `error` result
  rather than a bare 500.

## Observability

OpenTelemetry tracing is wired through the service with a strict no-op default:
the `telemetry` module activates only when the OTEL SDK is installed (the `otel`
extra) *and* `OTEL_EXPORTER_OTLP_ENDPOINT` is set — otherwise every tracer and
span is a silent no-op, so neither tests nor local runs need a collector. When
enabled, spans wrap `counsel.ask` / `counsel.resume` / `counsel.astream` and
`tenant.create` (tagged with `tenant_id`, `thread_id`, and request size), the
FastAPI app is auto-instrumented, and spans are batched to an OTLP endpoint.

```bash
uv sync --extra service --extra otel
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=atlas-counsel
```

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

## Multi-tenancy

`CounselService` is tenant-aware: each `tenant_id` gets its own SQLite
checkpointer at `${CHECKPOINT_DIR}/{tenant_id}/checkpoints.db`, while the
retriever (the read-only corpus) is shared. Graphs are compiled lazily per
tenant and cached. Tenant ids must match `^[a-z0-9]([a-z0-9-]*[a-z0-9])?$`
(max 64 chars) to keep them filesystem- and path-safe. A `thread_id` is only
resumable by the tenant that created it; a cross-tenant resume returns a
structured `error` rather than leaking or crashing.

REST and MCP both accept `tenant_id` (defaulting to `"default"`):

```
POST /ask     {tenant_id, question}
POST /resume  {tenant_id, thread_id, action, guidance?}
```

## Remote MCP

The MCP server runs two ways from the same `CounselService`:

- **stdio** (local dev): `python -m atlas_counsel.service.mcp_server`
- **Streamable HTTP** (deployed): mounted at `/mcp` on the FastAPI app, so REST
  and MCP share one port and one `TenantRegistry`.

See `buyer-team-mcp.example.json` for local and remote client entries.

## Authentication

The `/mcp` endpoint is guarded by a small ASGI middleware (REST routes are
unaffected). It supports two schemes:

- **JWT** (`Authorization: Bearer …`, HS256) — the token's `tenant_id` claim
  selects the tenant, so one deployment serves many isolated customers. Audience
  is verified when `MCP_JWT_AUDIENCE` is set.
- **API key** (`x-api-key`) — single-tenant fallback, compared in constant time
  with `hmac.compare_digest`.

Behaviour is fail-safe: with neither `MCP_API_KEY` nor `MCP_JWT_SECRET` set the
endpoint runs unauthenticated but logs a startup warning, and if
`MCP_REQUIRE_AUTH` is set without any secret the app refuses to boot. The MCP
tools never accept a `tenant_id` argument — it's derived from the verified auth
context (a `current_tenant` ContextVar), so a caller can't act as another tenant.
In production, Terraform provisions the secrets and the HTTPS listener (see
Deployment).

## Deployment

Infrastructure-as-code lives in `infra/` (Terraform): a VPC, an Application
Load Balancer, ECS Fargate running the container, EFS for per-tenant
checkpoints, ECR for images, and a GitHub Actions OIDC role for keyless
deploys. Remote state is kept in S3 with DynamoDB-based locking. CI
(`.github/workflows/ci.yml`) runs the test matrix on every push/PR; deploy
(`deploy.yml`) builds and pushes to ECR and rolls the ECS service on push to
`main`, authenticating via OIDC (no long-lived AWS keys). See `infra/README.md`
for the one-time state/OIDC bootstrap and `terraform apply`.

## Meta-evaluation: judging the judge

The offline `HeuristicJudge` is only trustworthy if its scores reflect content,
not surface style. `eval/meta_eval.py` probes for that: it generates an answer
per answerable golden item, then creates content-preserving perturbations that
change only surface features — fluent vs. choppy phrasing, confident vs. hedging
tone — and measures how much the judge's faithfulness/relevancy move between
variants. A fair judge shows deltas near zero (the token-overlap judge does,
which also proves the perturbations preserve content); a real LLM judge would
reveal genuine fluency/confidence bias. It also reports Spearman correlation
between judge scores and retrieval quality (precision/recall), all with a pure
Python rank-correlation and no extra dependencies.

```bash
python -m atlas_counsel.eval --meta
```

## License

GNU AGPL v3 — see [LICENSE](LICENSE).

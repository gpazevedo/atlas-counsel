# ADR-0003: Eval-first: harness and CI regression gate before the agent

- **Status:** Accepted
- **Implemented in:** PR #4

## Context

RAG quality regresses invisibly. We want quality to be a measured, enforced property rather than a vibe.

## Decision

Build the evaluation harness before the agent. Provide exact retrieval metrics (hit@k, recall, context-precision, MRR vs golden span IDs) and judge metrics (faithfulness, relevancy, refuse-if-ungrounded), plus per-tag slices, A/B comparison, and ablation. A regression gate runs in CI and fails loudly on a quality drop.

## Alternatives considered

- **Manual / spot-check evaluation** — does not scale; regressions slip through.
- **Eval added after the agent** — bakes in untested assumptions and provides no baseline.

## Consequences

**Positive**

- Every change is measured against a baseline; the harness drives tuning (RRF weights, chunk size, rerank depth, gap thresholds).
- Refusal behavior is a first-class, tested outcome.

**Negative / costs**

- The golden set and metrics must be maintained alongside the corpus.
- A deterministic judge is required for CI to be reproducible (see ADR-0005).

# ADR-0005: Provider abstraction via Protocols with deterministic offline defaults

- **Status:** Accepted
- **Implemented in:** PR #3–#5 (protocols); real backends pending

## Context

We want to develop and test deterministically and offline, yet run real models in production, without backend-selection branches scattered through the pipeline.

## Decision

Define narrow `Protocol` interfaces for the swappable backends — `EmbeddingProvider`, `Reranker`, `LLMProvider`, `LLMJudge`. Ship deterministic offline implementations as the default (`HashingEmbedder`, `TokenInteractionReranker`, `TemplateLLM`, `HeuristicJudge`) and treat real backends (bge-m3 / Titan embeddings, a cross-encoder reranker, Ollama / Bedrock LLMs, a real LLM judge) as injected, opt-in implementations selected by configuration — not a code branch.

## Alternatives considered

- **Hard-code a real model** — non-deterministic CI; requires network/GPU; not reproducible.
- **Feature flags / if-else per backend** — branching logic leaks into business code.

## Consequences

**Positive**

- CI is deterministic, offline, fast, and free; the same code path runs stubs or real models.
- Clean seam for benchmarking backends through the eval harness.

**Negative / costs**

- The shipped defaults are stubs: out of the box, retrieval is only as good as a hash and answers only as good as a template. Real backends must be implemented for the system to be genuinely useful (the current top priority). The abstraction can also mask integration bugs until a real backend is wired.

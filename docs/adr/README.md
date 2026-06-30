# Architecture Decision Records

This directory records the significant architectural decisions for Atlas Counsel using the lightweight ADR format — one decision per file: context, decision, alternatives, and consequences.

Most ADRs are **retrospective and Accepted**: they document decisions already embodied in the codebase, each linked to the PR(s) that implemented it. ADRs in **Proposed** status (0019–0021) record decisions the team intends to make but has not yet implemented; their consequences are anticipated rather than observed.

**Convention.** Add a new decision as the next numbered file. Once an ADR is accepted, do not rewrite it — supersede it with a new ADR and mark the old one *Superseded by ADR-NNNN*. A Proposed ADR is promoted to *Accepted* (with an **Implemented in** link) when the work lands.

## Index

| # | Status | Decision | Ref |
|---|--------|----------|-----|
| [0001](0001-citation-span-id-contract.md) | Accepted | Stable span IDs as the citation contract | PR #1–#2 |
| [0002](0002-synthetic-deterministic-corpus.md) | Accepted | Synthetic, deterministic corpus | PR #2 |
| [0003](0003-eval-first-regression-gate.md) | Accepted | Eval-first: harness and CI regression gate before the agent | PR #4 |
| [0004](0004-hybrid-retrieval-qdrant.md) | Accepted | Hybrid retrieval on Qdrant with named vectors, one collection per embedding space | PR #3 |
| [0005](0005-provider-abstraction-protocols.md) | Accepted | Provider abstraction via Protocols with deterministic offline defaults | PR #3–#5 (protocols); real backends pending |
| [0006](0006-langgraph-stategraph.md) | Accepted | LangGraph StateGraph with explicit decision nodes | PR #6 |
| [0007](0007-structured-output-verify.md) | Accepted | Structured-output synthesis with a verify (faithfulness self-check) node | PR #6 |
| [0008](0008-bounded-gap-retrieval.md) | Accepted | Bounded gap-aware iterative retrieval | PR #12 |
| [0009](0009-durable-checkpointing.md) | Accepted | Durable checkpointing and resumable runs | PR #7, #9 |
| [0010](0010-per-tenant-isolation.md) | Accepted | Per-tenant isolation | PR #10 |
| [0011](0011-mcp-integration-boundary.md) | Accepted | MCP as the integration boundary; one service backs two transports | PR #7 (+ remote MCP in #10) |
| [0012](0012-auth-tenant-binding.md) | Accepted | Authentication and tenant binding from the auth context | PR #16 |
| [0013](0013-multi-tier-memory.md) | Accepted | Multi-tier memory (semantic, episodic, procedural) | PR #15 |
| [0014](0014-optional-hitl.md) | Accepted | Optional human-in-the-loop, on by default | PR #14 (human-gate in #6) |
| [0015](0015-observability-otel.md) | Accepted | Observability via OpenTelemetry; Langfuse optional in eval | PR #11 |
| [0016](0016-aws-deployment-iac.md) | Accepted | AWS deployment topology and IaC conventions | PR #10 (+ HTTPS/Secrets in #16) |
| [0017](0017-memory-write-gating.md) | Accepted | Gate memory writes to verified, grounded answers | PR #19 |
| [0018](0018-injection-defense.md) | Accepted | Indirect prompt-injection defense at the retrieval boundary | PR #19 |
| [0019](0019-real-backends.md) | Proposed | Implement real embedding, reranker, LLM, and judge backends | — |
| [0020](0020-real-corpus-validation.md) | Proposed | Validate on a private real-document corpus | — |
| [0021](0021-networked-state-store.md) | Proposed | Networked checkpoint and memory store for horizontal scale | — |

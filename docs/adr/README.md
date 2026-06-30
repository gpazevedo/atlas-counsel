# Architecture Decision Records

This directory records the significant architectural decisions for Atlas Counsel using the lightweight ADR format — one decision per file: context, decision, alternatives, and consequences.

These ADRs are **retrospective**: they document decisions already embodied in the codebase, reconstructed from the implementation and its PR history. Each links to the PR(s) that implemented it. Status is *Accepted* unless noted.

**Convention.** Add a new decision as the next numbered file. Once an ADR is accepted, do not rewrite it — supersede it with a new ADR and mark the old one *Superseded by ADR-NNNN*.

## Index

| # | Decision | Implemented in |
|---|----------|----------------|
| [0001](0001-citation-span-id-contract.md) | Stable span IDs as the citation contract | PR #1–#2 |
| [0002](0002-synthetic-deterministic-corpus.md) | Synthetic, deterministic corpus | PR #2 |
| [0003](0003-eval-first-regression-gate.md) | Eval-first: harness and CI regression gate before the agent | PR #4 |
| [0004](0004-hybrid-retrieval-qdrant.md) | Hybrid retrieval on Qdrant with named vectors, one collection per embedding space | PR #3 |
| [0005](0005-provider-abstraction-protocols.md) | Provider abstraction via Protocols with deterministic offline defaults | PR #3–#5 (protocols); real backends pending |
| [0006](0006-langgraph-stategraph.md) | LangGraph StateGraph with explicit decision nodes | PR #6 |
| [0007](0007-structured-output-verify.md) | Structured-output synthesis with a verify (faithfulness self-check) node | PR #6 |
| [0008](0008-bounded-gap-retrieval.md) | Bounded gap-aware iterative retrieval | PR #12 |
| [0009](0009-durable-checkpointing.md) | Durable checkpointing and resumable runs | PR #7, #9 |
| [0010](0010-per-tenant-isolation.md) | Per-tenant isolation | PR #10 |
| [0011](0011-mcp-integration-boundary.md) | MCP as the integration boundary; one service backs two transports | PR #7 (+ remote MCP in #10) |
| [0012](0012-auth-tenant-binding.md) | Authentication and tenant binding from the auth context | PR #16 |
| [0013](0013-multi-tier-memory.md) | Multi-tier memory (semantic, episodic, procedural) | PR #15 |
| [0014](0014-optional-hitl.md) | Optional human-in-the-loop, on by default | PR #14 (human-gate in #6) |
| [0015](0015-observability-otel.md) | Observability via OpenTelemetry; Langfuse optional in eval | PR #11 |
| [0016](0016-aws-deployment-iac.md) | AWS deployment topology and IaC conventions | PR #10 (+ HTTPS/Secrets in #16) |

# ADR-0009: Durable checkpointing and resumable runs

- **Status:** Accepted
- **Implemented in:** PR #7, #9

## Context

Human-gated and long-running graph executions must survive process boundaries and stateless HTTP/MCP calls, and external dependencies (Qdrant) can fail transiently.

## Decision

Persist graph state with a durable checkpointer (`SqliteSaver` by default; `MemorySaver` for the dev CLI). Expose a `needs_input` + `thread_id` resume token so a paused run can be continued across stateless calls. Add tenacity-based retries on flaky I/O and a deep health check that exercises the graph, checkpointer, and retriever together.

## Alternatives considered

- **In-memory-only state** — runs lost on restart; no resume across calls.
- **External datastore (Postgres/Redis) from day one** — operational overhead unjustified at this stage.

## Consequences

**Positive**

- Human-in-the-loop and multi-call workflows are reliable and resumable; health is verifiable end-to-end.

**Negative / costs**

- SQLite checkpoints are node-local (EFS-backed in prod), which constrains horizontal scale-out and concurrency; a networked checkpoint store may be needed as load grows.

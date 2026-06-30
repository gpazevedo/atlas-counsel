# ADR-0021: Networked checkpoint and memory store for horizontal scale

- **Status:** Proposed
- **Target:** Future work

## Context

ADR-0009 and ADR-0010 use node-local SQLite (EFS-backed in production) for graph checkpoints and per-tenant memory. Both ADRs recorded the same ceiling: node-local files constrain horizontal scale-out and concurrency and bind state to a node's filesystem, and per-tenant files multiply with the tenant count.

## Proposed decision

When load warrants, move checkpoints and memory to a networked store behind the existing checkpointer and `MemoryStore` seams — e.g. Postgres for LangGraph checkpoints and Postgres + pgvector (or a server-mode vector DB) for memory — preserving per-tenant isolation (ADR-0010) by schema / namespace scoping rather than separate files. Keep SQLite as the dev / single-node default so the offline story is unchanged.

## Alternatives considered

- **Stay on EFS-backed SQLite** — simplest, but the operational ceiling remains.
- **Shard tenants across nodes with sticky routing** — adds routing complexity and uneven load.
- **In-memory only** — loses durability; rejected by ADR-0009.

## Consequences (anticipated)

**Positive**

- Horizontal scale-out, pooled concurrent access, and no EFS coupling.

**Negative / costs**

- New managed infrastructure plus a migration path.
- Isolation now depends on correct query scoping; the cross-tenant leak risk that ADR-0010 avoided with filesystem separation returns and must be tested deliberately.
- Added cost and operational surface.

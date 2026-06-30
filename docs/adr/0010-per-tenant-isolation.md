# ADR-0010: Per-tenant isolation

- **Status:** Accepted
- **Implemented in:** PR #10

## Context

A single deployment must serve multiple customers without leaking data across them.

## Decision

Introduce a `TenantRegistry` providing per-tenant resources — per-tenant `SqliteSaver` checkpoints and a per-tenant `SqliteMemoryStore` at `{tenant}/memory.db`. Validate `tenant_id` (charset and length) to prevent path traversal. Tenant identity threads through `CounselState` and is honored everywhere a run touches state or memory.

## Alternatives considered

- **Single shared store with a tenant column** — one query bug leaks across tenants; weaker isolation.
- **Separate deployment per tenant** — operationally expensive; defeats multi-tenant economics.

## Consequences

**Positive**

- Strong filesystem-level isolation of checkpoints and memory; a simple mental model.

**Negative / costs**

- Per-tenant SQLite files multiply with tenant count and bind state to a node's filesystem; large fleets may need a different backend. Cross-tenant isolation now depends on correct `tenant_id` derivation (see ADR-0012).

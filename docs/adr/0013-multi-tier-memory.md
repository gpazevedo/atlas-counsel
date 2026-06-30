# ADR-0013: Multi-tier memory (semantic, episodic, procedural)

- **Status:** Accepted
- **Implemented in:** PR #15

## Context

Across runs, the agent benefits from recalling tenant-specific facts, prior outcomes, and learned procedures — without leaking across tenants.

## Decision

Add a per-tenant multi-tier memory store (semantic facts, episodic summaries, procedural skills), retrieved by embedding similarity. Wire it into the graph as `load_memory` (before plan) and `save_memory` (after finalize) nodes, which are added only when a memory store is injected (the live service always injects one).

## Alternatives considered

- **No memory** — every run is cold; no personalization or learning.
- **A single flat memory blob** — no distinction between fact, outcome, and procedure; harder to use selectively.

## Consequences

**Positive**

- Cross-run context and personalization; cleanly optional (the graph is identical without a store).

**Negative / costs**

- `save_memory` after `finalize` can persist ungrounded or incorrect answers, risking memory poisoning; persistence should be gated on verified/grounded outcomes and validated (memory-on vs memory-off A/B) before being trusted. Memory adds retrieval cost per run.

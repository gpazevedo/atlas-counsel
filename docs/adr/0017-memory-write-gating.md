# ADR-0017: Gate memory writes to verified, grounded answers

- **Status:** Accepted
- **Implemented in:** PR #19

## Context

`save_memory` runs after `finalize`. Without a gate it persists any non-refused answer — including ungrounded, unfaithful, or human-steered ones — as an episodic “fact”. A later run that recalls a wrong fact is then corrupted by it. ADR-0013 flagged exactly this risk in its consequences; this decision closes it.

## Decision

Persist memory only from *trustworthy* answers. An `_is_trustworthy` predicate requires the answer to be present and not refused, grounded, faithful per the verify node (ADR-0007), not human-escalated, and free of any injection detected during the run (ADR-0018). Untrusted answers are still returned to the caller but never written back. A `memory_persisted` flag records the decision, and an offline memory-on-vs-off A/B (`eval/memory_ab.py`) confirms recall works and is safe before memory is trusted.

## Alternatives considered

- **Persist every non-refused answer (the prior behavior)** — this is the poisoning vector itself.
- **Persist nothing** — discards the cross-run value memory exists for (ADR-0013).
- **Require human approval for every write** — too costly; defeats unattended operation.
- **Persist human-steered answers too** — a human override is lower-confidence and can be socially engineered; excluding it is the conservative default.

## Consequences

**Positive**

- A wrong, ungrounded, or tainted answer can no longer become a remembered fact; later runs are protected.
- The persistence decision is observable (`memory_persisted`) and regression-tested.

**Negative / costs**

- Correct-but-human-steered answers are deliberately not remembered; some useful recall is forgone.
- The gate is only as trustworthy as the verify node backing the faithfulness check.
- Offline the A/B shows no answer delta (synthesis is span-driven); a real LLM backend is needed to quantify memory's benefit.

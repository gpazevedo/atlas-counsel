# ADR-0008: Bounded gap-aware iterative retrieval

- **Status:** Accepted
- **Implemented in:** PR #12

## Context

A single retrieval pass often misses a sub-topic of a multi-faceted question. Unbounded re-retrieval risks non-termination and cost blow-ups.

## Decision

Add a `gap_analyze` node that detects missing-topic tokens after validation and triggers bounded re-retrieval (`MAX_GAP_ITERATIONS = 2`). When the gap budget is exhausted, escalate (human gate) or refuse rather than loop.

## Alternatives considered

- **Single-shot retrieval** — misses multi-topic questions.
- **Unbounded agentic re-retrieval** — non-terminating risk; unpredictable cost and latency.

## Consequences

**Positive**

- Recovers recall on multi-topic questions while guaranteeing termination.
- The bound is an explicit, tunable knob measured by the harness.

**Negative / costs**

- Adds iterations (latency/cost) on hard questions; the missing-topic heuristic can mis-fire.

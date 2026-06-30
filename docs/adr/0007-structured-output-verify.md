# ADR-0007: Structured-output synthesis with a verify (faithfulness self-check) node

- **Status:** Accepted
- **Implemented in:** PR #6

## Context

An LLM can produce fluent but ungrounded answers. Citations must be enforced structurally, and a check must confirm that every claim maps to a retrieved span.

## Decision

Synthesis produces Pydantic-enforced structured output (answer plus citations as span IDs). A dedicated `verify` node performs a faithfulness self-check (“every claim → a span?”); on failure it routes to a bounded synthesize retry, and ultimately to the human gate or a safe refusal.

## Alternatives considered

- **Free-text answers with post-hoc citation extraction** — lossy and unreliable.
- **Trusting synthesis without verification** — defeats the grounding promise.

## Consequences

**Positive**

- Grounding is enforced at the type level and re-checked; refuse-if-ungrounded becomes a real path.
- Structured output is directly scorable by the eval harness.

**Negative / costs**

- Extra LLM round-trips (verify, retries) add latency and cost; the self-check is only as good as the judge backing it.

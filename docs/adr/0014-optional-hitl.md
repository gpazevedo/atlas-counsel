# ADR-0014: Optional human-in-the-loop, on by default

- **Status:** Accepted
- **Implemented in:** PR #14 (human-gate in #6)

## Context

For high-stakes or low-confidence answers a human should be able to steer or decline, but fully automated callers (e.g. batch tool use) need a non-interactive mode.

## Decision

Default to human-in-the-loop: when grounding/faithfulness is exhausted the graph hits a `human_gate` via `interrupt()` and resumes from a checkpoint on `steer` / `decline`. Provide `--no-hitl` to opt out, routing exhausted loops to a safe finalize-refusal instead of pausing.

## Alternatives considered

- **Always human-gated** — blocks automated/orchestrated use.
- **Never human-gated** — removes the safety valve for hard or risky cases.

## Consequences

**Positive**

- A safety valve for hard cases with a clean automated fallback; resumable across stateless calls.

**Negative / costs**

- Two routing modes to test and reason about; HITL implies an operator/UI workflow to be useful in production.

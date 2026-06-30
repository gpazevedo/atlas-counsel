# ADR-0006: LangGraph StateGraph with explicit decision nodes

- **Status:** Accepted
- **Implemented in:** PR #6

## Context

The agent must plan, retrieve, validate grounding, synthesize, self-check, escalate to a human when stuck, and be resumable — with control flow that is auditable and testable.

## Decision

Model the agent as a LangGraph `StateGraph` with explicit nodes (plan, retrieve, validate, gap_analyze, synthesize, verify, human_gate, finalize) and conditional edges, threading a typed `CounselState` through every node via reducers.

## Alternatives considered

- **Linear chain** — cannot express retry loops, gap re-retrieval, or human gates.
- **Free-form ReAct / tool-calling agent** — opaque, non-deterministic control flow; hard to test, checkpoint, and reason about.
- **Hand-rolled state machine** — reinvents checkpointing, interrupts, and streaming that LangGraph provides.

## Consequences

**Positive**

- Control flow is explicit, testable, checkpointable, and streamable; decision nodes map directly to eval-able behaviors.
- Conditional routing supports bounded loops and human escalation cleanly.

**Negative / costs**

- Couples the agent to LangGraph's execution and checkpoint model; disciplined state/reducer design is required.

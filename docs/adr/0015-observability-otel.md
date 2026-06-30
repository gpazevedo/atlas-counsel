# ADR-0015: Observability via OpenTelemetry; Langfuse optional in eval

- **Status:** Accepted
- **Implemented in:** PR #11

## Context

We need production tracing, latency, and error visibility, plus optional LLM-trace logging during evaluation, without coupling the runtime to a single vendor.

## Decision

Use OpenTelemetry as the primary observability layer (spans around ask / resume / astream / tenant-create, plus FastAPI instrumentation). Keep Langfuse strictly optional and confined to the eval path (`maybe_log_to_langfuse`, a no-op when unconfigured).

## Alternatives considered

- **Langfuse as the primary/only layer** — vendor lock-in for core runtime telemetry.
- **No standardized tracing** — blind in production.

## Consequences

**Positive**

- Vendor-neutral, standard traces exportable to any OTLP backend; eval can still use Langfuse when wanted.

**Negative / costs**

- An OTLP backend and SLOs must be configured to get value; two observability concepts (OTel runtime vs Langfuse eval) to understand.

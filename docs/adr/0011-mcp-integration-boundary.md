# ADR-0011: MCP as the integration boundary; one service backs two transports

- **Status:** Accepted
- **Implemented in:** PR #7 (+ remote MCP in #10)

## Context

Atlas Counsel must plug into the Buyer Team orchestrator as a callable tool, and also be reachable directly over HTTP. Behavior must be identical across entry points.

## Decision

Expose the graph as Model Context Protocol (MCP) tools (`counsel_ask`, `counsel_resume`, `counsel_brief`, `counsel_health`), and have a single `CounselService` back both the FastAPI app and the MCP server. Support remote MCP over Streamable HTTP, mounted alongside REST.

## Alternatives considered

- **Bespoke REST contract only** — every consumer reimplements client glue; not a first-class tool for agent orchestrators.
- **Separate logic per transport** — behavior drifts between HTTP and MCP.

## Consequences

**Positive**

- Identical behavior across HTTP and MCP — “this whole graph = one tool” to Buyer Team.
- Streamable HTTP enables remote tool use without a bespoke protocol.

**Negative / costs**

- Couples to the evolving MCP spec; the shared service must stay transport-agnostic.

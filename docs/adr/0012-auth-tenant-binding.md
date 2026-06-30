# ADR-0012: Authentication and tenant binding from the auth context

- **Status:** Accepted
- **Implemented in:** PR #16

## Context

The remote `/mcp` endpoint is internet-exposed and multi-tenant. A caller must not be able to act as another tenant, and an unconfigured deployment must not silently become an open relay.

## Decision

Guard `/mcp` with an ASGI middleware supporting JWT (HS256, `tenant_id` claim, optional audience) and an `x-api-key` fallback compared with `hmac.compare_digest`. Derive the tenant from the verified token into a `current_tenant` ContextVar; MCP tools take no `tenant_id` argument. Fail safe: warn at startup when unauthenticated, and refuse to boot if `MCP_REQUIRE_AUTH` is set without a secret.

## Alternatives considered

- **Caller-supplied tenant_id argument** — trivially spoofable; enables cross-tenant access.
- **No auth / network controls only** — unacceptable for an internet-exposed multi-tenant endpoint.
- **Plain string comparison of API keys** — timing side-channel.

## Consequences

**Positive**

- Tenant identity is cryptographically bound to the request; callers cannot impersonate tenants; key checks are constant-time.
- Fail-safe defaults prevent accidental open endpoints.

**Negative / costs**

- JWT/secret lifecycle (rotation, distribution) is now an operational concern; HS256 shared secrets require careful handling (managed via Secrets Manager — see ADR-0016).

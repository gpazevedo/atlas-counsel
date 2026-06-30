# ADR-0016: AWS deployment topology and IaC conventions

- **Status:** Accepted
- **Implemented in:** PR #10 (+ HTTPS/Secrets in #16)

## Context

Production needs a reproducible, reviewable deployment with durable state, least-privilege access, and secure ingress.

## Decision

Provision with Terraform: ECS Fargate behind an ALB, EFS for durable SQLite checkpoint/memory storage, an ALB HTTPS listener (ACM) with HTTP→HTTPS redirect, and Secrets Manager for the Qdrant URL plus a generated MCP API key and JWT secret. Use S3 + DynamoDB for remote state and locking, GitHub Actions OIDC (keyless) for deploys, current action versions, and keep `.terraform.lock.hcl` committed.

## Alternatives considered

- **Local Terraform state** — no locking or sharing; risky for teams.
- **Long-lived AWS access keys in CI** — credential-leakage risk; OIDC is keyless.
- **Plaintext env vars for secrets** — exposure; Secrets Manager with a scoped read policy is safer.
- **EC2 / Kubernetes** — heavier operations than warranted at this stage.

## Consequences

**Positive**

- Reproducible, least-privilege, secure-by-default infrastructure; keyless CI; locked, shared state.

**Negative / costs**

- EFS-backed SQLite couples state to the filesystem and limits horizontal scale; single-region; the ACM certificate and DNS must be provisioned out of band.

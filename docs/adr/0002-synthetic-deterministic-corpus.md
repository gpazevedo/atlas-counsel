# ADR-0002: Synthetic, deterministic corpus

- **Status:** Accepted
- **Implemented in:** PR #2

## Context

We need a corpus to develop and regression-test retrieval and grounding without depending on proprietary documents, network access, or LLM calls — and it must be safe to publish.

## Decision

Ship a synthetic, template-driven corpus generated deterministically from a seed — no LLM, no network. 8 documents, 24 citable spans, 8 golden question→span mappings, with hard cases (a contradiction between two contracts, near-duplicate policies differing by a single threshold, an anti-splitting reasoning trap) deliberately planted and tagged.

## Alternatives considered

- **Real procurement documents** — licensing/confidentiality risk; not publishable; non-deterministic.
- **LLM-generated corpus** — non-deterministic, network-dependent, and circular — using an LLM to test an LLM pipeline.

## Consequences

**Positive**

- Fully offline, reproducible, and public-safe; CI needs no secrets or GPUs.
- Planted, tagged hard cases let the eval prove specific failure modes are handled.

**Negative / costs**

- Synthetic text under-represents real-world messiness (tables, OCR noise, cross-references); strong synthetic scores do not guarantee real-world performance. Validation on real documents remains necessary.

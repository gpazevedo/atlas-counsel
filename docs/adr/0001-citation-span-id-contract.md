# ADR-0001: Stable span IDs as the citation contract

- **Status:** Accepted
- **Implemented in:** PR #1–#2

## Context

The product promise is citation-grounded answers: every claim must be traceable to a source the user can audit. We need an atomic, stable citation unit that survives chunking, retrieval, and synthesis, and that the eval harness can score deterministically against a golden set.

## Decision

Adopt stable, human-readable span IDs (e.g. `POL-001#S0`) as the atomic unit of citation and the contract between every layer. Chunking preserves a roughly one-chunk-≈-one-span mapping and carries `span_id` through ingestion, retrieval, and into the synthesized answer. A citation is a span ID — not a character offset, a vector ID, or a quoted string.

## Alternatives considered

- **Character offsets / quote spans** — brittle under re-chunking or editing; hard to diff against a golden set.
- **Document-level citations** — too coarse to verify claim-level faithfulness.
- **Opaque vector IDs** — not human-auditable.

## Consequences

**Positive**

- Faithfulness (“every claim → a span”) and retrieval metrics (hit@k, recall, MRR vs golden span IDs) become exact and deterministic.
- Citations are auditable by a human reading the corpus.

**Negative / costs**

- Imposes discipline on the corpus and chunker to keep span IDs stable; re-spanning a document is a breaking change to the golden set.

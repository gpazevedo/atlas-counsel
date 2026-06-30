# ADR-0020: Validate on a private real-document corpus

- **Status:** Proposed
- **Target:** Future work

## Context

ADR-0002's synthetic corpus is offline and public-safe but, as noted there, under-represents real-world messiness — tables, OCR noise, cross-references, scanned PDFs, inconsistent headings. Strong synthetic scores do not guarantee real-world performance, and only real documents will exercise the ingestion and chunking paths that matter.

## Proposed decision

Stand up a private, real-document validation set (a pilot / customer corpus) behind the same stable span-id contract (ADR-0001) and golden format, kept out of the public repository. Run the eval harness against it as a separate, non-public gate, and use the findings to tune chunking and retrieval and to expand the planted hard cases in the synthetic corpus. Pairs with ADR-0019: real corpus plus real backends is the only combination that measures product quality.

## Alternatives considered

- **Synthetic-only** — blind to real ingestion / chunking failure modes.
- **Publish a real corpus** — confidentiality and licensing risk; rejected for the same reasons as ADR-0002.
- **Rely on production telemetry only** — no ground truth to score against.

## Consequences (anticipated)

**Positive**

- Real-world signal; catches document-shape and ingestion gaps the synthetic corpus cannot.
- Lets the synthetic corpus be improved with realistic hard cases.

**Negative / costs**

- A private eval pipeline and data-governance process to maintain; golden labeling on real documents is manual effort.
- Results are not publishable, so this gate lives alongside — not inside — the public CI.

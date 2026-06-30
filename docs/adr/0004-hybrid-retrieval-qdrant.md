# ADR-0004: Hybrid retrieval on Qdrant with named vectors, one collection per embedding space

- **Status:** Accepted
- **Implemented in:** PR #3

## Context

Dense retrieval misses exact-term matches (thresholds, IDs, rare terms that matter in contracts); sparse retrieval misses semantics. We need both, fused, with safe handling of multiple embedding models.

## Decision

Use hybrid retrieval — dense + sparse vectors per chunk — fused with Reciprocal Rank Fusion (RRF), stored in Qdrant using named vectors within a single collection. Derive the collection name from the embedding `space_id` (`counsel_{space_id}`) so vectors from different embedding spaces are never mixed.

## Alternatives considered

- **Dense-only** — weaker on exact thresholds, IDs, and rare terms.
- **Separate collections per vector type** — loses co-location and adds orchestration.
- **Mixing embedding spaces in one collection** — a silent correctness bug when models differ.

## Consequences

**Positive**

- Robust across semantic and lexical queries; RRF is simple and parameter-light.
- `counsel_{space_id}` makes embedding-space safety structural rather than conventional.

**Negative / costs**

- Two vectors per chunk increase index size and ingestion cost; RRF weighting is another tunable.

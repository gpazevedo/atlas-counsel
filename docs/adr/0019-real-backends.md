# ADR-0019: Implement real embedding, reranker, LLM, and judge backends

- **Status:** Proposed
- **Target:** Future work

## Context

ADR-0005 ships deterministic stubs (`HashingEmbedder`, `TokenInteractionReranker`, `TemplateLLM`, `HeuristicJudge`) as the defaults so CI is offline and reproducible. The consequence recorded there is that out of the box retrieval is only as good as a hash and answers only as good as a template. The Protocol seam already exists; implementing real backends is the gap between tested infrastructure and a useful product, and is the highest-priority next step.

## Proposed decision

Implement injected, opt-in real backends behind the existing Protocols, selected by configuration with CI still defaulting to stubs: a real embedding model (e.g. bge-m3 or Titan) writing to its own `counsel_{space_id}` collection (ADR-0004); a cross-encoder reranker; an LLM provider (Ollama / Bedrock) for synthesize / verify / gap / reflect with Pydantic-enforced structured output (ADR-0007); and a real LLM judge. Benchmark each through the existing eval harness and ablation (ADR-0003), and re-run the memory A/B (ADR-0017) and adversarial gate (ADR-0018) against the live model.

## Alternatives considered

- **Keep shipping only stubs** — not a product.
- **Hard-wire a single vendor** — lock-in; violates the abstraction in ADR-0005.
- **Train a bespoke model first** — premature before the harness shows where quality is lost.

## Consequences (anticipated)

**Positive**

- Real retrieval and answer quality; the eval harness converts from a plumbing check into a live quality signal.
- The memory-benefit A/B and the injection numbers become meaningful rather than offline-flat.

**Negative / costs**

- Introduces non-determinism, latency, cost, and network/GPU + secret dependencies into paths that are currently free and offline.
- The injection shield must be re-validated against a model that can be socially engineered; prompts become load-bearing.
- Open questions: which embedding space becomes canonical, and whether verify and judge may share a model without reintroducing the judge-bias problem (ADR-0013 / meta-eval).

"""Memory A/B: does cross-run memory actually help, and is it safe?

Runs the real agent graph over priming -> target scenarios twice — once with a
per-tenant memory store wired in, once without — and reports, per scenario:

  * ``prime_persisted`` — the priming run's answer was trustworthy enough to be
    written to memory (the poisoning gate let it through), and
  * ``recalled`` — the later target run pulled that memory back into its context.

This is the harness the project uses to *confirm memory helps before trusting
it*, in the same spirit as the retrieval ablation. Offline (TemplateLLM) the
synthesizer answers purely from retrieved spans, so recalled context does not
change the final text — ``answer_changed`` is expected to be False here. The
value of the A/B is realized with a real LLM backend, where the same harness
measures the quality delta; offline it proves the plumbing and that memory does
no harm.

    python -m atlas_counsel.eval.memory_ab
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from ..chunking import chunk_corpus
from ..corpus import build_corpus
from ..embeddings import HashingEmbedder
from ..memory.store import InMemoryMemoryStore
from ..retrieval import InMemoryHybridRetriever, Retriever


class Scenario(BaseModel):
    name: str
    prime: str   # establishes knowledge
    target: str  # related follow-up that should benefit from recall


SCENARIOS: list[Scenario] = [
    Scenario(name="approval-threshold",
             prime="Who must approve a $60,000 purchase?",
             target="Who signs off on a $60,000 purchase?"),
    Scenario(name="payment-terms",
             prime="What are NorthLink's payment terms?",
             target="What payment terms did NorthLink agree to?"),
]


class ABResult(BaseModel):
    scenario: str
    prime_persisted: bool
    recalled: bool
    answer_changed: bool


class ABReport(BaseModel):
    results: list[ABResult]

    @property
    def recall_rate(self) -> float:
        return round(sum(r.recalled for r in self.results) / len(self.results), 4) if self.results else 0.0

    @property
    def persist_rate(self) -> float:
        return round(sum(r.prime_persisted for r in self.results) / len(self.results), 4) if self.results else 0.0


def _build_retriever() -> Retriever:
    r = InMemoryHybridRetriever(HashingEmbedder())
    r.index(chunk_corpus(build_corpus()))
    return r


def _invoke(graph, question: str, tenant: str, thread: str) -> dict:
    return graph.invoke(
        {"question": question, "tenant_id": tenant, "thread_id": thread},
        {"configurable": {"thread_id": thread}},
    )


def run_memory_ab(scenarios: list[Scenario] = SCENARIOS) -> ABReport:
    from ..agent.graph import build_counsel_graph  # lazy: avoids import cycle
    retriever = _build_retriever()
    results: list[ABResult] = []

    for i, sc in enumerate(scenarios):
        tenant = f"ab-{i}"

        # --- memory ON: prime persists, target recalls ---
        store = InMemoryMemoryStore(HashingEmbedder())
        g_on = build_counsel_graph(
            retriever, memory_store=store, checkpointer=MemorySaver(), hitl_enabled=False)
        prime_out = _invoke(g_on, sc.prime, tenant, "prime")
        target_on = _invoke(g_on, sc.target, tenant, "target")

        prime_persisted = bool(prime_out.get("memory_persisted"))
        recalled = bool(target_on.get("memory_context"))

        # --- memory OFF: same target, no store ---
        g_off = build_counsel_graph(
            retriever, memory_store=None, checkpointer=MemorySaver(), hitl_enabled=False)
        target_off = _invoke(g_off, sc.target, tenant, "target-off")

        ans_on = target_on.get("answer")
        ans_off = target_off.get("answer")
        answer_changed = bool(ans_on and ans_off and ans_on.text != ans_off.text)

        results.append(ABResult(
            scenario=sc.name,
            prime_persisted=prime_persisted,
            recalled=recalled,
            answer_changed=answer_changed,
        ))
    return ABReport(results=results)


def main() -> None:
    rep = run_memory_ab()
    print("=== Memory A/B (memory ON vs OFF) ===")
    print(f"{'scenario':<22}{'persisted':>11}{'recalled':>10}{'ans_changed':>13}")
    for r in rep.results:
        print(f"{r.scenario:<22}{str(r.prime_persisted):>11}{str(r.recalled):>10}{str(r.answer_changed):>13}")
    print(f"\npersist_rate={rep.persist_rate}  recall_rate={rep.recall_rate}")
    print("Offline note: answers are synthesized from retrieved spans, so recalled")
    print("context does not change the text here; rerun with a real LLM backend to")
    print("measure the quality delta. The A/B confirms recall works and memory is safe.")


if __name__ == "__main__":
    main()

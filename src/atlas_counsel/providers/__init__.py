"""Provider factory.

`make_embedder` / `make_llm` / `make_judge` build the configured backend from
`Settings`. Defaults are the deterministic offline stubs, so with no environment
set the system behaves exactly as before — CI is unchanged. Real backends are
lazily imported only when selected, so importing this module (and constructing a
real provider) never pulls torch/boto3 or touches the network; the heavy work
happens on first embed/complete.
"""

from __future__ import annotations

from ..agent.llm import LLMProvider, TemplateLLM
from ..config import Settings
from ..embeddings import EmbeddingProvider, HashingEmbedder

__all__ = ["make_embedder", "make_llm", "make_judge"]


def make_embedder(settings: Settings | None = None) -> EmbeddingProvider:
    s = settings or Settings.from_env()
    name = (s.embedder or "hashing").lower()
    if name in ("hashing", "hashing-v1", ""):
        return HashingEmbedder()
    if name in ("bge-m3", "bge", "bgem3"):
        from .bge_m3 import BGEM3Embedder
        return BGEM3Embedder(model_name=s.bge_model, device=s.bge_device)
    if name in ("titan", "titan-v2"):
        from .titan import TitanEmbedder
        return TitanEmbedder(model_id=s.bedrock_embed_model, region=s.bedrock_region)
    raise ValueError(f"unknown ATLAS_EMBEDDER={s.embedder!r} (hashing|bge-m3|titan)")


def _make_llm_named(name: str, s: Settings) -> LLMProvider:
    name = (name or "template").lower()
    if name in ("template", ""):
        return TemplateLLM()
    if name == "ollama":
        from .ollama import OllamaLLM
        return OllamaLLM(model=s.ollama_model, host=s.ollama_host)
    if name == "bedrock":
        from .bedrock import BedrockLLM
        return BedrockLLM(model_id=s.bedrock_llm_model, region=s.bedrock_region)
    raise ValueError(f"unknown LLM backend {name!r} (template|ollama|bedrock)")


def make_llm(settings: Settings | None = None) -> LLMProvider:
    s = settings or Settings.from_env()
    return _make_llm_named(s.llm, s)


def make_judge(settings: Settings | None = None):
    s = settings or Settings.from_env()
    kind = (s.judge or "heuristic").lower()
    if kind in ("heuristic", ""):
        from ..eval.judge import HeuristicJudge
        return HeuristicJudge()
    if kind == "llm":
        backend = (s.judge_llm or s.llm or "template").lower()
        if backend == "template":
            raise ValueError(
                "ATLAS_JUDGE=llm requires a real LLM backend; set ATLAS_LLM or "
                "ATLAS_JUDGE_LLM to ollama|bedrock")
        llm = _make_llm_named(backend, s)
        from .llm_judge import LLMBackedJudge
        return LLMBackedJudge(llm.complete)  # type: ignore[attr-defined]
    raise ValueError(f"unknown ATLAS_JUDGE={s.judge!r} (heuristic|llm)")

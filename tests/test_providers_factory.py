"""Provider factory + settings tests.

Pins the contract that matters for safety: with no environment the factory yields
the deterministic stubs (so CI never accidentally needs a model or network), and
selecting a real backend constructs the right class lazily — without importing
torch/boto3 or touching the network at construction time.
"""

from __future__ import annotations

import pytest

from atlas_counsel.agent.llm import TemplateLLM
from atlas_counsel.config import Settings
from atlas_counsel.embeddings import HashingEmbedder
from atlas_counsel.eval.judge import HeuristicJudge
from atlas_counsel.providers import make_embedder, make_judge, make_llm
from atlas_counsel.providers.bedrock import BedrockLLM
from atlas_counsel.providers.bge_m3 import BGEM3Embedder
from atlas_counsel.providers.llm_judge import LLMBackedJudge
from atlas_counsel.providers.ollama import OllamaLLM
from atlas_counsel.providers.titan import TitanEmbedder


def test_defaults_are_offline_stubs():
    assert isinstance(make_embedder(Settings()), HashingEmbedder)
    assert isinstance(make_llm(Settings()), TemplateLLM)
    assert isinstance(make_judge(Settings()), HeuristicJudge)


def test_settings_from_env_reads_atlas_vars():
    s = Settings.from_env({"ATLAS_EMBEDDER": "bge-m3", "ATLAS_LLM": "ollama",
                           "ATLAS_OLLAMA_MODEL": "mistral"})
    assert s.embedder == "bge-m3" and s.llm == "ollama" and s.ollama_model == "mistral"


def test_settings_default_when_env_empty():
    s = Settings.from_env({})
    assert s.embedder == "hashing" and s.llm == "template" and s.judge == "heuristic"


@pytest.mark.parametrize("name,cls", [("bge-m3", BGEM3Embedder), ("titan", TitanEmbedder)])
def test_real_embedders_selected_without_loading(name, cls):
    e = make_embedder(Settings(embedder=name))
    assert isinstance(e, cls)
    # static props available without loading the model / hitting AWS
    assert e.dense_dim == 1024 and e.space_id


@pytest.mark.parametrize("name,cls", [("ollama", OllamaLLM), ("bedrock", BedrockLLM)])
def test_real_llms_selected_without_network(name, cls):
    assert isinstance(make_llm(Settings(llm=name)), cls)


def test_unknown_backends_raise():
    with pytest.raises(ValueError):
        make_embedder(Settings(embedder="nope"))
    with pytest.raises(ValueError):
        make_llm(Settings(llm="nope"))


def test_llm_judge_selected_and_guarded():
    assert isinstance(make_judge(Settings(judge="llm", judge_llm="ollama")), LLMBackedJudge)
    # an LLM judge over the template stub is meaningless — must error clearly
    with pytest.raises(ValueError):
        make_judge(Settings(judge="llm", llm="template"))

"""Real-backend tests via injected fakes — no network, no heavy deps.

Each backend's request-building and response-parsing is exercised with an
injected client/model: Ollama through httpx.MockTransport, Bedrock/Titan through
a fake boto3-style client, bge-m3 through a fake FlagModel. A final end-to-end
test drives the whole agent graph with a fake Ollama backend and asserts a
grounded, cited answer — proving the real-provider path works through the graph,
not just in isolation.
"""

from __future__ import annotations

import json

import httpx
import pytest

from atlas_counsel.providers.bedrock import BedrockLLM
from atlas_counsel.providers.bge_m3 import BGEM3Embedder
from atlas_counsel.providers.llm_judge import LLMBackedJudge
from atlas_counsel.providers.ollama import OllamaLLM
from atlas_counsel.providers.titan import TitanEmbedder


# -- Ollama ---------------------------------------------------------------
def test_ollama_complete_posts_chat_with_json_format():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        body = json.loads(req.content)
        seen["format"] = body.get("format")
        seen["model"] = body["model"]
        seen["roles"] = [m["role"] for m in body["messages"]]
        return httpx.Response(200, json={"message": {"content": '{"ok":true}'}})

    llm = OllamaLLM(model="llama3.1",
                    client=httpx.Client(transport=httpx.MockTransport(handler)))
    out = llm.complete("system text", "user text", want_json=True)
    assert out == '{"ok":true}'
    assert seen == {"path": "/api/chat", "format": "json", "model": "llama3.1",
                    "roles": ["system", "user"]}


# -- Bedrock --------------------------------------------------------------
class _FakeBedrockConverse:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def converse(self, **kw):
        self.calls.append(kw)
        return {"output": {"message": {"content": [
            {"text": '{"faithful":true,"unsupported_span_ids":[]}'}]}}}


def test_bedrock_complete_uses_converse():
    client = _FakeBedrockConverse()
    llm = BedrockLLM(model_id="anthropic.claude-3-5-sonnet-20240620-v1:0", client=client)
    out = llm.complete("sys", "user", want_json=True)
    assert "faithful" in out
    call = client.calls[0]
    assert call["modelId"].startswith("anthropic.")
    assert call["system"] == [{"text": "sys"}]
    assert call["messages"][0]["role"] == "user"


# -- Titan ----------------------------------------------------------------
class _FakeBody:
    def __init__(self, data: dict) -> None:
        self._data = data

    def read(self) -> bytes:
        return json.dumps(self._data).encode()


class _FakeTitanClient:
    def __init__(self, dim: int) -> None:
        self.dim = dim

    def invoke_model(self, modelId: str, body: str):
        assert json.loads(body)["normalize"] is True
        return {"body": _FakeBody({"embedding": [0.1] * self.dim})}


def test_titan_embed_pairs_dense_with_lexical_sparse():
    emb = TitanEmbedder(client=_FakeTitanClient(8), dim=8)
    out = emb.embed(["net-30 payment $25,000", "liability cap"])
    assert emb.space_id == "titan-v2" and emb.dense_dim == 8
    assert len(out) == 2 and len(out[0].dense) == 8
    # dense-only model still yields a sparse channel via lexical_sparse
    assert out[0].sparse.indices and out[0].sparse.values


# -- bge-m3 ---------------------------------------------------------------
class _FakeFlagModel:
    def encode(self, texts, **kw):
        assert kw["return_dense"] and kw["return_sparse"]
        return {"dense_vecs": [[0.2] * 4 for _ in texts],
                "lexical_weights": [{"205": 0.3, "101": 0.7} for _ in texts]}


def test_bge_m3_maps_dense_and_learned_sparse():
    emb = BGEM3Embedder(model=_FakeFlagModel(), dim=4)
    out = emb.embed(["a", "b"])
    assert emb.space_id == "bge-m3"
    assert len(out[0].dense) == 4
    # learned sparse weights -> sorted int indices
    assert out[0].sparse.indices == [101, 205] and out[0].sparse.values == [0.7, 0.3]


# -- LLM judge ------------------------------------------------------------
def test_llm_judge_parses_and_clamps():
    judge = LLMBackedJudge(lambda s, u: '{"faithfulness":0.9,"answer_relevancy":1.4}')
    res = judge.judge("q", "a", ["ctx"])
    assert res.faithfulness == 0.9 and res.answer_relevancy == 1.0  # clamped to [0,1]


def test_llm_judge_malformed_defaults_to_zero():
    res = LLMBackedJudge(lambda s, u: "nonsense").judge("q", "a", ["ctx"])
    assert res.faithfulness == 0.0 and res.answer_relevancy == 0.0


# -- end-to-end through the agent graph -----------------------------------
def test_real_llm_backend_drives_agent_to_cited_answer():
    import re

    from langgraph.checkpoint.memory import MemorySaver

    from atlas_counsel.agent.graph import build_counsel_graph
    from atlas_counsel.chunking import chunk_corpus
    from atlas_counsel.corpus import build_corpus
    from atlas_counsel.embeddings import HashingEmbedder
    from atlas_counsel.retrieval import InMemoryHybridRetriever

    retriever = InMemoryHybridRetriever(HashingEmbedder())
    retriever.index(chunk_corpus(build_corpus()))

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        system, user = (m["content"] for m in body["messages"][:2])
        if system.startswith("You are ATLAS Counsel"):  # synthesize from first span
            m = re.search(r"\[span_id=([^\]]+)\]\s*([^\n]+)", user)
            sid, text = (m.group(1), m.group(2).strip()) if m else ("X#S0", "x")
            content = json.dumps({"claims": [{"text": text, "span_id": sid}]})
        elif system.startswith("You verify"):
            content = json.dumps({"faithful": True, "unsupported_span_ids": []})
        else:  # gap analysis: nothing missing
            content = '{"follow_up_queries":[]}'
        return httpx.Response(200, json={"message": {"content": content}})

    llm = OllamaLLM(client=httpx.Client(transport=httpx.MockTransport(handler)))
    graph = build_counsel_graph(retriever, llm=llm, checkpointer=MemorySaver(),
                                hitl_enabled=False)
    out = graph.invoke(
        {"question": "What are NorthLink's payment terms?",
         "tenant_id": "t", "thread_id": "th"},
        {"configurable": {"thread_id": "th"}})
    answer = out["answer"]
    assert not answer.refused
    assert answer.citations  # grounded, with real span-id citations

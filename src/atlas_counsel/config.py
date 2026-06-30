"""Backend selection settings.

A small, dependency-free settings object read from the environment. It decides
which provider implementations the composition root wires in. The defaults are
the deterministic offline stubs, so nothing changes for CI or anyone who sets no
environment — real backends are strictly opt-in (ADR-0005, ADR-0019).

    ATLAS_EMBEDDER   hashing (default) | bge-m3 | titan
    ATLAS_LLM        template (default) | ollama | bedrock
    ATLAS_JUDGE      heuristic (default) | llm
    ATLAS_JUDGE_LLM  (optional) ollama | bedrock  — backend for the LLM judge,
                     defaults to ATLAS_LLM

    # Ollama (local dev)
    ATLAS_OLLAMA_HOST    default http://localhost:11434
    ATLAS_OLLAMA_MODEL   default llama3.1

    # Bedrock (prod)
    ATLAS_BEDROCK_REGION       default AWS_REGION or us-east-1
    ATLAS_BEDROCK_LLM_MODEL    default anthropic.claude-3-5-sonnet-20240620-v1:0
    ATLAS_BEDROCK_EMBED_MODEL  default amazon.titan-embed-text-v2:0

    # bge-m3 (local embeddings)
    ATLAS_BGE_MODEL    default BAAI/bge-m3
    ATLAS_BGE_DEVICE   default "" (auto)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Settings:
    embedder: str = "hashing"
    llm: str = "template"
    judge: str = "heuristic"
    judge_llm: str = ""

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    bedrock_region: str = "us-east-1"
    bedrock_llm_model: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"

    bge_model: str = "BAAI/bge-m3"
    bge_device: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        e = env if env is not None else os.environ
        g = e.get
        return cls(
            embedder=g("ATLAS_EMBEDDER", "hashing"),
            llm=g("ATLAS_LLM", "template"),
            judge=g("ATLAS_JUDGE", "heuristic"),
            judge_llm=g("ATLAS_JUDGE_LLM", ""),
            ollama_host=g("ATLAS_OLLAMA_HOST", "http://localhost:11434"),
            ollama_model=g("ATLAS_OLLAMA_MODEL", "llama3.1"),
            bedrock_region=g("ATLAS_BEDROCK_REGION", g("AWS_REGION", "us-east-1")),
            bedrock_llm_model=g(
                "ATLAS_BEDROCK_LLM_MODEL", "anthropic.claude-3-5-sonnet-20240620-v1:0"),
            bedrock_embed_model=g(
                "ATLAS_BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0"),
            bge_model=g("ATLAS_BGE_MODEL", "BAAI/bge-m3"),
            bge_device=g("ATLAS_BGE_DEVICE", ""),
        )

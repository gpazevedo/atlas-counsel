# ATLAS Counsel

**Citation-grounded agentic RAG over a synthetic procurement corpus.**

A LangGraph agent that answers procurement-policy and contract questions, grounds
every claim in a retrievable source span, refuses when the corpus doesn't cover the
question, and pauses for a human when it isn't sure.

The project is built to be *measured*: it runs offline and reproducibly in CI, then
swaps to real models and a real vector store in production via config, not code
changes. This README grows alongside the implementation, one pull request at a time.

## Quickstart

```bash
uv sync --extra dev
uv run pytest
```

## License

GNU AGPL v3 — see [LICENSE](LICENSE).

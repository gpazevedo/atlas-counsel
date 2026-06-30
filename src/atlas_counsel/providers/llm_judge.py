"""LLM-backed judge.

Faithfulness and answer-relevancy are the metrics that genuinely need semantic
judgement; the heuristic judge is an honest lexical proxy. This judge asks a real
LLM to score both in [0, 1]. It takes a `complete(system, user) -> str` callable
(supplied by the configured `StructuredLLMProvider`), so it is decoupled from any
specific backend and testable with a fake completion.

This is the judge the meta-eval bias work (ADR-0013 / meta_eval) actually needs:
scoring a heuristic against a heuristic measures nothing.
"""

from __future__ import annotations

from typing import Callable

from ..eval.judge import JudgeResult

_JUDGE_SYS = (
    "You are an evaluation judge. Given a question, an answer, and the context "
    "passages the answer should be grounded in, score two values in [0, 1]: "
    "faithfulness (are the answer's claims supported by the context?) and "
    "answer_relevancy (does the answer address the question?). Output a single "
    'JSON object: {"faithfulness": <0..1>, "answer_relevancy": <0..1>}.'
)


def _clamp(v: object) -> float:
    try:
        return max(0.0, min(1.0, float(v)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


class LLMBackedJudge:
    def __init__(self, complete: Callable[[str, str], str]) -> None:
        self._complete = complete

    def judge(self, question: str, answer: str, context: list[str]) -> JudgeResult:
        from ._json import extract_json
        ctx = "\n".join(f"- {c}" for c in context) if context else "(no context)"
        user = f"QUESTION:\n{question}\n\nANSWER:\n{answer}\n\nCONTEXT:\n{ctx}"
        data = extract_json(self._complete(_JUDGE_SYS, user)) or {}
        if not isinstance(data, dict):
            data = {}
        return JudgeResult(
            faithfulness=round(_clamp(data.get("faithfulness")), 4),
            answer_relevancy=round(_clamp(data.get("answer_relevancy")), 4),
        )

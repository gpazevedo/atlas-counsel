"""Best-effort JSON extraction from an LLM completion.

Real models wrap JSON in prose or ```json fences even when asked not to. This
pulls the first balanced object/array out and parses it, returning None on
failure so callers can fall back to a safe default rather than crashing the
graph.
"""

from __future__ import annotations

import json
from typing import Any


def extract_json(text: str | None) -> Any | None:
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s[:4].lower() == "json":
            s = s[4:]
        s = s.strip()
    # Try a direct parse first (the well-behaved case).
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Otherwise, slice from the first opening bracket to the last closing one.
    candidates = [i for i in (s.find("{"), s.find("[")) if i != -1]
    if not candidates:
        return None
    start = min(candidates)
    end = max(s.rfind("}"), s.rfind("]"))
    if end <= start:
        return None
    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return None

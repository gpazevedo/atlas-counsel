"""Extra service tests beyond test_service.py.

The main suite covers REST ask/resume/steer, the interrupt-across-two-calls
cycle, WebSocket streaming, MCP/HTTP agreement, validation, the exception
boundary, and the FallbackRetriever. These add the bits it leaves implicit:
CounselService.astream exercised directly, deep_health's shape, and the
ask->resume thread continuity through the checkpointer.

An in-memory checkpointer is injected so these don't create an on-disk
checkpoints.db.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed (try: uv sync --extra service)")

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

from atlas_counsel.service import AskStatus, CounselService  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")


def _svc() -> CounselService:
    return CounselService(checkpointer=MemorySaver())


def _drain(agen):
    """Collect an async generator's frames from sync test code."""
    async def run():
        return [f async for f in agen]
    return asyncio.run(run())


def test_astream_streams_nodes_then_result_frame():
    frames = _drain(_svc().astream("What are NorthLink's payment terms?"))
    node_frames = [f for f in frames if f["event"] == "node"]
    assert node_frames and node_frames[0]["node"] == "plan"
    assert frames[-1]["event"] == "result"
    assert frames[-1]["status"] == "answered"
    assert any(c.startswith("CON-002") for c in frames[-1]["citations"])


def test_astream_unanswerable_ends_in_needs_input():
    frames = _drain(_svc().astream("What is our policy on accepting gifts from suppliers?"))
    assert frames[-1]["event"] == "needs_input"
    assert frames[-1]["status"] == "needs_input"
    assert frames[-1]["gate_reason"] == "insufficient_grounding"


def test_deep_health_reports_component_status():
    health = _svc().deep_health()
    assert health["status"] == "ok"
    assert health["ready"] is True
    assert health["graph"] == "ok"
    assert health["checkpointer"] == "ok"


def test_ask_and_resume_share_thread_via_checkpointer():
    svc = _svc()
    first = svc.ask("What is our policy on accepting gifts from suppliers?")
    assert first.status == AskStatus.NEEDS_INPUT
    # The thread_id from ask is the resume token carried by the checkpointer.
    resumed = svc.resume(first.thread_id, "decline")
    assert resumed.status == AskStatus.REFUSED
    assert resumed.thread_id == first.thread_id

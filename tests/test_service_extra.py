"""Extra service tests beyond test_service.py.

The main suite covers REST ask/resume/steer, the interrupt-across-two-calls
cycle, WebSocket streaming, and MCP/HTTP agreement. These add the bits it
leaves implicit: explicit thread_id passthrough, and CounselService.astream
exercised directly (the WS test covers it only through the socket).
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed (try: uv sync --extra service)")

from fastapi.testclient import TestClient  # noqa: E402

from atlas_counsel.service import CounselService, create_app  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")


def test_ask_uses_caller_supplied_thread_id():
    client = TestClient(create_app())
    r = client.post("/ask", json={
        "question": "What are NorthLink's payment terms?",
        "thread_id": "fixed-thread-123",
    }).json()
    assert r["thread_id"] == "fixed-thread-123"
    assert r["status"] == "answered"


def _drain(agen):
    """Collect an async generator's frames from sync test code."""
    async def run():
        return [f async for f in agen]
    return asyncio.run(run())


def test_astream_streams_nodes_then_result_frame():
    svc = CounselService()
    frames = _drain(svc.astream("What are NorthLink's payment terms?"))
    node_frames = [f for f in frames if f["event"] == "node"]
    assert node_frames and node_frames[0]["node"] == "plan"
    assert frames[-1]["event"] == "result"
    assert frames[-1]["status"] == "answered"
    assert any(c.startswith("CON-002") for c in frames[-1]["citations"])


def test_astream_unanswerable_ends_in_needs_input():
    svc = CounselService()
    frames = _drain(svc.astream("What is our policy on accepting gifts from suppliers?"))
    assert frames[-1]["event"] == "needs_input"
    assert frames[-1]["status"] == "needs_input"
    assert frames[-1]["gate_reason"] == "insufficient_grounding"

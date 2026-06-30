"""Extra service tests beyond test_service.py.

The main suite covers REST ask/resume/steer, the interrupt-across-two-calls
cycle, WebSocket streaming, MCP/HTTP agreement, validation, the exception
boundary, the FallbackRetriever, and tenant isolation. These add the bits it
leaves implicit: CounselService.astream exercised directly, deep_health's
shape, and ask->resume thread continuity within a tenant.

CHECKPOINT_DIR is redirected to a tmp dir so per-tenant SQLite checkpoints
don't land in ./data.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed (try: uv sync --extra service)")

from atlas_counsel.service import AskStatus, CounselService  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKPOINT_DIR", str(tmp_path))
    return CounselService()


def _drain(agen):
    """Collect an async generator's frames from sync test code."""
    async def run():
        return [f async for f in agen]
    return asyncio.run(run())


def test_astream_streams_nodes_then_result_frame(svc):
    frames = _drain(svc.astream("What are NorthLink's payment terms?"))
    node_frames = [f for f in frames if f["event"] == "node"]
    assert node_frames and node_frames[0]["node"] == "plan"
    assert frames[-1]["event"] == "result"
    assert frames[-1]["status"] == "answered"
    assert any(c.startswith("CON-002") for c in frames[-1]["citations"])


def test_astream_unanswerable_ends_in_needs_input(svc):
    frames = _drain(svc.astream("What is our policy on accepting gifts from suppliers?"))
    assert frames[-1]["event"] == "needs_input"
    assert frames[-1]["status"] == "needs_input"
    assert frames[-1]["gate_reason"] == "insufficient_grounding"


def test_deep_health_reports_component_status(svc):
    # Touch a tenant so the registry has something to probe.
    svc.ask("What are NorthLink's payment terms?")
    health = svc.deep_health()
    assert health["status"] == "ok"
    assert health["ready"] is True
    assert health["graph"] == "ok"
    assert health["checkpointer"] == "ok"
    assert health["tenants"] >= 1


def test_astream_scopes_thread_to_tenant(svc):
    """A thread streamed under one tenant isn't visible to another."""
    frames = _drain(svc.astream("What is our policy on accepting gifts from suppliers?",
                                tenant_id="acme"))
    tid = frames[-1]["thread_id"]
    # Resuming that thread under a different tenant errors (separate DB).
    cross = svc.resume(tid, "decline", tenant_id="globex")
    assert cross.status == AskStatus.ERROR
    # Same tenant resumes fine.
    same = svc.resume(tid, "decline", tenant_id="acme")
    assert same.status == AskStatus.REFUSED

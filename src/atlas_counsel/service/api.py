"""FastAPI runtime around the CounselService.

Endpoints (all thin wrappers over the service — no logic here):

  POST /ask            {tenant_id, question}             -> AskResult
  POST /resume         {tenant_id, thread_id, action,..} -> AskResult
  GET  /health                                          -> {status, ...}
  WS   /ws/ask         stream node-by-node progress, then the result

The WebSocket demonstrates the "real-time / streaming AI experiences" the JD
asks for: it streams the graph's state updates as each node completes, then a
terminal frame with the final result (or a needs_input frame at the gate).
"""

from __future__ import annotations

import hmac
import logging
import os

import jwt
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..telemetry import instrument_fastapi, shutdown as otel_shutdown
from .core import AskResult, AskStatus, CounselService
from .tenants import DEFAULT_TENANT, current_tenant

logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    tenant_id: str = Field(default=DEFAULT_TENANT, min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=2000)


class ResumeRequest(BaseModel):
    tenant_id: str = Field(default=DEFAULT_TENANT, min_length=1, max_length=64)
    thread_id: str = Field(..., min_length=1)
    action: str = Field(..., pattern=r"^(steer|decline)$")
    guidance: str | None = None


def create_app(service: CounselService | None = None) -> FastAPI:
    service = service or CounselService()
    app = FastAPI(title="ATLAS Counsel", version="0.1.0")
    instrument_fastapi(app)
    _mount_mcp(app, service)

    mcp_api_key = os.environ.get("MCP_API_KEY", "")
    mcp_jwt_secret = os.environ.get("MCP_JWT_SECRET", "")
    mcp_jwt_audience = os.environ.get("MCP_JWT_AUDIENCE", "")
    require_auth = os.environ.get("MCP_REQUIRE_AUTH", "").lower() in {"1", "true", "yes"}

    if require_auth and not mcp_api_key and not mcp_jwt_secret:
        raise RuntimeError(
            "MCP_REQUIRE_AUTH is set but neither MCP_API_KEY nor MCP_JWT_SECRET is configured"
        )
    if not mcp_api_key and not mcp_jwt_secret:
        logger.warning(
            "MCP_API_KEY and MCP_JWT_SECRET are not set - the /mcp endpoint is "
            "UNAUTHENTICATED. Set one of them to require authentication."
        )

    @app.middleware("http")
    async def _mcp_auth(request: Request, call_next):
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        token = current_tenant.set(DEFAULT_TENANT)

        # JWT auth: extract tenant_id from the token
        if mcp_jwt_secret:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                try:
                    decode_opts: dict = {}
                    if mcp_jwt_audience:
                        decode_opts["audience"] = mcp_jwt_audience
                    else:
                        decode_opts["options"] = {"verify_aud": False}
                    claims = jwt.decode(
                        auth_header[7:], mcp_jwt_secret, algorithms=["HS256"],
                        **decode_opts,
                    )
                    tenant = claims.get("tenant_id", DEFAULT_TENANT)
                    current_tenant.set(tenant)
                    return await call_next(request)
                except jwt.InvalidTokenError:
                    return JSONResponse(
                        status_code=401, content={"detail": "invalid or expired token"}
                    )

        # API key auth: single-tenant fallback
        if mcp_api_key:
            presented = request.headers.get("x-api-key", "")
            if hmac.compare_digest(presented, mcp_api_key):
                return await call_next(request)
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})

        # No auth configured — dev mode
        return await call_next(request)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        otel_shutdown()

    @app.get("/health")
    def health() -> dict:
        return service.deep_health()

    @app.post("/ask")
    def ask(req: AskRequest) -> AskResult:
        return service.ask(req.question, tenant_id=req.tenant_id)

    @app.post("/resume")
    def resume(req: ResumeRequest) -> AskResult:
        return service.resume(
            req.thread_id, req.action, guidance=req.guidance,
            tenant_id=req.tenant_id,
        )

    @app.websocket("/ws/ask")
    async def ws_ask(ws: WebSocket) -> None:
        await ws.accept()
        try:
            data = await ws.receive_json()
            question = data["question"]
            thread_id = data.get("thread_id")
            tenant_id = data.get("tenant_id", DEFAULT_TENANT)
            async for frame in service.astream(question, thread_id=thread_id,
                                               tenant_id=tenant_id):
                await ws.send_json(frame)
        except WebSocketDisconnect:
            return

    @app.exception_handler(Exception)
    async def _exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=AskResult(
                status=AskStatus.ERROR,
                thread_id="",
                answer=str(exc),
            ).model_dump(),
        )

    return app


def _mount_mcp(app: FastAPI, service: CounselService) -> None:
    """Mount the Streamable HTTP MCP transport at /mcp so the MCP server and
    REST API share the same port and TenantRegistry."""
    from .mcp_server import build_mcp_server
    mcp = build_mcp_server(service)
    app.mount("/mcp", mcp.streamable_http_app())


# Convenience for `uvicorn atlas_counsel.service.api:app`
app = create_app()

import os
import time
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("jwt", reason="pyjwt not installed (try: uv sync --extra service)")
pytest.importorskip("httpx", reason="httpx not installed (try: uv sync --extra service)")

import jwt
from httpx import ASGITransport, AsyncClient


@contextmanager
def _env(**kwargs):
    """Set env vars for the duration of the context, restoring originals after."""
    originals = {}
    for k, v in kwargs.items():
        originals[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        yield
    finally:
        for k, orig in originals.items():
            if orig is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = orig


def _make_app(*, mcp_api_key="", mcp_jwt_secret="", mcp_jwt_audience="",
              require_auth=""):
    with _env(
        MCP_API_KEY=mcp_api_key,
        MCP_JWT_SECRET=mcp_jwt_secret,
        MCP_JWT_AUDIENCE=mcp_jwt_audience,
        MCP_REQUIRE_AUTH=require_auth,
    ):
        with patch("atlas_counsel.service.api._mount_mcp"):
            with patch("atlas_counsel.service.api.instrument_fastapi"):
                from atlas_counsel.service.api import create_app
                return create_app(MagicMock())


def _jwt(secret, tenant_id="acme", audience="atlas-counsel"):
    return jwt.encode(
        {"tenant_id": tenant_id, "aud": audience, "iat": int(time.time())},
        secret, algorithm="HS256",
    )


# ── Dev mode (no auth configured) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_dev_mode_passes_through():
    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/mcp/tools")
        assert r.status_code != 401


@pytest.mark.asyncio
async def test_non_mcp_paths_never_challenged():
    app = _make_app(mcp_api_key="secret")
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/does-not-exist")
        assert r.status_code != 401


# ── API key auth ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_api_key_passes():
    app = _make_app(mcp_api_key="secret")
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/mcp/tools",
                             headers={"x-api-key": "secret"})
        assert r.status_code != 401


@pytest.mark.asyncio
async def test_wrong_api_key_returns_401():
    app = _make_app(mcp_api_key="secret")
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/mcp/tools", headers={"x-api-key": "wrong"})
        assert r.status_code == 401
        assert r.json() == {"detail": "unauthorized"}


@pytest.mark.asyncio
async def test_missing_api_key_returns_401():
    app = _make_app(mcp_api_key="secret")
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/mcp/tools")
        assert r.status_code == 401


# ── JWT auth ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_jwt_passes():
    app = _make_app(mcp_jwt_secret="jwt-secret", mcp_jwt_audience="atlas-counsel")
    token = _jwt("jwt-secret")
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/mcp/tools",
                             headers={"Authorization": f"Bearer {token}"})
        assert r.status_code != 401


@pytest.mark.asyncio
async def test_jwt_wrong_secret_returns_401():
    app = _make_app(mcp_jwt_secret="jwt-secret")
    token = _jwt("wrong-secret")
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/mcp/tools",
                             headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
        assert r.json()["detail"] == "invalid or expired token"


@pytest.mark.asyncio
async def test_jwt_wrong_audience_returns_401():
    app = _make_app(mcp_jwt_secret="jwt-secret", mcp_jwt_audience="atlas-counsel")
    token = _jwt("jwt-secret", audience="wrong-audience")
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/mcp/tools",
                             headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_expired_jwt_returns_401():
    app = _make_app(mcp_jwt_secret="jwt-secret")
    token = jwt.encode(
        {"tenant_id": "acme", "iat": int(time.time()) - 7200,
         "exp": int(time.time()) - 3600},
        "jwt-secret", algorithm="HS256",
    )
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/mcp/tools",
                             headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_jwt_malformed_returns_401():
    app = _make_app(mcp_jwt_secret="jwt-secret")
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/mcp/tools",
                             headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401


# ── Auth precedence ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jwt_takes_precedence_over_api_key():
    """When both are configured, a valid JWT passes without x-api-key."""
    app = _make_app(mcp_api_key="secret", mcp_jwt_secret="jwt-secret")
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        token = _jwt("jwt-secret")
        r = await client.get("/mcp/tools",
                             headers={"Authorization": f"Bearer {token}"})
        assert r.status_code != 401


@pytest.mark.asyncio
async def test_bad_jwt_fails_even_with_good_api_key():
    """A bad JWT returns 401 even when x-api-key is valid."""
    app = _make_app(mcp_api_key="secret", mcp_jwt_secret="jwt-secret")
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/mcp/tools",
                             headers={"Authorization": "Bearer bad",
                                      "x-api-key": "secret"})
        assert r.status_code == 401


# ── Boot crash when auth is required but unconfigured ──────────────────────

def test_require_auth_crashes_without_any_secret():
    with pytest.raises(RuntimeError, match="MCP_REQUIRE_AUTH"):
        _make_app(require_auth="true")


def test_require_auth_passes_with_api_key():
    _make_app(mcp_api_key="secret", require_auth="true")


def test_require_auth_passes_with_jwt_secret():
    _make_app(mcp_jwt_secret="jwt-secret", require_auth="true")

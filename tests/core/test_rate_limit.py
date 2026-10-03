from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport

from app.core.auth import TokenUser
from app.core.rate_limit import _enforce, client_ip, ip_rate_limit, user_rate_limit
from app.main import app


def _fake_client(count=1, ttl=60, sink=None):
    """Minimal Redis stand-in. `sink` (optional dict) records the INCR key."""
    class Pipe:
        def incr(self, key):
            if sink is not None:
                sink["key"] = key
            return self

        def expire(self, *args, **kwargs):
            return self

        async def execute(self):
            return [count, True]

    class Client:
        def pipeline(self):
            return Pipe()

        async def ttl(self, key):
            return ttl

    return Client()


# --- _enforce ---


@pytest.mark.asyncio
async def test_enforce_under_limit_does_not_raise():
    with patch("app.core.rate_limit._get_client", return_value=_fake_client(count=1)):
        await _enforce("k", limit=5, window=60)  # must not raise


@pytest.mark.asyncio
async def test_enforce_over_limit_raises_429_with_retry_after():
    with patch("app.core.rate_limit._get_client", return_value=_fake_client(count=6, ttl=42)):
        with pytest.raises(HTTPException) as exc:
            await _enforce("k", limit=5, window=60)
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "42"


# --- client_ip ---


def test_client_ip_prefers_forwarded_header():
    class Req:
        headers = {"x-forwarded-for": "1.2.3.4, 10.0.0.1"}
        client = None

    assert client_ip(Req()) == "1.2.3.4"


def test_client_ip_falls_back_to_socket_peer():
    class Peer:
        host = "9.9.9.9"

    class Req:
        headers = {}
        client = Peer()

    assert client_ip(Req()) == "9.9.9.9"


# --- key construction ---


@pytest.mark.asyncio
async def test_ip_rate_limit_keys_by_ip():
    class Peer:
        host = "1.1.1.1"

    class Req:
        headers = {}
        client = Peer()

    sink = {}
    with patch("app.core.rate_limit._get_client", return_value=_fake_client(count=1, sink=sink)):
        await ip_rate_limit(5, "login")(Req())

    assert sink["key"] == "ratelimit:login:ip:1.1.1.1"


@pytest.mark.asyncio
async def test_user_rate_limit_keys_by_user_sub():
    sink = {}
    with patch("app.core.rate_limit._get_client", return_value=_fake_client(count=1, sink=sink)):
        await user_rate_limit(5, "generate")(TokenUser(sub="42"))

    assert sink["key"] == "ratelimit:generate:user:42"


# --- endpoint wiring ---


@pytest.mark.asyncio
async def test_login_rate_limited_returns_429():
    with patch("app.core.rate_limit._get_client", return_value=_fake_client(count=11)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/login", json={
                "username": "alice", "password": "wrong"
            })
    assert response.status_code == 429

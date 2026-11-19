"""Тесты HTTP-слоя: повторы, 401, rate limit и сетевые ошибки."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from stalzone_api import AsyncClient, Client, TransportError
from stalzone_api._http import RateLimiter
from stalzone_api.auth import Credentials


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr("stalzone_api._http.time.sleep", lambda _seconds: None)


def test_retry_on_server_error(router, http_client, no_sleep):
    router.add("/regions", {"title": "boom", "status": 500, "details": {}}, status=500)
    router.add("/regions", {"title": "boom", "status": 500, "details": {}}, status=500)
    router.add("/regions", [{"id": "EU", "name": "EUROPE"}])

    client = Client(app_id="1", app_secret="x", client=http_client, retries=2)
    try:
        assert client.regions()[0].id == "EU"
        assert len(router.requests) == 3
    finally:
        client.close()


def test_retry_after_header(router, http_client, monkeypatch):
    delays: list[float] = []
    monkeypatch.setattr("stalzone_api._http.time.sleep", delays.append)
    router.add(
        "/regions",
        {"title": "slow down", "status": 429, "details": {}},
        status=429,
        headers={"Retry-After": "0.25"},
    )
    router.add("/regions", [{"id": "EU", "name": "EUROPE"}])

    client = Client(app_id="1", app_secret="x", client=http_client, retries=1)
    try:
        client.regions()
    finally:
        client.close()

    assert delays == [0.25]


def test_retry_exhausted_raises_server_error(router, http_client, no_sleep):
    for _ in range(2):
        router.add("/regions", {"title": "boom", "status": 503, "details": {}}, status=503)

    client = Client(app_id="1", app_secret="x", client=http_client, retries=1)
    try:
        with pytest.raises(Exception) as exc_info:
            client.regions()
        assert exc_info.value.status == 503
        assert len(router.requests) == 2
    finally:
        client.close()


class RefreshingCredentials(Credentials):
    def __init__(self) -> None:
        self.token = "old"
        self.refresh_calls = 0

    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def refresh(self) -> bool:
        self.refresh_calls += 1
        self.token = "new"
        return True


def test_401_refreshes_token_once(router, http_client):
    router.add("/regions", {"title": "Unauthorized", "status": 401, "details": {}}, status=401)
    router.add("/regions", [{"id": "EU", "name": "EUROPE"}])
    credentials = RefreshingCredentials()

    client = Client(credentials=credentials, client=http_client, retries=0)
    try:
        assert client.regions()[0].id == "EU"
    finally:
        client.close()

    assert credentials.refresh_calls == 1
    assert router.requests[0].headers["Authorization"] == "Bearer old"
    assert router.requests[1].headers["Authorization"] == "Bearer new"


def test_transport_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    client = Client(app_id="1", app_secret="x", region="EU", client=http, retries=0)
    try:
        with pytest.raises(TransportError, match="failed"):
            client.regions()
    finally:
        client.close()
        http.close()


def test_invalid_json_response(router, http_client):
    router.add("/regions", response=httpx.Response(200, content=b"<html>oops</html>"))

    client = Client(app_id="1", app_secret="x", client=http_client, retries=0)
    try:
        with pytest.raises(Exception, match="not valid JSON"):
            client.regions()
    finally:
        client.close()


def test_rate_limiter_interval():
    limiter = RateLimiter(4, per=1.0)

    assert limiter.interval == 0.25
    with pytest.raises(ValueError):
        RateLimiter(0)


@pytest.mark.asyncio
async def test_async_retry(router, async_http_client, monkeypatch):
    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("stalzone_api._http.asyncio.sleep", fake_sleep)
    router.add("/regions", {"title": "boom", "status": 500, "details": {}}, status=500)
    router.add("/regions", [{"id": "EU", "name": "EUROPE"}])

    client = AsyncClient(app_id="1", app_secret="x", client=async_http_client, retries=1)
    try:
        regions = await client.regions()
    finally:
        await client.close()

    assert regions[0].id == "EU"
    assert len(router.requests) == 2

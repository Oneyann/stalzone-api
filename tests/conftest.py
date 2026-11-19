"""Общие приспособления для тестов: мок-транспорт, клиенты и тестовая база."""

from __future__ import annotations

from typing import Any, Callable

import httpx
import pytest

from stalzone_api import AsyncClient, Client, PROD_URL

Handler = Callable[[httpx.Request], httpx.Response]


class Router:
    """Маршрутизатор запросов для ``httpx.MockTransport``.

    Позволяет задать один ответ или очередь ответов для конкретного пути,
    а также сохраняет все входящие запросы для проверок.
    """

    def __init__(self) -> None:
        self._routes: dict[str, list[httpx.Response]] = {}
        self.requests: list[httpx.Request] = []

    def add(
        self,
        path: str,
        payload: Any = None,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        response: httpx.Response | None = None,
        times: int = 1,
    ) -> None:
        if response is None:
            response = httpx.Response(
                status,
                json=payload,
                headers=headers,
            )
        for _ in range(times):
            self._routes.setdefault(path, []).append(response)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        queue = self._routes.get(request.url.path)
        if not queue:
            return httpx.Response(
                404,
                json={"title": "Not Found", "status": 404, "details": {}},
            )
        return queue.pop(0)

    @property
    def last_request(self) -> httpx.Request:
        return self.requests[-1]


def make_transport(handler: Handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.fixture
def router() -> Router:
    return Router()


@pytest.fixture
def http_client(router: Router):
    client = httpx.Client(transport=make_transport(router), base_url=PROD_URL)
    yield client
    client.close()


@pytest.fixture
def client(router: Router, http_client: httpx.Client):
    instance = Client(
        app_id="123",
        app_secret="secret",
        region="EU",
        client=http_client,
        retries=0,
    )
    yield instance
    instance.close()


@pytest.fixture
async def async_http_client(router: Router):
    client = httpx.AsyncClient(transport=make_transport(router), base_url=PROD_URL)
    yield client
    await client.aclose()


@pytest.fixture
async def async_client(router: Router, async_http_client: httpx.AsyncClient):
    instance = AsyncClient(
        app_id="123",
        app_secret="secret",
        region="EU",
        client=async_http_client,
        retries=0,
    )
    yield instance
    await instance.close()

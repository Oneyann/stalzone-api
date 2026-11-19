"""Tests for the deliberately simple AppClient facade."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from stalzone_api import (
    AppClient,
    AuthError,
    SyncAppClient,
)

REGIONS = [{"id": "RU", "name": "RUSSIA"}, {"id": "EU", "name": "EUROPE"}]
LOTS = {
    "total": 2,
    "lots": [
        {
            "itemId": "zyv9",
            "amount": 2,
            "startPrice": 100,
            "currentPrice": 150,
            "buyoutPrice": 500,
            "endTime": "2026-11-19T12:00:00Z",
        }
    ],
}
HISTORY = {
    "total": 2,
    "prices": [
        {"amount": 1, "price": 100, "time": "2026-11-18T12:00:00Z"},
        {"amount": 1, "price": 200, "time": "2026-11-19T12:00:00Z"},
    ],
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: Any) -> None:
    for name in (
        "STALZONE_APP_ID",
        "STALZONE_APP_SECRET",
        "STALZONE_ACCESS_TOKEN",
        "CLIENT_ID",
        "CLIENT_SECRET",
        "APP_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def test_no_credentials_falls_back_to_demo() -> None:
    client = AppClient()
    try:
        assert client.demo is True
        assert client.mode == "demo"
        assert client.region == "RU"
        assert repr(client) == "AppClient(mode='demo', region='RU')"
    finally:
        asyncio.run(client.close())


def test_explicit_demo_and_sync_facade() -> None:
    client = SyncAppClient.demo(region="eu")
    try:
        assert client.demo is True
        assert client.region == "EU"
        assert repr(client) == "SyncAppClient(mode='demo', region='EU')"
    finally:
        client.close()


def test_environment_credentials(monkeypatch: Any) -> None:
    monkeypatch.setenv("CLIENT_ID", "42")
    monkeypatch.setenv("CLIENT_SECRET", "secret")
    client = SyncAppClient()
    try:
        assert client.mode == "secret"
        assert client.demo is False
    finally:
        client.close()

    monkeypatch.setenv("APP_TOKEN", "ready-token")
    client = SyncAppClient()
    try:
        assert client.mode == "token"
    finally:
        client.close()


def test_demo_false_requires_credentials() -> None:
    with pytest.raises(AuthError, match="No credentials"):
        AppClient(demo=False)


@pytest.mark.asyncio
async def test_async_facade(router: Any, async_http_client: httpx.AsyncClient) -> None:
    router.add("/regions", REGIONS)
    router.add("/RU/emission", {"previousEnd": "2026-11-19T10:24:30Z"})
    router.add("/RU/character/by-name/ZIV/profile", {"username": "ZIV", "uuid": "u-1"})
    router.add("/RU/characters", [{"information": {"id": "u-1", "name": "ZIV"}}])
    router.add("/RU/friends/ZIV", {"friends": ["One"]})
    router.add("/RU/clans", {"totalClans": 1, "data": [{"id": "c", "name": "Clan"}]})
    router.add("/RU/operations/sessions", {"total": 1, "sessions": [{"id": 1, "map": "m"}]})
    router.add("/RU/auction/zyv9/lots", LOTS)
    router.add("/RU/auction/zyv9/history", HISTORY)

    async with AppClient(
        client_id="123", client_secret="x", region="RU", client=async_http_client
    ) as client:
        assert [r.id for r in await client.regions()] == ["RU", "EU"]
        emission = await client.emission()
        assert str(emission).startswith("Emission: inactive")
        assert str(await client.profile("ZIV")) == "ZIV · 0 stats"
        assert (await client.characters())[0].name == "ZIV"
        assert await client.friends("ZIV") == ["One"]
        assert (await client.clans()).total == 1
        assert (await client.sessions(map="m")).total == 1

        auction = client.auction("zyv9")
        assert repr(auction) == "Auction('zyv9')"
        page = await auction.lots(limit=3)
        assert str(page).startswith("1 of 2")
        assert page[0].price == 150
        assert str(page[0]).startswith("zyv9: 150 x 2")

        summary = await auction.summary(limit=2)
        assert summary.min_price == 100
        assert summary.max_price == 200
        assert "min 100" in str(summary)


def test_sync_facade(router: Any, http_client: httpx.Client) -> None:
    router.add("/regions", REGIONS)
    router.add("/EU/emission", {"currentStart": "2026-11-19T10:00:00Z"})
    router.add("/EU/character/by-uuid/u-1/profile", {"username": "ZIV", "uuid": "u-1"})
    router.add("/EU/auction/zyv9/lots", LOTS, times=2)
    router.add("/EU/auction/zyv9/lots", {"total": 2, "lots": []})
    router.add("/EU/auction/zyv9/history", HISTORY)
    router.add("/EU/operations/sessions", {"total": 1, "sessions": [{"id": 7, "map": "m"}]})

    with SyncAppClient(
        token="ready-token", region="EU", client=http_client
    ) as client:
        assert (await_regions := client.regions())[0].id == "RU"
        assert await_regions[1].id == "EU"
        assert "active since" in str(client.emission())
        assert str(client.profile("u-1", uuid=True)) == "ZIV · 0 stats"

        auction = client.auction("zyv9")
        assert repr(auction) == "SyncAuction('zyv9')"
        assert auction.lots(limit=3)[0].total_price == 300
        assert len(auction.all_lots()) == 1
        assert str(client.sessions()[0]) == "7 · m · 0 players"

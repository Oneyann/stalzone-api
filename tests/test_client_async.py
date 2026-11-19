"""Тесты асинхронного клиента."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from stalzone_api import AsyncClient, Unauthorized


@pytest.mark.asyncio
async def test_regions_and_emission(async_client, router):
    router.add("/regions", [{"id": "EU", "name": "EUROPE"}])
    router.add("/EU/emission", {"previousStart": "2026-11-19T09:01:35Z"})

    regions, emission = await asyncio.gather(async_client.regions(), async_client.emission())

    assert regions[0].id == "EU"
    assert emission.previous_start is not None


@pytest.mark.asyncio
async def test_auction_and_async_iterators(async_client, router):
    router.add(
        "/EU/auction/y1q9/lots",
        {"total": 2, "lots": [{"itemId": "y1q9", "amount": 1, "startPrice": 10, "buyoutPrice": 20}]},
    )
    router.add(
        "/EU/auction/y1q9/lots",
        {"total": 2, "lots": [{"itemId": "y1q9", "amount": 1, "startPrice": 30, "buyoutPrice": 40}]},
    )
    router.add(
        "/EU/auction/y1q9/lots",
        {"total": 2, "lots": [{"itemId": "y1q9", "amount": 1, "startPrice": 10, "buyoutPrice": 20}]},
    )
    router.add(
        "/EU/auction/y1q9/history",
        {"total": 1, "prices": [{"amount": 1, "price": 100, "time": "2026-01-01T00:00:00Z"}]},
    )

    lots = [lot async for lot in async_client.auction.iter_lots("y1q9", page_size=1)]
    page = await async_client.auction.lots("y1q9", limit=1)
    prices = [entry async for entry in async_client.auction.iter_history("y1q9", page_size=1)]

    assert [lot.price for lot in lots] == [10, 30]
    assert page.lots[0].price == 10
    assert prices[0].price == 100


@pytest.mark.asyncio
async def test_characters_clans_operations_friends(async_client, router):
    router.add("/EU/characters", [{"information": {"id": "1", "name": "One"}}])
    router.add("/EU/character/by-name/One/profile", {"username": "One", "uuid": "1"})
    router.add("/EU/character/by-uuid/1/profile", {"username": "One", "uuid": "1"})
    router.add("/EU/clans", {"totalClans": 1, "data": [{"id": "c", "name": "Clan"}]})
    router.add("/EU/clan/c/info", {"id": "c", "name": "Clan"})
    router.add("/EU/clan/c/members", [{"name": "One", "rank": "LEADER"}])
    router.add("/EU/operations/sessions", {"total": 1, "sessions": [{"id": 1, "map": "m"}]})
    router.add("/EU/friends/One", {"friends": ["Two"]})

    assert (await async_client.characters.list())[0].name == "One"
    assert (await async_client.characters.profile("One")).uuid == "1"
    assert (await async_client.characters.profile_by_uuid("1")).username == "One"
    assert (await async_client.clans.list()).total == 1
    assert (await async_client.clans.info("c")).name == "Clan"
    assert (await async_client.clans.members("c"))[0].rank == "LEADER"
    assert (await async_client.operations.sessions()).sessions[0].id == 1
    assert await async_client.friends("One") == ["Two"]


@pytest.mark.asyncio
async def test_clans_and_sessions_iterators(async_client, router):
    router.add("/EU/clans", {"totalClans": 2, "data": [{"id": "a", "name": "A"}]})
    router.add("/EU/clans", {"totalClans": 2, "data": [{"id": "b", "name": "B"}]})
    router.add("/EU/operations/sessions", {"total": 2, "sessions": [{"id": 1, "map": "m"}]})
    router.add("/EU/operations/sessions", {"total": 2, "sessions": [{"id": 2, "map": "m"}]})

    clans = [clan async for clan in async_client.clans.iter_all(page_size=1)]
    sessions = [session async for session in async_client.operations.iter_sessions(page_size=1)]

    assert [clan.name for clan in clans] == ["A", "B"]
    assert [session.id for session in sessions] == [1, 2]


@pytest.mark.asyncio
async def test_async_request_bytes_and_error(async_client, router):
    router.add("/image", response=httpx.Response(200, content=b"png"))
    router.add("/bad", {"title": "Unauthorized", "status": 401, "details": {}}, status=401)

    assert await async_client.request_bytes("GET", "image") == b"png"

    with pytest.raises(Unauthorized) as exc_info:
        await async_client.request("GET", "bad")
    assert exc_info.value.status == 401


@pytest.mark.asyncio
async def test_async_price_summary(async_client, router):
    router.add(
        "/EU/auction/y1q9/history",
        {
            "total": 2,
            "prices": [
                {"amount": 1, "price": 10, "time": "2026-01-01T00:00:00Z"},
                {"amount": 1, "price": 20, "time": "2026-01-02T00:00:00Z"},
            ],
        },
    )

    summary = await async_client.auction.price_summary("y1q9", limit=2)

    assert summary.mean_price == 15


def test_demo_async_client():
    instance = AsyncClient.demo(region="EU")
    try:
        assert instance.access_token
    finally:
        asyncio.run(instance.close())

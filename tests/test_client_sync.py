"""Тесты синхронного клиента: пути, параметры и разбор ответов."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from stalzone_api import (
    BadRequest,
    Client,
    DEMO_URL,
    NotFound,
    RateLimited,
    Unauthorized,
)

REGIONS = [
    {"id": "RU", "name": "RUSSIA"},
    {"id": "EU", "name": "EUROPE"},
]


def test_regions(client, router):
    router.add("/regions", REGIONS)

    regions = client.regions()

    assert [region.id for region in regions] == ["RU", "EU"]
    assert regions[1].name == "EUROPE"
    assert client._http.base_url == "https://eapi.stalzone.com"


def test_emission_uses_default_region(client, router):
    router.add(
        "/EU/emission",
        {"previousStart": "2026-11-19T09:01:35Z", "previousEnd": "2026-11-19T09:05:35Z"},
    )

    emission = client.emission()

    assert emission.active is False
    assert emission.previous_end == datetime(2026, 11, 19, 9, 5, 35, tzinfo=timezone.utc)


def test_emission_explicit_region(client, router):
    router.add("/SEA/emission", {"currentStart": "2026-11-19T10:00:00Z"})

    assert client.emission("sea").active is True


def test_auction_lots_params_and_parsing(client, router):
    router.add(
        "/EU/auction/y1q9/lots",
        {
            "total": 2,
            "lots": [
                {
                    "itemId": "y1q9",
                    "amount": 1,
                    "startPrice": 100,
                    "buyoutPrice": 500,
                    "additional": {},
                }
            ],
        },
    )

    page = client.auction.lots("y1q9", limit=10, offset=5, sort="current_price", order="asc")

    assert page.total == 2
    assert page.offset == 5
    assert page.lots[0].price == 100

    params = router.last_request.url.params
    assert params["limit"] == "10"
    assert params["offset"] == "5"
    assert params["sort"] == "current_price"
    assert params["order"] == "asc"
    assert router.last_request.url.path == "/EU/auction/y1q9/lots"


def test_auction_history_and_summary(client, router):
    router.add(
        "/EU/auction/y1q9/history",
        {
            "total": 3,
            "prices": [
                {"amount": 1, "price": 100, "time": "2026-01-01T00:00:00Z"},
                {"amount": 1, "price": 200, "time": "2026-01-02T00:00:00Z"},
                {"amount": 1, "price": 300, "time": "2026-01-03T00:00:00Z"},
            ],
        },
        times=2,
    )

    page = client.auction.history("y1q9", limit=3)
    summary = client.auction.price_summary("y1q9", limit=3)

    assert len(page.prices) == 3
    assert summary.min_price == 100
    assert summary.max_price == 300
    assert summary.median_price == 200


def test_auction_iterators(client, router):
    router.add(
        "/EU/auction/y1q9/lots",
        {"total": 3, "lots": [{"itemId": "y1q9", "amount": 1, "startPrice": 1, "buyoutPrice": 2}]},
    )
    router.add(
        "/EU/auction/y1q9/lots",
        {"total": 3, "lots": [{"itemId": "y1q9", "amount": 1, "startPrice": 2, "buyoutPrice": 3}]},
    )
    router.add(
        "/EU/auction/y1q9/lots",
        {"total": 3, "lots": [{"itemId": "y1q9", "amount": 1, "startPrice": 3, "buyoutPrice": 4}]},
    )
    router.add(
        "/EU/auction/y1q9/history",
        {"total": 1, "prices": [{"amount": 1, "price": 10, "time": "2026-01-01T00:00:00Z"}]},
    )

    lots = list(client.auction.iter_lots("y1q9", page_size=1, limit=2))
    history = list(client.auction.iter_history("y1q9", page_size=1))

    assert [lot.price for lot in lots] == [1, 2]
    assert history[0].price == 10


def test_character_profile_by_name_encodes_spaces(client, router):
    router.add(
        "/EU/character/by-name/Test 1/profile",
        {"username": "Test 1", "uuid": "uuid", "stats": []},
    )

    profile = client.characters.profile("Test 1")

    assert profile.username == "Test 1"
    assert router.last_request.url.raw_path.startswith(
        b"/EU/character/by-name/Test%201/profile"
    )


def test_character_profile_by_uuid(client, router):
    router.add(
        "/EU/character/by-uuid/abc-123/profile",
        {"username": "Player", "uuid": "abc-123", "clan": {"info": {"id": "c", "name": "Clan", "tag": "C"}}},
    )

    profile = client.characters.profile_by_uuid("abc-123")

    assert profile.uuid == "abc-123"
    assert profile.clan.info.tag == "C"


def test_characters_list_accepts_array_and_object(client, router):
    router.add("/EU/characters", [{"information": {"id": "1", "name": "One"}}])
    assert client.characters.list()[0].name == "One"

    router.add("/EU/characters", {"data": [{"information": {"id": "2", "name": "Two"}}]})
    assert client.characters.list()[0].name == "Two"


def test_clans_list_info_members(client, router):
    router.add(
        "/EU/clans",
        {"totalClans": 1, "data": [{"id": "clan-1", "name": "Clan", "tag": "TAG"}]},
    )
    router.add("/EU/clan/clan-1/info", {"id": "clan-1", "name": "Clan", "tag": "TAG", "level": 5})
    router.add(
        "/EU/clan/clan-1/members",
        {"members": [{"name": "Player", "rank": "OFFICER"}]},
    )

    clans = client.clans.list(limit=10)
    info = client.clans.info("clan-1")
    members = client.clans.members("clan-1")

    assert clans.total == 1
    assert info.level == 5
    assert members[0].name == "Player"
    assert router.requests[0].url.params["limit"] == "10"


def test_operations_sessions_filters(client, router):
    router.add(
        "/EU/operations/sessions",
        {"total": 1, "sessions": [{"id": 1610546606433042433, "map": "shock_therapy"}]},
    )

    page = client.operations.sessions(
        username="Player",
        map="shock_therapy",
        after=datetime(2026, 1, 2, tzinfo=timezone.utc),
        before="2026-02-01T00:00:00Z",
        limit=5,
        offset=2,
    )

    assert page.sessions[0].id == 1610546606433042433
    params = router.last_request.url.params
    assert params["username"] == "Player"
    assert params["map"] == "shock_therapy"
    assert params["after"] == "2026-01-02T00:00:00Z"
    assert params["before"] == "2026-02-01T00:00:00Z"
    assert params["limit"] == "5"
    assert params["offset"] == "2"


def test_friends_accepts_strings_and_objects(client, router):
    router.add("/EU/friends/Player", {"friends": ["One", {"name": "Two"}]})

    assert client.friends("Player") == ["One", "Two"]


def test_request_and_request_bytes(client, router):
    router.add("/custom", {"ok": True})
    router.add("/image", response=httpx.Response(200, content=b"\x89PNG\r\n"))

    assert client.request("GET", "custom") == {"ok": True}
    assert client.request_bytes("GET", "image") == b"\x89PNG\r\n"


def test_error_mapping(client, router):
    router.add(
        "/EU/characters",
        {"title": "Unauthorized", "status": 401, "details": {}},
        status=401,
    )
    with pytest.raises(Unauthorized) as exc_info:
        client.characters.list()
    assert exc_info.value.status == 401
    assert exc_info.value.title == "Unauthorized"

    router.add(
        "/EU/emission",
        {"title": "Bad request", "status": 400, "details": {"field": "region"}},
        status=400,
    )
    with pytest.raises(BadRequest) as exc_info:
        client.emission()
    assert exc_info.value.details == {"field": "region"}

    router.add(
        "/EU/auction/missing/lots",
        {"title": "Not found", "status": 404, "details": {}},
        status=404,
    )
    with pytest.raises(NotFound):
        client.auction.lots("missing")


def test_rate_limited_retry_after(client, router):
    router.add(
        "/regions",
        {"title": "Too many requests", "status": 429, "details": {}},
        status=429,
        headers={"Retry-After": "7"},
    )

    with pytest.raises(RateLimited) as exc_info:
        client.regions()

    assert exc_info.value.retry_after == 7


def test_environment_credentials(monkeypatch):
    monkeypatch.setenv("STALZONE_APP_ID", "999")
    monkeypatch.setenv("STALZONE_APP_SECRET", "env-secret")

    instance = Client(region="EU")
    try:
        assert instance.credentials.headers() == {
            "Client-Id": "999",
            "Client-Secret": "env-secret",
        }
    finally:
        instance.close()


def test_environment_token_has_priority(monkeypatch):
    monkeypatch.setenv("STALZONE_APP_ID", "999")
    monkeypatch.setenv("STALZONE_APP_SECRET", "env-secret")
    monkeypatch.setenv("STALZONE_ACCESS_TOKEN", "env-token")

    instance = Client(region="EU")
    try:
        assert instance.credentials.headers() == {"Authorization": "Bearer env-token"}
    finally:
        instance.close()


def test_demo_client():
    instance = Client.demo(region="EU")
    try:
        assert instance._http.base_url == DEMO_URL
        assert instance.credentials.headers()["Authorization"].startswith("Bearer ")
    finally:
        instance.close()


def test_missing_region_error():
    instance = Client(app_id="1", app_secret="x")
    try:
        with pytest.raises(ValueError, match="region is required"):
            instance.emission()
    finally:
        instance.close()

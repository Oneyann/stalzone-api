"""Тесты моделей: разбор ответов API и терпимость к изменениям схемы."""

from __future__ import annotations

from datetime import datetime, timezone

from stalzone_api import (
    Character,
    CharacterProfile,
    Clan,
    ClanMember,
    ClanRank,
    Emission,
    Lot,
    LotPage,
    OperationSession,
    PriceEntry,
    PricePage,
    PriceSummary,
    Region,
)
from stalzone_api.models.common import format_datetime, parse_datetime


def test_lot_without_current_price():
    lot = Lot.from_dict(
        {
            "itemId": "y1q9",
            "amount": 3,
            "startPrice": 100,
            "buyoutPrice": 500,
            "startTime": "2026-01-01T10:00:00Z",
            "endTime": "2026-01-02T10:00:00.1234567Z",
            "additional": {},
            "unknownField": "keep-me",
        }
    )

    assert lot.current_price is None
    assert lot.has_bids is False
    assert lot.price == 100
    assert lot.total_price == 300
    assert lot.end_time == datetime(2026, 1, 2, 10, 0, 0, 123456, tzinfo=timezone.utc)
    assert lot.extra == {"unknownField": "keep-me"}


def test_lot_with_bid_and_numeric_strings():
    lot = Lot.from_dict(
        {
            "itemId": "y1q9",
            "amount": "2",
            "startPrice": "100",
            "currentPrice": "150",
            "buyoutPrice": "500",
        }
    )

    assert lot.current_price == 150
    assert lot.price == 150
    assert lot.total_price == 300
    assert lot.has_bids is True


def test_lot_page_and_price_page_pagination():
    lots = LotPage.from_dict(
        {"total": 5, "lots": [{"itemId": "a", "amount": 1, "startPrice": 1, "buyoutPrice": 2}]},
        offset=2,
    )

    assert len(lots) == 1
    assert lots.next_offset == 3
    assert lots.is_last is False
    assert lots[0].item_id == "a"

    prices = PricePage.from_dict(
        {"total": 1, "prices": [{"amount": 1, "price": 10, "time": "2026-01-01T00:00:00Z"}]},
        offset=0,
    )
    assert prices.is_last is True
    assert prices.prices[0].price == 10


def test_price_summary():
    prices = [
        PriceEntry.from_dict({"amount": 1, "price": 100, "time": "2026-01-01T00:00:00Z"}),
        PriceEntry.from_dict({"amount": 2, "price": 300, "time": "2026-01-02T00:00:00Z"}),
        PriceEntry.from_dict({"amount": 1, "price": 200, "time": "2026-01-03T00:00:00Z"}),
    ]

    summary = PriceSummary.from_prices(prices)

    assert summary.count == 3
    assert summary.min_price == 100
    assert summary.max_price == 300
    assert summary.mean_price == 200
    assert summary.median_price == 200
    assert summary.total_amount == 4
    assert summary.latest_price == 200
    assert summary.latest_time == datetime(2026, 1, 3, tzinfo=timezone.utc)


def test_price_summary_empty():
    summary = PriceSummary.from_prices([])

    assert summary.count == 0
    assert summary.min_price is None
    assert summary.mean_price is None


def test_character_from_array_entry():
    character = Character.from_dict(
        {
            "information": {
                "id": "uuid-1",
                "name": "Test-1",
                "creationTime": "2021-12-03T10:15:30Z",
            },
            "clan": {
                "info": {"id": "clan-1", "name": "Clan #1", "tag": "TAG", "level": 2},
                "member": {"name": "Test-1", "rank": "LEADER", "joinTime": "2022-07-03T10:15:30Z"},
            },
        }
    )

    assert character.id == "uuid-1"
    assert character.name == "Test-1"
    assert character.clan.info.tag == "TAG"
    assert character.clan.member.rank is ClanRank.LEADER


def test_character_flat_fallback():
    character = Character.from_dict({"id": "uuid-2", "name": "Flat"})

    assert character.id == "uuid-2"
    assert character.name == "Flat"


def test_character_profile_stats():
    profile = CharacterProfile.from_dict(
        {
            "username": "Firas_",
            "uuid": "uuid",
            "status": "PvP",
            "alliance": "duty",
            "lastLogin": "2026-11-19T00:00:00Z",
            "displayedAchievements": ["a", "b"],
            "stats": [
                {"id": "sea-alienation-max-key-ops", "type": "INTEGER", "value": 4},
                {"id": "joined-guild", "type": "DATE", "value": "2026-11-12T22:34:18.987Z"},
                {"id": "unknown", "type": "NEW_TYPE", "value": "x"},
            ],
            "unknown": 1,
        }
    )

    assert profile.username == "Firas_"
    assert profile.stat("sea-alienation-max-key-ops").value == 4
    assert profile.stats_dict()["unknown"] == "x"
    assert profile.stats[2].type == "NEW_TYPE"
    assert profile.extra == {"unknown": 1}


def test_clan_member_unknown_rank():
    member = ClanMember.from_dict({"name": "Player", "rank": "SUPER_BOSS"})

    assert member.rank == "SUPER_BOSS"
    assert isinstance(member.rank, ClanRank)


def test_clan_parsing():
    clan = Clan.from_dict(
        {
            "id": "clan-1",
            "name": "Wuthering Waves",
            "tag": "WUTH",
            "level": 1,
            "levelPoints": 396315,
            "registrationTime": "2022-01-01T00:00:00Z",
            "alliance": "covenant",
            "description": "desc",
            "leader": "Leader",
            "memberCount": 42,
        }
    )

    assert clan.tag == "WUTH"
    assert clan.level_points == 396315
    assert clan.member_count == 42
    assert str(clan) == "WUTH"


def test_emission_without_current_start():
    emission = Emission.from_dict(
        {
            "previousStart": "2026-11-19T09:01:35Z",
            "previousEnd": "2026-11-19T09:05:35Z",
        }
    )

    assert emission.active is False
    assert emission.previous_end == datetime(2026, 11, 19, 9, 5, 35, tzinfo=timezone.utc)


def test_operation_session_int64_and_participants():
    session = OperationSession.from_dict(
        {
            "id": 1610546606433042433,
            "map": "shock_therapy",
            "startTime": "2026-11-19T02:23:10Z",
            "endTime": "2026-11-19T02:40:00Z",
            "difficulty": 3,
            "sessionDurationSeconds": 1010.5,
            "difficultyReward": 10,
            "participants": [{"username": "Player", "death": 2, "mobKills": 10}],
        }
    )

    assert session.id == 1610546606433042433
    assert session.participants[0].mob_kills == 10
    assert session.participant("player").death == 2
    assert session.participant("nobody") is None


def test_region_normalization():
    assert Region("eu") is Region.EU
    assert Region("неизвестный").value == "НЕИЗВЕСТНЫЙ"
    assert str(Region.SEA) == "SEA"


def test_datetime_helpers():
    value = "2026-01-02T03:04:05.123456789Z"
    parsed = parse_datetime(value)
    assert parsed == datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)
    assert format_datetime(parsed) == "2026-01-02T03:04:05Z"
    assert format_datetime("already-formatted") == "already-formatted"
    assert parse_datetime(None) is None
    assert parse_datetime("") is None

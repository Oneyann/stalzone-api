"""Typed, dependency-free models returned by the client."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


def _dt(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp coming from the API."""

    return datetime.fromisoformat(value) if value else None


def _when(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "-"


class Region(StrEnum):
    """Game server region. Accepts any case: ``Region("eu")`` works."""

    RU = "RU"
    EU = "EU"
    NA = "NA"
    SEA = "SEA"
    NEA = "NEA"

    @classmethod
    def _missing_(cls, value: object) -> "Region | None":
        if isinstance(value, str):
            return cls.__members__.get(value.strip().upper())
        return None


@dataclass(slots=True)
class Page(Generic[T]):
    """One page of a listing plus the total number of entries."""

    items: list[T]
    total: int = 0
    offset: int = 0

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]

    @property
    def next_offset(self) -> int:
        return self.offset + len(self.items)

    @property
    def is_last(self) -> bool:
        return self.next_offset >= self.total

    def __str__(self) -> str:
        return f"{len(self.items)} of {self.total}"


@dataclass(slots=True)
class RegionInfo:
    id: str
    name: str
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "RegionInfo":
        return cls(id=str(data.get("id", "")), name=str(data.get("name", "")), raw=data)

    def __str__(self) -> str:
        return f"{self.id} ({self.name})"


@dataclass(slots=True)
class Emission:
    current_start: datetime | None
    previous_start: datetime | None
    previous_end: datetime | None
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Emission":
        return cls(
            _dt(data.get("currentStart")),
            _dt(data.get("previousStart")),
            _dt(data.get("previousEnd")),
            raw=data,
        )

    @property
    def active(self) -> bool:
        return self.current_start is not None and (
            self.previous_end is None or self.current_start > self.previous_end
        )

    def __str__(self) -> str:
        state = "active" if self.active else "inactive"
        return f"Emission: {state}, last ended {_when(self.previous_end)}"


@dataclass(slots=True)
class Lot:
    item_id: str
    amount: int
    start_price: int
    buyout_price: int
    start_time: datetime | None
    end_time: datetime | None
    current_price: int | None = None
    additional: dict = field(default_factory=dict, repr=False)
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Lot":
        return cls(
            item_id=str(data.get("itemId", "")),
            amount=int(data.get("amount") or 0),
            start_price=int(data.get("startPrice") or 0),
            buyout_price=int(data.get("buyoutPrice") or 0),
            start_time=_dt(data.get("startTime")),
            end_time=_dt(data.get("endTime")),
            current_price=data.get("currentPrice"),
            additional=data.get("additional") or {},
            raw=data,
        )

    @property
    def price(self) -> int:
        """Current bid, otherwise the start price (buyout-only lots use buyout)."""

        if self.current_price is not None:
            return self.current_price
        return self.start_price or self.buyout_price

    @property
    def total_price(self) -> int:
        return self.price * self.amount

    @property
    def has_bids(self) -> bool:
        return self.current_price is not None

    def __str__(self) -> str:
        return f"{self.item_id}: {self.price} x {self.amount} (ends {_when(self.end_time)})"


@dataclass(slots=True)
class Price:
    amount: int
    price: int
    time: datetime | None
    additional: dict = field(default_factory=dict, repr=False)
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Price":
        return cls(
            amount=int(data.get("amount") or 0),
            price=int(data.get("price") or 0),
            time=_dt(data.get("time")),
            additional=data.get("additional") or {},
            raw=data,
        )

    def __str__(self) -> str:
        return f"{self.price} x {self.amount} ({_when(self.time)})"


@dataclass(slots=True)
class Clan:
    id: str
    name: str
    tag: str
    level: int
    level_points: int
    registration_time: datetime | None
    alliance: str
    description: str
    leader: str
    member_count: int
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Clan":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            tag=str(data.get("tag", "")),
            level=int(data.get("level") or 0),
            level_points=int(data.get("levelPoints") or 0),
            registration_time=_dt(data.get("registrationTime")),
            alliance=str(data.get("alliance") or ""),
            description=str(data.get("description") or ""),
            leader=str(data.get("leader") or ""),
            member_count=int(data.get("memberCount") or 0),
            raw=data,
        )

    def __str__(self) -> str:
        return f"{self.name} [{self.tag}]" if self.tag else self.name


@dataclass(slots=True)
class ClanMember:
    name: str
    rank: str
    join_time: datetime | None
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "ClanMember":
        return cls(
            name=str(data.get("name", "")),
            rank=str(data.get("rank") or ""),
            join_time=_dt(data.get("joinTime")),
            raw=data,
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.rank})"


@dataclass(slots=True)
class Character:
    id: str
    name: str
    creation_time: datetime | None
    clan: Clan | None = None
    member: ClanMember | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        info = data.get("information") or {}
        clan = data.get("clan") or {}
        return cls(
            id=str(info.get("id", "")),
            name=str(info.get("name", "")),
            creation_time=_dt(info.get("creationTime")),
            clan=Clan.from_dict(clan["info"]) if clan.get("info") else None,
            member=ClanMember.from_dict(clan["member"]) if clan.get("member") else None,
            raw=data,
        )

    def __str__(self) -> str:
        return f"{self.name} (since {_when(self.creation_time)})"


@dataclass(slots=True)
class Profile:
    username: str
    uuid: str
    status: str
    alliance: str
    last_login: datetime | None
    displayed_achievements: list[str]
    clan: Clan | None = None
    member: ClanMember | None = None
    stats: list[dict] = field(default_factory=list, repr=False)
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        clan = data.get("clan") or {}
        return cls(
            username=str(data.get("username", "")),
            uuid=str(data.get("uuid", "")),
            status=str(data.get("status") or ""),
            alliance=str(data.get("alliance") or ""),
            last_login=_dt(data.get("lastLogin")),
            displayed_achievements=list(data.get("displayedAchievements") or []),
            clan=Clan.from_dict(clan["info"]) if clan.get("info") else None,
            member=ClanMember.from_dict(clan["member"]) if clan.get("member") else None,
            stats=list(data.get("stats") or []),
            raw=data,
        )

    def stat(self, stat_id: str) -> dict | None:
        """Raw statistic entry by id, e.g. ``profile.stat("kills")``."""

        return next((s for s in self.stats if s.get("id") == stat_id), None)

    def __str__(self) -> str:
        return f"{self.username} ({len(self.stats)} stats)"


@dataclass(slots=True)
class Participant:
    username: str
    death: int
    mob_kills: int
    damage_received: float
    damage_dealt: float
    armor_class: str
    armor_item_id: str
    armor_level: int
    primary_weapon_item_id: str
    primary_weapon_level: int
    secondary_weapon_item_id: str
    secondary_weapon_level: int
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Participant":
        return cls(
            username=str(data.get("username", "")),
            death=int(data.get("death") or 0),
            mob_kills=int(data.get("mobKills") or 0),
            damage_received=float(data.get("damageReceived") or 0),
            damage_dealt=float(data.get("damageDealt") or 0),
            armor_class=str(data.get("armorClass") or ""),
            armor_item_id=str(data.get("armorItemId") or ""),
            armor_level=int(data.get("armorLevel") or 0),
            primary_weapon_item_id=str(data.get("primaryWeaponItemId") or ""),
            primary_weapon_level=int(data.get("primaryWeaponLevel") or 0),
            secondary_weapon_item_id=str(data.get("secondaryWeaponItemId") or ""),
            secondary_weapon_level=int(data.get("secondaryWeaponLevel") or 0),
            raw=data,
        )

    def __str__(self) -> str:
        return f"{self.username}: {self.mob_kills} kills, {self.damage_dealt:.0f} damage"


@dataclass(slots=True)
class Session:
    id: int
    map: str
    start_time: datetime | None
    end_time: datetime | None
    difficulty: int
    duration: float
    reward: int
    participants: list[Participant] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(
            id=int(data.get("id") or 0),
            map=str(data.get("map") or ""),
            start_time=_dt(data.get("startTime")),
            end_time=_dt(data.get("endTime")),
            difficulty=int(data.get("difficulty") or 0),
            duration=float(data.get("sessionDurationSeconds") or 0),
            reward=int(data.get("difficultyReward") or 0),
            participants=[Participant.from_dict(p) for p in data.get("participants") or []],
            raw=data,
        )

    def participant(self, username: str) -> Participant | None:
        return next(
            (p for p in self.participants if p.username.casefold() == username.casefold()),
            None,
        )

    def __str__(self) -> str:
        return f"{self.map} (difficulty {self.difficulty}, {len(self.participants)} players)"

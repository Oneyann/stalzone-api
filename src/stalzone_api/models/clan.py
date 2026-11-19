"""Models for the clan endpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .common import parse_datetime

__all__ = ["Clan", "ClanList", "ClanMember", "ClanRank"]


class ClanRank(str, Enum):
    """Member rank inside a clan."""

    RECRUIT = "RECRUIT"
    COMMONER = "COMMONER"
    SOLDIER = "SOLDIER"
    SERGEANT = "SERGEANT"
    OFFICER = "OFFICER"
    COLONEL = "COLONEL"
    LEADER = "LEADER"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def _missing_(cls, value: object) -> "ClanRank | None":
        if isinstance(value, str) and value.strip():
            normalized = value.strip().upper()
            if normalized in cls.__members__:
                return cls.__members__[normalized]
            member = str.__new__(cls, normalized)
            member._name_ = normalized
            member._value_ = normalized
            return member
        return None


@dataclass
class ClanMember:
    name: str
    rank: ClanRank | None = None
    join_time: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClanMember":
        known = {"name", "rank", "joinTime"}
        rank = data.get("rank")
        return cls(
            name=str(data.get("name", "")),
            rank=ClanRank(rank) if rank is not None else None,
            join_time=parse_datetime(data.get("joinTime")),
            extra={k: v for k, v in data.items() if k not in known},
        )


@dataclass
class Clan:
    id: str
    name: str
    tag: str = ""
    level: int = 0
    level_points: int = 0
    registration_time: datetime | None = None
    alliance: str | None = None
    description: str = ""
    leader: str | None = None
    member_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Clan":
        known = {
            "id",
            "name",
            "tag",
            "level",
            "levelPoints",
            "registrationTime",
            "alliance",
            "description",
            "leader",
            "memberCount",
        }
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            tag=str(data.get("tag") or ""),
            level=int(data.get("level") or 0),
            level_points=int(data.get("levelPoints") or 0),
            registration_time=parse_datetime(data.get("registrationTime")),
            alliance=data.get("alliance"),
            description=str(data.get("description") or ""),
            leader=data.get("leader"),
            member_count=int(data.get("memberCount") or 0),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def __str__(self) -> str:
        return self.tag or self.name


@dataclass
class ClanList:
    """Response of ``GET /{region}/clans``."""

    total_clans: int
    data: list[Clan] = field(default_factory=list)
    offset: int = 0

    @property
    def items(self) -> list[Clan]:
        return self.data

    @property
    def total(self) -> int:
        return self.total_clans

    def __iter__(self):
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, index: int) -> Clan:
        return self.data[index]

    @property
    def next_offset(self) -> int:
        return self.offset + len(self.data)

    @property
    def is_last(self) -> bool:
        return not self.data or self.next_offset >= self.total_clans

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, offset: int = 0) -> "ClanList":
        return cls(
            total_clans=int(data.get("totalClans") or 0),
            data=[Clan.from_dict(entry) for entry in data.get("data") or []],
            offset=offset,
        )

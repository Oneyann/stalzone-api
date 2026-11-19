"""Models for character endpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .clan import Clan, ClanMember
from .common import parse_datetime

__all__ = [
    "Character",
    "CharacterClan",
    "CharacterInformation",
    "CharacterProfile",
    "CharacterStat",
    "StatType",
]


class StatType(str, Enum):
    """Type of a profile statistic."""

    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    DATE = "DATE"
    DURATION = "DURATION"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def _missing_(cls, value: object) -> "StatType | None":
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
class CharacterInformation:
    """Brief information about a character."""

    id: str
    name: str
    creation_time: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterInformation":
        known = {"id", "name", "creationTime"}
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            creation_time=parse_datetime(data.get("creationTime")),
            extra={k: v for k, v in data.items() if k not in known},
        )


@dataclass
class CharacterClan:
    """Clan information attached to a character."""

    info: Clan | None = None
    member: ClanMember | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterClan":
        info = data.get("info")
        member = data.get("member")
        return cls(
            info=Clan.from_dict(info) if isinstance(info, dict) else None,
            member=ClanMember.from_dict(member) if isinstance(member, dict) else None,
            extra={k: v for k, v in data.items() if k not in ("info", "member")},
        )


@dataclass
class Character:
    """One entry of ``GET /{region}/characters``."""

    information: CharacterInformation
    clan: CharacterClan | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Character":
        information = data.get("information")
        if not isinstance(information, dict):
            # Be tolerant: some deployments return a flat object.
            information = data
        clan = data.get("clan")
        return cls(
            information=CharacterInformation.from_dict(information),
            clan=CharacterClan.from_dict(clan) if isinstance(clan, dict) else None,
            extra={k: v for k, v in data.items() if k not in ("information", "clan")},
        )

    @property
    def id(self) -> str:
        return self.information.id

    @property
    def name(self) -> str:
        return self.information.name


@dataclass
class CharacterStat:
    id: str
    type: StatType | None = None
    value: Any = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterStat":
        stat_type = data.get("type")
        return cls(
            id=str(data.get("id", "")),
            type=StatType(stat_type) if stat_type is not None else None,
            value=data.get("value"),
            extra={k: v for k, v in data.items() if k not in ("id", "type", "value")},
        )


@dataclass
class CharacterProfile:
    """Response of ``/{region}/character/.../profile``."""

    username: str
    uuid: str
    status: str | None = None
    alliance: str | None = None
    last_login: datetime | None = None
    displayed_achievements: list[str] = field(default_factory=list)
    clan: CharacterClan | None = None
    stats: list[CharacterStat] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterProfile":
        known = {
            "username",
            "uuid",
            "status",
            "alliance",
            "lastLogin",
            "displayedAchievements",
            "clan",
            "stats",
        }
        clan = data.get("clan")
        return cls(
            username=str(data.get("username", "")),
            uuid=str(data.get("uuid", "")),
            status=data.get("status"),
            alliance=data.get("alliance"),
            last_login=parse_datetime(data.get("lastLogin")),
            displayed_achievements=list(data.get("displayedAchievements") or []),
            clan=CharacterClan.from_dict(clan) if isinstance(clan, dict) else None,
            stats=[CharacterStat.from_dict(entry) for entry in data.get("stats") or []],
            extra={k: v for k, v in data.items() if k not in known},
        )

    def stat(self, stat_id: str) -> CharacterStat | None:
        """Find a statistic by its id."""

        for entry in self.stats:
            if entry.id == stat_id:
                return entry
        return None

    def __str__(self) -> str:
        clan = ""
        if self.clan is not None and self.clan.info is not None:
            clan = f" [{self.clan.info.tag}]" if self.clan.info.tag else ""
        return f"{self.username or self.uuid}{clan} · {len(self.stats)} stats"

    def stats_dict(self) -> dict[str, Any]:
        return {entry.id: entry.value for entry in self.stats}

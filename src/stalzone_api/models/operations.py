"""Models for operation sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator

from .common import parse_datetime

__all__ = ["OperationSession", "SessionPage", "SessionParticipant"]


@dataclass
class SessionParticipant:
    username: str
    death: int = 0
    mob_kills: int = 0
    damage_received: float = 0.0
    damage_dealt: float = 0.0
    armor_class: str | None = None
    armor_item_id: str | None = None
    armor_level: int = 0
    primary_weapon_item_id: str | None = None
    primary_weapon_level: int = 0
    secondary_weapon_item_id: str | None = None
    secondary_weapon_level: int = 0
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionParticipant":
        known = {
            "username",
            "death",
            "mobKills",
            "damageReceived",
            "damageDealt",
            "armorClass",
            "armorItemId",
            "armorLevel",
            "primaryWeaponItemId",
            "primaryWeaponLevel",
            "secondaryWeaponItemId",
            "secondaryWeaponLevel",
        }
        return cls(
            username=str(data.get("username", "")),
            death=int(data.get("death") or 0),
            mob_kills=int(data.get("mobKills") or 0),
            damage_received=float(data.get("damageReceived") or 0.0),
            damage_dealt=float(data.get("damageDealt") or 0.0),
            armor_class=data.get("armorClass"),
            armor_item_id=data.get("armorItemId"),
            armor_level=int(data.get("armorLevel") or 0),
            primary_weapon_item_id=data.get("primaryWeaponItemId"),
            primary_weapon_level=int(data.get("primaryWeaponLevel") or 0),
            secondary_weapon_item_id=data.get("secondaryWeaponItemId"),
            secondary_weapon_level=int(data.get("secondaryWeaponLevel") or 0),
            extra={k: v for k, v in data.items() if k not in known},
        )


@dataclass
class OperationSession:
    id: int
    map: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    difficulty: int = 0
    session_duration_seconds: float = 0.0
    difficulty_reward: int = 0
    participants: list[SessionParticipant] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperationSession":
        known = {
            "id",
            "map",
            "startTime",
            "endTime",
            "difficulty",
            "sessionDurationSeconds",
            "difficultyReward",
            "participants",
        }
        return cls(
            id=int(data.get("id") or 0),
            map=str(data.get("map", "")),
            start_time=parse_datetime(data.get("startTime")),
            end_time=parse_datetime(data.get("endTime")),
            difficulty=int(data.get("difficulty") or 0),
            session_duration_seconds=float(data.get("sessionDurationSeconds") or 0.0),
            difficulty_reward=int(data.get("difficultyReward") or 0),
            participants=[SessionParticipant.from_dict(entry) for entry in data.get("participants") or []],
            extra={k: v for k, v in data.items() if k not in known},
        )

    def participant(self, username: str) -> SessionParticipant | None:
        username = username.casefold()
        for entry in self.participants:
            if entry.username.casefold() == username:
                return entry
        return None

    def __str__(self) -> str:
        return f"{self.id} · {self.map} · {len(self.participants)} players"


@dataclass
class SessionPage:
    """Response of ``GET /{region}/operations/sessions``."""

    total: int
    sessions: list[OperationSession] = field(default_factory=list)
    offset: int = 0

    @property
    def items(self) -> list[OperationSession]:
        return self.sessions

    def __iter__(self) -> Iterator[OperationSession]:
        return iter(self.sessions)

    def __len__(self) -> int:
        return len(self.sessions)

    def __getitem__(self, index: int) -> OperationSession:
        return self.sessions[index]

    @property
    def next_offset(self) -> int:
        return self.offset + len(self.sessions)

    @property
    def is_last(self) -> bool:
        return not self.sessions or self.next_offset >= self.total

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, offset: int = 0) -> "SessionPage":
        return cls(
            total=int(data.get("total") or 0),
            sessions=[OperationSession.from_dict(entry) for entry in data.get("sessions") or []],
            offset=offset,
        )

    def __str__(self) -> str:
        lines = [str(session) for session in self.sessions]
        return f"{len(lines)} of {self.total}" + ("\n" + "\n".join(lines) if lines else "")

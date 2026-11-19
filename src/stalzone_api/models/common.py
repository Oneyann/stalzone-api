"""Shared helpers, enums and small value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

__all__ = [
    "Alliance",
    "Realm",
    "Region",
    "RegionInfo",
    "format_datetime",
    "parse_datetime",
    "region_value",
]


def _fallback_member(cls: type[Enum], value: str) -> Any:
    """Create a pseudo-member for values unknown to the enum (forward compatibility)."""

    member = str.__new__(cls, value)  # type: ignore[arg-type]
    member._name_ = value  # type: ignore[attr-defined]
    member._value_ = value  # type: ignore[attr-defined]
    return member


class Region(str, Enum):
    """Game region (server). Unknown regions are accepted as-is."""

    RU = "RU"
    EU = "EU"
    NA = "NA"
    SEA = "SEA"
    NEA = "NEA"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def _missing_(cls, value: object) -> "Region | None":
        if isinstance(value, str) and value.strip():
            normalized = value.strip().upper()
            if normalized in cls.__members__:
                return cls.__members__[normalized]
            return _fallback_member(cls, normalized)
        return None


class Realm(str, Enum):
    """Game version the items database is tied to."""

    RU = "ru"
    GLOBAL = "global"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def _missing_(cls, value: object) -> "Realm | None":
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
            aliases = {"en": "global", "world": "global", "global": "global", "ru": "ru"}
            alias = aliases.get(normalized)
            if alias is not None:
                return cls(alias)
        return None


class Alliance(str, Enum):
    """Known in-game alliances; unknown values are still accepted."""

    DUTY = "duty"
    COVENANT = "covenant"
    MERCENARIES = "mercenaries"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def _missing_(cls, value: object) -> "Alliance | None":
        if isinstance(value, str) and value.strip():
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
            return _fallback_member(cls, normalized)
        return None


def region_value(value: str | Region) -> str:
    """Normalize a region argument to the uppercase string expected by the API."""

    if isinstance(value, Enum):
        value = value.value
    normalized = str(value).strip().upper()
    if not normalized:
        raise ValueError("region must not be empty")
    return normalized


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp returned by the API (``Z`` suffix and >6 digits supported)."""

    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        # Python < 3.11 rejects more than 6 fractional digits; trim them.
        fixed = re.sub(r"(\.\d{6})\d+", r"\1", text)
        if fixed == text:
            return None
        parsed = datetime.fromisoformat(fixed)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_datetime(value: datetime | str) -> str:
    """Serialize a datetime the way the API expects (``2025-01-20T10:15:30Z``)."""

    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class RegionInfo:
    """One entry of ``GET /regions``."""

    id: str
    name: str
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegionInfo":
        known = {"id", "name"}
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def __str__(self) -> str:
        return self.id

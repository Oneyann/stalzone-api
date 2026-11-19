"""Model for the emission endpoint."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .common import parse_datetime

__all__ = ["Emission"]


@dataclass
class Emission:
    """Current and previous emission timestamps."""

    current_start: datetime | None = None
    previous_start: datetime | None = None
    previous_end: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Emission":
        known = {"currentStart", "previousStart", "previousEnd"}
        return cls(
            current_start=parse_datetime(data.get("currentStart")),
            previous_start=parse_datetime(data.get("previousStart")),
            previous_end=parse_datetime(data.get("previousEnd")),
            extra={k: v for k, v in data.items() if k not in known},
        )

    @property
    def active(self) -> bool:
        """Whether an emission is running right now."""

        return self.current_start is not None

    def __str__(self) -> str:
        if self.active and self.current_start is not None:
            return f"Emission: active since {self.current_start:%Y-%m-%d %H:%M} UTC"
        if self.previous_end is not None:
            return f"Emission: inactive, last ended {self.previous_end:%Y-%m-%d %H:%M} UTC"
        return "Emission: no data"

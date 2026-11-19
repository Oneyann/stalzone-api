"""Models for the auction endpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import Any, Iterator, Sequence

from .common import parse_datetime

__all__ = ["Lot", "LotPage", "PriceEntry", "PricePage", "PriceSummary"]


class _PageMixin:
    """Shared behaviour for paginated responses (``total`` + ``offset``)."""

    total: int
    offset: int

    @property
    def items(self) -> Sequence[Any]:
        raise NotImplementedError

    def __iter__(self) -> Iterator[Any]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> Any:
        return self.items[index]

    @property
    def next_offset(self) -> int:
        return self.offset + len(self.items)

    @property
    def is_last(self) -> bool:
        return not self.items or self.next_offset >= self.total


@dataclass
class Lot:
    """An active auction lot."""

    item_id: str
    amount: int
    start_price: int
    buyout_price: int
    start_time: datetime | None = None
    end_time: datetime | None = None
    current_price: int | None = None
    additional: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Lot":
        known = {
            "itemId",
            "amount",
            "startPrice",
            "currentPrice",
            "buyoutPrice",
            "startTime",
            "endTime",
            "additional",
        }
        return cls(
            item_id=str(data.get("itemId", "")),
            amount=int(data.get("amount") or 0),
            start_price=int(data.get("startPrice") or 0),
            buyout_price=int(data.get("buyoutPrice") or 0),
            start_time=parse_datetime(data.get("startTime")),
            end_time=parse_datetime(data.get("endTime")),
            current_price=int(data["currentPrice"]) if data.get("currentPrice") is not None else None,
            additional=dict(data.get("additional") or {}),
            extra={k: v for k, v in data.items() if k not in known},
        )

    @property
    def price(self) -> int:
        """Current bid if there is one, otherwise the start price."""

        return int(self.current_price if self.current_price is not None else self.start_price)

    @property
    def total_price(self) -> int:
        """Price of the whole stack."""

        return self.price * self.amount

    @property
    def has_bids(self) -> bool:
        return self.current_price is not None

    def __str__(self) -> str:
        end = self.end_time.strftime("%Y-%m-%d %H:%M") if self.end_time else "—"
        return f"{self.item_id}: {self.price} x {self.amount} (ends {end})"


@dataclass
class LotPage(_PageMixin):
    """Response of ``/{region}/auction/{item}/lots``."""

    total: int
    lots: list[Lot] = field(default_factory=list)
    offset: int = 0

    @property
    def items(self) -> list[Lot]:
        return self.lots

    def __str__(self) -> str:
        lines = [str(lot) for lot in self.lots]
        return f"{len(lines)} of {self.total}" + ("\n" + "\n".join(lines) if lines else "")

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, offset: int = 0) -> "LotPage":
        return cls(
            total=int(data.get("total") or 0),
            lots=[Lot.from_dict(entry) for entry in data.get("lots") or []],
            offset=offset,
        )


@dataclass
class PriceEntry:
    """A completed auction purchase."""

    amount: int
    price: int
    time: datetime | None = None
    additional: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    def __str__(self) -> str:
        time = self.time.strftime("%Y-%m-%d %H:%M") if self.time else "—"
        return f"{self.price} x {self.amount} at {time}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PriceEntry":
        known = {"amount", "price", "time", "additional"}
        return cls(
            amount=int(data.get("amount") or 0),
            price=int(data.get("price") or 0),
            time=parse_datetime(data.get("time")),
            additional=dict(data.get("additional") or {}),
            extra={k: v for k, v in data.items() if k not in known},
        )


@dataclass
class PricePage(_PageMixin):
    """Response of ``/{region}/auction/{item}/history``."""

    total: int
    prices: list[PriceEntry] = field(default_factory=list)
    offset: int = 0

    @property
    def items(self) -> list[PriceEntry]:
        return self.prices

    def __str__(self) -> str:
        lines = [str(entry) for entry in self.prices]
        return f"{len(lines)} of {self.total}" + ("\n" + "\n".join(lines) if lines else "")

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, offset: int = 0) -> "PricePage":
        return cls(
            total=int(data.get("total") or 0),
            prices=[PriceEntry.from_dict(entry) for entry in data.get("prices") or []],
            offset=offset,
        )


@dataclass
class PriceSummary:
    """Aggregated statistics over a slice of the price history."""

    count: int
    min_price: int | None
    max_price: int | None
    mean_price: float | None
    median_price: float | None
    total_amount: int
    latest_price: int | None
    latest_time: datetime | None

    @classmethod
    def from_prices(cls, prices: Sequence[PriceEntry]) -> "PriceSummary":
        values = [entry.price for entry in prices if entry.price is not None]
        if not values:
            return cls(0, None, None, None, None, 0, None, None)
        ordered = sorted(prices, key=lambda entry: entry.time.timestamp() if entry.time else 0.0)
        latest = ordered[-1]
        return cls(
            count=len(values),
            min_price=min(values),
            max_price=max(values),
            mean_price=sum(values) / len(values),
            median_price=float(median(values)),
            total_amount=sum(entry.amount for entry in prices),
            latest_price=latest.price,
            latest_time=latest.time,
        )

    def __str__(self) -> str:
        if not self.count:
            return "Price summary: no sales"
        return (
            f"Price summary ({self.count} sales): "
            f"min {self.min_price}, mean {self.mean_price:.0f}, "
            f"median {self.median_price:.0f}, max {self.max_price}, "
            f"last {self.latest_price}"
        )

"""Helpers for walking paginated endpoints."""

from __future__ import annotations

from typing import Any, Callable, Iterator, Protocol, TypeVar

__all__ = ["Paginated", "paginate"]

T = TypeVar("T", covariant=True)


class Paginated(Protocol[T]):
    """Minimal protocol implemented by all ``*Page`` models."""

    total: int
    offset: int

    @property
    def items(self) -> Any: ...


def paginate(
    fetch: Callable[[int, int], Paginated],
    *,
    page_size: int = 200,
    limit: int | None = None,
    start: int = 0,
) -> Iterator:
    """Yield items page by page until the response is exhausted or ``limit`` is reached."""

    if page_size <= 0:
        raise ValueError("page_size must be positive")
    if limit is not None and limit <= 0:
        return

    offset = start
    produced = 0
    while True:
        page = fetch(offset, page_size)
        items = list(page.items)
        if not items:
            return
        for item in items:
            yield item
            produced += 1
            if limit is not None and produced >= limit:
                return
        if page.total is not None and offset + len(items) >= page.total:
            return
        offset += len(items)

"""Тесты постраничного обхода."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from stalzone_api import paginate


@dataclass
class FakePage:
    total: int
    offset: int
    data: list[int]

    @property
    def items(self):
        return self.data


def test_paginate_walks_all_pages():
    pages = {
        0: FakePage(5, 0, [1, 2]),
        2: FakePage(5, 2, [3, 4]),
        4: FakePage(5, 4, [5]),
    }

    result = list(paginate(lambda offset, size: pages[offset], page_size=2))

    assert result == [1, 2, 3, 4, 5]


def test_paginate_respects_limit():
    pages = {
        0: FakePage(4, 0, [1, 2]),
        2: FakePage(4, 2, [3, 4]),
    }

    result = list(paginate(lambda offset, size: pages[offset], page_size=2, limit=3))

    assert result == [1, 2, 3]


def test_paginate_start_and_empty_page():
    calls: list[int] = []

    def fetch(offset, size):
        calls.append(offset)
        return FakePage(10, offset, [] if offset == 4 else [offset])

    assert list(paginate(fetch, page_size=2, start=4)) == []
    assert calls == [4]


def test_paginate_zero_limit_and_bad_page_size():
    assert list(paginate(lambda offset, size: FakePage(0, 0, []), limit=0)) == []

    with pytest.raises(ValueError):
        list(paginate(lambda offset, size: FakePage(0, 0, []), page_size=0))

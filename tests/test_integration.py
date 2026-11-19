"""Необязательные live-тесты реального API.

Запуск:

    $env:STALZONE_RUN_INTEGRATION="1"
    python -m pytest -m integration

Для production нужны STALZONE_APP_ID и STALZONE_APP_SECRET.
Без них проверяется только публичный demo-сервер.
"""

from __future__ import annotations

import os

import pytest

from stalzone_api import Client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("STALZONE_RUN_INTEGRATION") != "1",
        reason="live-тесты выключены; установите STALZONE_RUN_INTEGRATION=1",
    ),
]


def test_production_regions_and_operations():
    app_id = os.environ.get("STALZONE_APP_ID")
    app_secret = os.environ.get("STALZONE_APP_SECRET")
    if not app_id or not app_secret:
        pytest.skip("нет STALZONE_APP_ID/STALZONE_APP_SECRET")

    with Client(app_id=app_id, app_secret=app_secret, region="EU") as client:
        assert client.regions()
        assert client.emission().previous_start is not None
        assert client.clans.list(limit=1).total > 0
        assert client.operations.sessions(limit=1).total > 0


def test_demo_characters():
    with Client.demo(user=True, region="EU") as client:
        characters = client.characters.list()
        assert [character.name for character in characters] == ["Test-1", "Test-2", "Test-3"]
        assert client.friends("Test-1")

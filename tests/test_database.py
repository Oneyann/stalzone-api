"""Тесты базы предметов: локальный провайдер, индекс, поиск, иконки, GitHub."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from stalzone_api import (
    Database,
    DatabaseError,
    DatabaseNotFound,
    Formatted,
    GroupedBlock,
    ListBlock,
    NumericElement,
    Text,
)
from stalzone_api.database.cache import DiskCache
from stalzone_api.database.items import DamageBlock, RawBlock, TextBlock
from stalzone_api.database.providers import GitHubProvider, LocalProvider

ITEM = {
    "id": "abc",
    "category": "weapon/pistol",
    "name": {
        "type": "translation",
        "key": "item.abc",
        "args": {},
        "lines": {"ru": "Тестовый пистолет", "en": "Test Pistol"},
    },
    "color": "RANK_VETERAN",
    "status": {"state": "PERSONAL_ON_USE"},
    "infoBlocks": [
        {
            "type": "list",
            "title": {"type": "translation", "key": "common", "lines": {"ru": "Общее", "en": "Common"}},
            "elements": [
                {
                    "type": "numeric",
                    "name": {
                        "type": "translation",
                        "key": "core.tooltip.info.weight",
                        "lines": {"ru": "Вес", "en": "Weight"},
                    },
                    "value": 0.88,
                    "formatted": {"value": {"ru": "0,88 кг", "en": "0.88 kg"}},
                },
                {
                    "type": "key-value",
                    "key": {
                        "type": "translation",
                        "key": "weapon.tooltip.ammo",
                        "lines": {"ru": "Патроны", "en": "Ammo"},
                    },
                    "value": {
                        "type": "translation",
                        "key": "ammo.939",
                        "lines": {"ru": "9x39", "en": "9x39"},
                    },
                },
                {"type": "text", "text": {"type": "text", "text": "Просто текст"}},
            ],
        },
        {
            "type": "grouped",
            "compact": [
                {
                    "type": "list",
                    "elements": [
                        {
                            "type": "numeric",
                            "name": {
                                "type": "translation",
                                "key": "weapon.damage",
                                "lines": {"ru": "Урон", "en": "Damage"},
                            },
                            "value": 59.8,
                        }
                    ],
                }
            ],
            "detailed": [],
        },
        {
            "type": "damage",
            "startDamage": 59.8,
            "damageDecreaseStart": 20,
            "endDamage": 30,
            "damageDecreaseEnd": 80,
            "maxDistance": 100,
        },
        {
            "type": "text",
            "text": {
                "type": "translation",
                "key": "item.abc.description",
                "lines": {"ru": "Первая строка@Вторая строка", "en": "First@Second"},
            },
        },
        {"type": "mystery", "foo": "bar"},
    ],
}

VARIANT = {
    "id": "abc-v1",
    "category": "weapon/pistol",
    "name": {"type": "translation", "key": "item.abc.v1", "lines": {"ru": "Вариант", "en": "Variant"}},
    "color": "RANK_MASTER",
    "status": {"state": "PERSONAL_ON_USE"},
    "infoBlocks": [],
}

ARMOR = {
    "id": "def",
    "category": "armor/vest",
    "name": {"type": "translation", "key": "item.def", "lines": {"ru": "Броня", "en": "Armor"}},
    "color": "RANK_MASTER",
    "status": {"state": "PERSONAL_ON_USE"},
    "infoBlocks": [],
}

PNG = b"\x89PNG\r\n\x1a\nfake"


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def database_root(tmp_path: Path) -> Path:
    root = tmp_path / "db"
    write_json(root / "ru" / "items" / "weapon" / "pistol" / "abc.json", ITEM)
    write_json(root / "ru" / "items" / "weapon" / "pistol" / "_variants" / "abc" / "1.json", VARIANT)
    write_json(
        root / "ru" / "items" / "weapon" / "pistol" / "_variants" / "abc" / "2.json",
        {**VARIANT, "id": "abc-v2"},
    )
    write_json(root / "ru" / "items" / "armor" / "vest" / "def.json", ARMOR)
    icon = root / "ru" / "icons" / "weapon" / "pistol" / "ABC.png"
    icon.parent.mkdir(parents=True, exist_ok=True)
    icon.write_bytes(PNG)
    write_json(root / "global" / "items" / "armor" / "vest" / "ghi.json", {**ARMOR, "id": "ghi"})
    return root


def test_local_provider_and_item_parsing(database_root: Path):
    db = Database.local(database_root)

    assert db.realm == "ru"
    assert len(db.items) == 2
    assert db.items.categories() == ["armor", "weapon"]
    assert db.items.subcategories("weapon") == ["pistol"]
    assert db.items.ids() == ["abc", "def"]
    assert "abc" in db.items

    item = db.items.get("abc")
    assert item.name.ru == "Тестовый пистолет"
    assert item.name.en == "Test Pistol"
    assert item.name.get("de") == "Test Pistol"
    assert item.color == "RANK_VETERAN"
    assert item.status.state == "PERSONAL_ON_USE"
    assert item.category_type == "weapon"
    assert item.category_subtype == "pistol"

    assert item.weight == 0.88
    assert item.stats["weapon.damage"] == 59.8
    assert item.stats["weapon.tooltip.ammo"].get("ru") == "9x39"
    assert item.stat("core.tooltip.info.weight") == 0.88
    assert isinstance(item.find("core.tooltip.info.weight"), NumericElement)
    assert isinstance(item.find("core.tooltip.info.weight"), object)

    assert isinstance(item.damage, DamageBlock)
    assert item.damage.start_damage == 59.8
    assert item.damage.max_distance == 100

    assert isinstance(item.description, Text)
    assert item.description.get("ru") == "Первая строка\nВторая строка"
    assert item.description.get("en", line_breaks=False) == "First@Second"

    assert any(isinstance(block, GroupedBlock) for block in item.info_blocks)
    assert any(isinstance(block, RawBlock) and block.type == "mystery" for block in item.info_blocks)
    assert item.extra == {}
    assert item.to_dict()["id"] == "abc"


def test_formatted_values(database_root: Path):
    item = Database.local(database_root).items.get("abc")
    elements = [element for block in item.info_blocks if isinstance(block, ListBlock) for element in block.elements]

    assert isinstance(elements[0].formatted, Formatted)
    assert elements[0].formatted.get("ru") == "0,88 кг"


def test_variants_and_iteration(database_root: Path):
    db = Database.local(database_root)

    variants = db.items.variants("abc")
    assert [variant.id for variant in variants] == ["abc-v1", "abc-v2"]
    assert variants[0].name.en == "Variant"

    all_items = list(db.items.all("weapon/pistol"))
    assert [item.id for item in all_items] == ["abc"]
    assert len(list(db.items)) == 2


def test_search(database_root: Path):
    db = Database.local(database_root)

    assert [item.id for item in db.items.search("тестовый", lang="ru")] == ["abc"]
    assert [item.id for item in db.items.search("test", lang="en")] == ["abc"]
    assert [item.id for item in db.items.search("pistol", lang="en")] == ["abc"]
    assert db.items.search("   ") == []
    assert [item.id for item in db.items.search("вариант", lang="ru", include_variants=True)] == [
        "abc-v1",
        "abc-v2",
    ]


def test_item_not_found(database_root: Path):
    db = Database.local(database_root)

    with pytest.raises(DatabaseNotFound):
        db.items.get("missing")
    with pytest.raises(DatabaseNotFound):
        db.icons.bytes("missing")


def test_icons(database_root: Path, tmp_path: Path):
    db = Database.local(database_root)

    assert db.icons.path("abc") == "icons/weapon/pistol/ABC.png"
    assert db.icons.url("abc").startswith("file://")
    assert db.icons.bytes("abc") == PNG

    saved = db.icons.save("abc", tmp_path / "icons")
    assert saved.name == "ABC.png"
    assert saved.read_bytes() == PNG
    assert db.icons.save("abc", tmp_path / "icons") == saved

    assert db.icons.download_all(tmp_path / "all", categories=["weapon"]) == 1
    assert db.icons.download_all(tmp_path / "all", categories=["weapon"]) == 0
    assert (tmp_path / "all" / "icons" / "weapon" / "pistol" / "ABC.png").exists()


def test_name_index_cache(database_root: Path, tmp_path: Path):
    cache_dir = tmp_path / "cache"
    db = Database.local(database_root, cache_dir=cache_dir)
    assert db.build_index() == 2

    files = list(cache_dir.glob("*.json"))
    assert files

    second = Database.local(database_root, cache_dir=cache_dir)
    assert second.build_index() == 2


def test_global_realm(database_root: Path):
    db = Database.local(database_root, realm="global")

    assert db.realm == "global"
    assert [item.id for item in db.items] == ["ghi"]


def test_invalid_local_directory(tmp_path: Path):
    with pytest.raises(DatabaseError, match="stalzone-database"):
        Database.local(tmp_path / "empty")


def test_formatted_and_text_edge_cases():
    assert Text.from_dict("plain").get() == "plain"
    assert Text.from_dict({"text": "raw"}).get() == "raw"
    assert Text.from_dict(None) is None
    text = Text.from_dict({"lines": {"ru": "a@b"}})
    assert text.get("ru") == "a\nb"
    assert text.get("en") == "a\nb"
    assert text.format() == "a\nb"
    assert Formatted.from_dict(None) is None
    assert Text.from_dict({"lines": {}}).get() is None


def test_github_provider(router, tmp_path: Path):
    tree = {
        "tree": [
            {"path": "ru/items/weapon/pistol/abc.json", "type": "blob"},
            {"path": "ru/items/weapon/pistol/_variants/abc/1.json", "type": "blob"},
            {"path": "ru/icons/weapon/pistol/ABC.png", "type": "blob"},
            {"path": "README.md", "type": "blob"},
            {"path": "ru/items/weapon", "type": "tree"},
        ]
    }
    router.add("/repos/owner/repo/git/trees/main", tree)
    router.add("/owner/repo/main/ru/items/weapon/pistol/abc.json", ITEM)
    router.add(
        "/owner/repo/main/ru/icons/weapon/pistol/ABC.png",
        response=httpx.Response(200, content=PNG),
    )

    http = httpx.Client(transport=httpx.MockTransport(router))
    provider = GitHubProvider(
        "ru",
        repo="owner/repo",
        ref="main",
        cache=DiskCache(tmp_path / "cache"),
        client=http,
    )
    try:
        assert provider.list_item_paths() == [
            "items/weapon/pistol/_variants/abc/1.json",
            "items/weapon/pistol/abc.json",
        ]
        assert provider.list_icon_paths() == ["icons/weapon/pistol/ABC.png"]
        assert provider.read_json("items/weapon/pistol/abc.json")["id"] == "abc"
        assert provider.read_bytes("icons/weapon/pistol/ABC.png") == PNG
        assert provider.read_bytes("icons/weapon/pistol/ABC.png") == PNG

        requests_before = len(router.requests)
        assert provider.read_json("items/weapon/pistol/abc.json")["id"] == "abc"
        assert len(router.requests) == requests_before
        assert provider.url("icons/weapon/pistol/ABC.png").startswith("https://raw.githubusercontent.com/")
    finally:
        provider.close()
        http.close()

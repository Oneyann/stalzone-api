"""Index of item and icon paths (id → file, category → files)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..errors import DatabaseError
from .providers import Provider

__all__ = ["ItemIndex", "build_index"]

_VARIANT_DIR = "_variants"


def _split_variant(path: str) -> tuple[str, str, int] | None:
    parts = path.split("/")
    if _VARIANT_DIR not in parts:
        return None
    index = parts.index(_VARIANT_DIR)
    if index + 2 >= len(parts):
        return None
    category = "/".join(parts[1:index]) if parts[:1] == ["items"] else "/".join(parts[:index])
    variant_id = parts[index + 1]
    stem = parts[-1].rsplit(".", 1)[0]
    try:
        number = int(stem)
    except ValueError:
        number = 0
    return category, variant_id, number


def _split_item(path: str) -> tuple[str, str]:
    parts = path.split("/")
    if parts[:1] == ["items"]:
        parts = parts[1:]
    category = "/".join(parts[:-1])
    item_id = parts[-1].rsplit(".", 1)[0]
    return category, item_id


@dataclass
class ItemIndex:
    """Pre-computed lookup tables for one realm."""

    item_paths: list[str] = field(default_factory=list)
    main_paths: list[str] = field(default_factory=list)
    icon_paths: list[str] = field(default_factory=list)
    by_id: dict[str, list[str]] = field(default_factory=dict)
    by_category: dict[str, list[str]] = field(default_factory=dict)
    variants: dict[str, list[tuple[int, str]]] = field(default_factory=dict)
    icons: dict[str, str] = field(default_factory=dict)
    lower_ids: dict[str, str] = field(default_factory=dict)
    categories: list[str] = field(default_factory=list)
    icon_categories: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ helpers
    def locate(self, item_id: str) -> list[str]:
        paths = self.by_id.get(item_id)
        if paths:
            return paths
        canonical = self.lower_ids.get(item_id.casefold())
        if canonical is not None:
            return self.by_id.get(canonical, [])
        return []

    def category_paths(self, category: str | None = None) -> list[str]:
        if category is None:
            return self.main_paths
        normalized = category.strip("/")
        if not normalized:
            return self.main_paths
        prefix = f"items/{normalized}/"
        return [path for path in self.main_paths if path.startswith(prefix)]

    def subcategories(self, category: str) -> list[str]:
        normalized = category.strip("/")
        prefix = f"items/{normalized}/"
        result = set()
        for path in self.item_paths:
            if path.startswith(prefix):
                remainder = path[len(prefix) :]
                parts = remainder.split("/")
                if len(parts) > 1 and parts[0] != _VARIANT_DIR:
                    result.add(parts[0])
        return sorted(result)

    def icon_for(self, item_id: str) -> str | None:
        direct = self.icons.get(item_id.casefold())
        if direct:
            return direct
        # Some icons use a different case; retry with the canonical id casing.
        paths = self.locate(item_id)
        if paths:
            _, canonical = _split_item(paths[0])
            return self.icons.get(canonical.casefold())
        return None

    def __len__(self) -> int:
        return len(self.by_id)


def build_index(provider: Provider) -> ItemIndex:
    """Build the lookup tables from the provider's path listings."""

    item_paths = provider.list_item_paths()
    icon_paths = provider.list_icon_paths()
    index = ItemIndex(item_paths=item_paths, icon_paths=icon_paths)

    for path in item_paths:
        variant = _split_variant(path)
        if variant is not None:
            category, variant_id, number = variant
            index.variants.setdefault(variant_id, []).append((number, path))
            continue
        category, item_id = _split_item(path)
        if not item_id:
            raise DatabaseError(f"unexpected item path: {path}")
        index.by_id.setdefault(item_id, []).append(path)
        index.by_category.setdefault(category, []).append(path)
        index.lower_ids.setdefault(item_id.casefold(), item_id)

    for variant_id, entries in index.variants.items():
        entries.sort(key=lambda pair: pair[0])

    index.main_paths = sorted(path for group in index.by_category.values() for path in group)
    index.categories = sorted({category.split("/", 1)[0] for category in index.by_category})
    index.icon_categories = sorted(
        {path.split("/")[1] for path in icon_paths if path.count("/") >= 2}
    )

    for path in icon_paths:
        stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        index.icons.setdefault(stem.casefold(), path)

    return index

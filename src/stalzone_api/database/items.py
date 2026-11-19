"""Typed representation of the items database (JSON files from stalzone-database)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

from ..errors import DatabaseError, DatabaseNotFound
from .index import ItemIndex, build_index
from .providers import Provider

__all__ = [
    "Block",
    "DamageBlock",
    "Element",
    "Formatted",
    "GroupedBlock",
    "Item",
    "ItemElement",
    "ItemStatus",
    "ItemStore",
    "KeyValueElement",
    "ListBlock",
    "NumericElement",
    "PriceElement",
    "RangeElement",
    "RawBlock",
    "RawElement",
    "Text",
    "TextBlock",
    "TextElement",
]

_LANG_FALLBACK = "en"
_WEIGHT_KEY = "core.tooltip.info.weight"


# ------------------------------------------------------------------------ texts
@dataclass(frozen=True)
class Text:
    """A localizable string from the item database."""

    type: str = "text"
    key: str | None = None
    args: dict[str, str] = field(default_factory=dict)
    lines: dict[str, str] = field(default_factory=dict)
    text: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> "Text | None":
        if data is None:
            return None
        if isinstance(data, str):
            return cls(text=data)
        if not isinstance(data, dict):
            return cls(text=str(data))
        lines = data.get("lines")
        args = data.get("args")
        return cls(
            type=str(data.get("type") or ("translation" if lines else "text")),
            key=data.get("key"),
            args={str(k): str(v) for k, v in args.items()} if isinstance(args, dict) else {},
            lines={str(k): str(v) for k, v in lines.items()} if isinstance(lines, dict) else {},
            text=data.get("text"),
        )

    def get(
        self,
        lang: str = _LANG_FALLBACK,
        *,
        default: str = _LANG_FALLBACK,
        line_breaks: bool = True,
    ) -> str | None:
        """Return the translation for ``lang``, falling back to English/the first locale."""

        value: str | None
        if self.lines:
            value = self.lines.get(lang) or self.lines.get(default)
            if value is None and self.lines:
                value = next(iter(self.lines.values()))
        else:
            value = self.text
        if value is None:
            return None
        return value.replace("@", "\n") if line_breaks else value

    @property
    def ru(self) -> str | None:
        return self.get("ru")

    @property
    def en(self) -> str | None:
        return self.get("en")

    def format(self, **kwargs: Any) -> str | None:
        """Substitute placeholders (if any) into the translated line."""

        value = self.get()
        if value is None or not kwargs:
            return value
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return value

    def __str__(self) -> str:
        return self.get() or ""


@dataclass(frozen=True)
class Formatted:
    """Pre-rendered value with colors, e.g. ``formatted.value.ru``."""

    value: dict[str, str] = field(default_factory=dict)
    name_color: str | None = None
    value_color: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> "Formatted | None":
        if not isinstance(data, dict):
            return None
        values = data.get("value")
        return cls(
            value={str(k): str(v) for k, v in values.items()} if isinstance(values, dict) else {},
            name_color=data.get("nameColor"),
            value_color=data.get("valueColor"),
        )

    def get(self, lang: str = _LANG_FALLBACK, *, default: str = _LANG_FALLBACK) -> str | None:
        if not self.value:
            return None
        return self.value.get(lang) or self.value.get(default) or next(iter(self.value.values()))


# --------------------------------------------------------------------- elements
@dataclass
class Element:
    type: str = ""
    formatted: Formatted | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class NumericElement(Element):
    name: Text | None = None
    value: float | None = None


@dataclass
class KeyValueElement(Element):
    key: Text | None = None
    value: Text | None = None


@dataclass
class RangeElement(Element):
    name: Text | None = None
    min: float | None = None
    max: float | None = None


@dataclass
class TextElement(Element):
    text: Text | None = None


@dataclass
class PriceElement(Element):
    currency: str | None = None
    amount: float | None = None


@dataclass
class ItemElement(Element):
    name: Text | None = None


@dataclass
class RawElement(Element):
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


# ----------------------------------------------------------------------- blocks
@dataclass
class Block:
    type: str = ""
    title: Text | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class TextBlock(Block):
    text: Text | None = None


@dataclass
class ListBlock(Block):
    elements: list[Element] = field(default_factory=list)


@dataclass
class DamageBlock(Block):
    start_damage: float | None = None
    damage_decrease_start: float | None = None
    end_damage: float | None = None
    damage_decrease_end: float | None = None
    max_distance: float | None = None


@dataclass
class GroupedBlock(Block):
    compact: list[Block] = field(default_factory=list)
    detailed: list[Block] = field(default_factory=list)


@dataclass
class RawBlock(Block):
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


_BLOCK_KEYS = {"type", "title"}
_ELEMENT_KEYS = {"type", "formatted"}


def parse_element(data: dict[str, Any]) -> Element:
    kind = str(data.get("type") or "")
    formatted = Formatted.from_dict(data.get("formatted"))
    extra = {k: v for k, v in data.items() if k not in _ELEMENT_KEYS}
    if kind == "numeric":
        return NumericElement(
            type=kind,
            formatted=formatted,
            extra=extra,
            name=Text.from_dict(data.get("name")),
            value=data.get("value"),
        )
    if kind == "key-value":
        return KeyValueElement(
            type=kind,
            formatted=formatted,
            extra=extra,
            key=Text.from_dict(data.get("key")),
            value=Text.from_dict(data.get("value")),
        )
    if kind == "range":
        return RangeElement(
            type=kind,
            formatted=formatted,
            extra=extra,
            name=Text.from_dict(data.get("name")),
            min=data.get("min"),
            max=data.get("max"),
        )
    if kind == "text":
        return TextElement(type=kind, formatted=formatted, extra=extra, text=Text.from_dict(data.get("text")))
    if kind == "price":
        return PriceElement(
            type=kind,
            formatted=formatted,
            extra=extra,
            currency=data.get("currency"),
            amount=data.get("amount"),
        )
    if kind == "item":
        return ItemElement(type=kind, formatted=formatted, extra=extra, name=Text.from_dict(data.get("name")))
    return RawElement(type=kind, formatted=formatted, extra=extra, raw=dict(data))


def parse_block(data: dict[str, Any]) -> Block:
    kind = str(data.get("type") or "")
    title = Text.from_dict(data.get("title"))
    base_extra = {k: v for k, v in data.items() if k not in ("type", "title", "text", "elements")}
    if kind == "text":
        return TextBlock(type=kind, title=title, extra=base_extra, text=Text.from_dict(data.get("text")))
    if kind == "list":
        elements = [parse_element(entry) for entry in data.get("elements") or [] if isinstance(entry, dict)]
        return ListBlock(type=kind, title=title, extra=base_extra, elements=elements)
    if kind == "grouped":
        return GroupedBlock(
            type=kind,
            title=title,
            extra=base_extra,
            compact=[
                parse_block(entry)
                for entry in data.get("compact") or []
                if isinstance(entry, dict)
            ],
            detailed=[
                parse_block(entry)
                for entry in data.get("detailed") or []
                if isinstance(entry, dict)
            ],
        )
    if kind in ("damage", "damage_ramp"):
        return DamageBlock(
            type=kind,
            title=title,
            extra=base_extra,
            start_damage=data.get("startDamage"),
            damage_decrease_start=data.get("damageDecreaseStart"),
            end_damage=data.get("endDamage"),
            damage_decrease_end=data.get("damageDecreaseEnd"),
            max_distance=data.get("maxDistance"),
        )
    return RawBlock(type=kind, title=title, extra=base_extra, raw=dict(data))


# ------------------------------------------------------------------------- item
@dataclass
class ItemStatus:
    state: str | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Any) -> "ItemStatus | None":
        if not isinstance(data, dict):
            return None
        return cls(state=data.get("state"), extra={k: v for k, v in data.items() if k != "state"})


def _text_key(text: Text | None) -> str | None:
    if text is None:
        return None
    return text.key or text.get(line_breaks=False)


def _iter_elements(blocks: list[Block]) -> Iterator[Element]:
    for block in blocks:
        if isinstance(block, ListBlock):
            yield from block.elements
        elif isinstance(block, GroupedBlock):
            yield from _iter_elements(block.compact)
            yield from _iter_elements(block.detailed)


def _iter_blocks(blocks: list[Block]) -> Iterator[Block]:
    for block in blocks:
        yield block
        if isinstance(block, GroupedBlock):
            yield from _iter_blocks(block.compact)
            yield from _iter_blocks(block.detailed)


@dataclass
class Item:
    """An in-game item from the official database."""

    id: str
    category: str
    name: Text = field(default_factory=Text)
    color: str | None = None
    status: ItemStatus | None = None
    info_blocks: list[Block] = field(default_factory=list)
    path: str | None = None
    realm: str | None = None
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        path: str | None = None,
        realm: str | None = None,
    ) -> "Item":
        known = {"id", "category", "name", "color", "status", "infoBlocks"}
        return cls(
            id=str(data.get("id", "")),
            category=str(data.get("category", "")),
            name=Text.from_dict(data.get("name")) or Text(),
            color=data.get("color"),
            status=ItemStatus.from_dict(data.get("status")),
            info_blocks=[parse_block(entry) for entry in data.get("infoBlocks") or [] if isinstance(entry, dict)],
            path=path,
            realm=realm,
            extra={k: v for k, v in data.items() if k not in known},
        )

    # ------------------------------------------------------------------ category
    @property
    def category_type(self) -> str:
        return self.category.split("/", 1)[0]

    @property
    def category_subtype(self) -> str | None:
        parts = self.category.split("/", 1)
        return parts[1] if len(parts) > 1 else None

    @property
    def type(self) -> str:
        return self.category_type

    @property
    def subtype(self) -> str | None:
        return self.category_subtype

    # -------------------------------------------------------------- convenience
    @property
    def blocks(self) -> list[Block]:
        return self.info_blocks

    def blocks_of(self, kind: str) -> list[Block]:
        return [block for block in self.info_blocks if block.type == kind]

    @property
    def stats(self) -> dict[str, Any]:
        """Flatten every element of every list block into a ``key → value`` mapping."""

        result: dict[str, Any] = {}
        for element in _iter_elements(self.info_blocks):
            if isinstance(element, NumericElement):
                key = _text_key(element.name)
                if key:
                    result[key] = element.value
            elif isinstance(element, RangeElement):
                key = _text_key(element.name)
                if key:
                    result[key] = (element.min, element.max)
            elif isinstance(element, KeyValueElement):
                key = _text_key(element.key)
                if key:
                    result[key] = element.value
            elif isinstance(element, TextElement) and element.text is not None:
                key = _text_key(element.text)
                if key:
                    result[key] = element.text
            elif isinstance(element, PriceElement):
                result[f"price:{element.currency}"] = element.amount
        return result

    def stat(self, key: str, default: Any = None) -> Any:
        return self.stats.get(key, default)

    def find(self, key: str) -> Block | Element | None:
        """Find a block or element by its translation key (e.g. ``core.tooltip.info.weight``)."""

        for block in _iter_blocks(self.info_blocks):
            if _text_key(block.title) == key:
                return block
            if isinstance(block, TextBlock) and _text_key(block.text) == key:
                return block
            if isinstance(block, ListBlock):
                for element in block.elements:
                    candidates = [
                        getattr(element, "name", None),
                        getattr(element, "key", None),
                        getattr(element, "text", None),
                    ]
                    if isinstance(element, KeyValueElement):
                        candidates.append(element.value)
                    for candidate in candidates:
                        if isinstance(candidate, Text) and candidate.key == key:
                            return element
        return None

    @property
    def weight(self) -> float | None:
        """Item weight in kilograms, if present."""

        element = self.find(_WEIGHT_KEY)
        if isinstance(element, NumericElement):
            return element.value
        for candidate in _iter_elements(self.info_blocks):
            if isinstance(candidate, NumericElement) and candidate.name is not None:
                if (candidate.name.en or "").strip().casefold() == "weight":
                    return candidate.value
        return None

    @property
    def damage(self) -> DamageBlock | None:
        """Damage ramp of a weapon, if present."""

        for block in self.info_blocks:
            if isinstance(block, DamageBlock):
                return block
        return None

    @property
    def description(self) -> Text | None:
        for block in self.info_blocks:
            if isinstance(block, TextBlock) and block.text is not None:
                if (block.text.key or "").endswith(".description"):
                    return block.text
        for block in self.info_blocks:
            if isinstance(block, TextBlock) and block.text is not None:
                return block.text
        return None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        return self.name.get() or self.id


# ------------------------------------------------------------------------ store
ProgressCallback = Callable[[str, int, int], Any]


class ItemStore:
    """Access to items of one realm (``db.items``)."""

    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        self._index: ItemIndex | None = None
        self._names: dict[str, dict[str, Any]] | None = None
        self._names_variants: dict[str, dict[str, Any]] | None = None

    # --------------------------------------------------------------------- index
    @property
    def index(self) -> ItemIndex:
        if self._index is None:
            self._index = build_index(self.provider)
        return self._index

    def ids(self) -> list[str]:
        """All item ids in the realm (sorted)."""

        return sorted(self.index.by_id)

    def categories(self) -> list[str]:
        """Top-level categories (``weapon``, ``armor``, ``artefact``, ...)."""

        return list(self.index.categories)

    def subcategories(self, category: str) -> list[str]:
        return self.index.subcategories(category)

    # ---------------------------------------------------------------------- read
    def get(self, item_id: str) -> Item:
        """Load an item by id; raises :class:`DatabaseNotFound` when it is absent."""

        paths = self.index.locate(item_id)
        if not paths:
            raise DatabaseNotFound(f"item {item_id!r} not found in realm {self.provider.realm!r}")
        return self._load(paths[0])

    def get_all(self, item_id: str) -> list[Item]:
        """Load every item sharing the same id (ids are not guaranteed to be unique)."""

        return [self._load(path) for path in self.index.locate(item_id)]

    def variants(self, item_id: str) -> list[Item]:
        """Load the ``_variants/<id>/*.json`` list of an item."""

        entries = self.index.variants.get(item_id)
        if not entries:
            canonical = self.index.lower_ids.get(item_id.casefold())
            entries = self.index.variants.get(canonical, []) if canonical else []
        return [self._load(path) for _number, path in entries]

    def all(self, category: str | None = None) -> Iterator[Item]:
        """Iterate over every item (optionally inside a category, e.g. ``"weapon/pistol"``)."""

        for path in self.index.category_paths(category):
            yield self._load(path)

    def _load(self, path: str) -> Item:
        data = self.provider.read_json(path)
        return Item.from_dict(data, path=path, realm=self.provider.realm)

    def __iter__(self) -> Iterator[Item]:
        return self.all()

    def __len__(self) -> int:
        return len(self.index.by_id)

    def __contains__(self, item_id: object) -> bool:
        return isinstance(item_id, str) and bool(self.index.locate(item_id))

    # -------------------------------------------------------------------- search
    def _name_cache_key(self, include_variants: bool) -> str:
        suffix = ":variants" if include_variants else ""
        return f"name_index:{self.provider.namespace}{suffix}"

    def _load_names(self, include_variants: bool = False) -> dict[str, dict[str, Any]] | None:
        if self._names is not None and not include_variants:
            return self._names
        cached_names = self._names_variants
        if include_variants and cached_names is not None:
            return cached_names
        cache = self.provider.cache
        if cache is not None:
            value, _etag, _fresh = cache.get_json(self._name_cache_key(include_variants), allow_stale=True)
            if isinstance(value, dict) and isinstance(value.get("items"), dict):
                if include_variants:
                    self._names_variants = value["items"]
                else:
                    self._names = value["items"]
                return value["items"]
        return None

    def build_name_index(
        self,
        *,
        include_variants: bool = False,
        progress: ProgressCallback | None = None,
        force: bool = False,
    ) -> int:
        """Download every item name and cache it; required by :meth:`search`.

        By default only regular items are indexed; pass ``include_variants=True``
        to include ``_variants/*.json`` entries as well.
        """

        if not force:
            existing = self._load_names(include_variants)
            if existing is not None:
                return len(existing)

        if include_variants:
            paths = list(self.index.item_paths)
        else:
            paths = list(self.index.main_paths)
        paths.sort()
        total = len(paths)
        entries: dict[str, dict[str, Any]] = {}
        for done, path in enumerate(paths, start=1):
            data = self.provider.read_json(path)
            name = data.get("name")
            names: dict[str, str] = {}
            if isinstance(name, dict):
                lines = name.get("lines")
                if isinstance(lines, dict):
                    names = {str(lang): str(value) for lang, value in lines.items()}
                elif name.get("text"):
                    names = {"en": str(name["text"])}
            entries[path] = {"id": str(data.get("id") or Path(path).stem), "names": names}
            if progress is not None:
                progress(path, done, total)

        if include_variants:
            self._names_variants = entries
        else:
            self._names = entries
        cache = self.provider.cache
        if cache is not None:
            cache.set_json(self._name_cache_key(include_variants), {"items": entries})
        return len(entries)

    def search(
        self,
        query: str,
        *,
        lang: str = "en",
        limit: int | None = 50,
        include_variants: bool = False,
    ) -> list[Item]:
        """Search items by (part of) their localized name.

        Regular items are searched by default. For the GitHub provider the name index
        must be built first (:meth:`build_name_index`); local checkouts build it
        automatically.
        """

        needle = query.strip().casefold()
        if not needle:
            return []
        entries = self._load_names(include_variants)
        if entries is None:
            if not self.provider.is_bulk:
                raise DatabaseError(
                    "the name index is not built yet; call build_name_index() once "
                    "(or use Database.local()/Database.sync() for offline search)"
                )
            self.build_name_index(include_variants=include_variants)
            entries = self._load_names(include_variants) or {}

        ranked: list[tuple[int, str, str]] = []
        for path, info in entries.items():
            names = info.get("names") or {}
            value = names.get(lang) or names.get(_LANG_FALLBACK)
            if value is None and names:
                value = next(iter(names.values()))
            if not value:
                continue
            folded = str(value).casefold()
            if folded == needle:
                score = 0
            elif folded.startswith(needle):
                score = 1
            elif needle in folded:
                score = 2
            else:
                continue
            ranked.append((score, folded, path))

        ranked.sort()
        if limit is not None:
            ranked = ranked[:limit]
        return [self._load(path) for _score, _name, path in ranked]

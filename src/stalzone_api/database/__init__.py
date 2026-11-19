"""Access to the official Stalcraft items database (``EXBO-Studio/stalzone-database``).

```python
from stalzone_api import Database, Realm

db = Database(Realm.RU)                 # fetch items from GitHub on demand
db = Database.local("./stalzone-database")  # use a local clone

item = db.items.get("0r2qk")
print(item.name.ru, item.weight)
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..constants import (
    DATABASE_REF,
    DEFAULT_DATABASE_TIMEOUT,
)
from ..errors import DatabaseError
from ..models.common import Realm
from .cache import DiskCache, default_cache_dir
from .icons import IconStore
from .items import (
    Block,
    DamageBlock,
    Element,
    Formatted,
    GroupedBlock,
    Item,
    ItemElement,    ItemStatus,
    ItemStore,
    KeyValueElement,
    ListBlock,
    NumericElement,
    PriceElement,
    RangeElement,
    RawBlock,
    RawElement,
    Text,
    TextBlock,
    TextElement,
)
from .providers import GitHubProvider, LocalProvider, Provider

__all__ = [
    "Block",
    "DamageBlock",
    "Database",
    "Element",
    "Formatted",
    "GitHubProvider",
    "GroupedBlock",
    "IconStore",
    "Item",
    "ItemElement",
    "ItemStatus",
    "ItemStore",
    "KeyValueElement",
    "ListBlock",
    "LocalProvider",
    "NumericElement",
    "PriceElement",
    "Provider",
    "RangeElement",
    "RawBlock",
    "RawElement",
    "Text",
    "TextBlock",
    "TextElement",
    "default_cache_dir",
]


class Database:
    """Facade over one realm of the items database."""

    def __init__(
        self,
        realm: str | Realm = Realm.RU,
        *,
        provider: Provider | None = None,
        cache_dir: str | Path | None = None,
        ref: str = DATABASE_REF,
        github_token: str | None = None,
        timeout: float = DEFAULT_DATABASE_TIMEOUT,
        user_agent: str | None = None,
    ) -> None:
        self.realm = str(Realm(realm))
        if provider is None:
            cache = DiskCache(cache_dir) if cache_dir else DiskCache()
            provider = GitHubProvider(
                self.realm,
                ref=ref,
                token=github_token,
                cache=cache,
                timeout=timeout,
                user_agent=user_agent,
            )
        elif provider.cache is None and cache_dir is not None:
            provider.cache = DiskCache(cache_dir)

        self._provider = provider
        self.items = ItemStore(provider)
        self.icons = IconStore(provider, self.items)

    # -------------------------------------------------------------------- factories
    @classmethod
    def local(
        cls,
        path: str | Path,
        realm: str | Realm | None = None,
        *,
        cache_dir: str | Path | None = None,
    ) -> "Database":
        """Use a local clone (or an unpacked snapshot) of the repository."""

        provider = LocalProvider(path, realm=realm, cache=DiskCache(cache_dir) if cache_dir else None)
        return cls(provider.realm, provider=provider)

    def sync(
        self,
        dest: str | Path | None = None,
        *,
        force: bool = False,
    ) -> "Database":
        """Download the repository zipball once and return a database backed by it.

        This is the fastest way to get a fully offline copy: one HTTP request instead
        of thousands of raw-file requests. Icons are included in the archive.
        """

        if not isinstance(self._provider, GitHubProvider):
            raise DatabaseError("sync() is only available for the GitHub provider")
        root = self._provider.download_archive(dest, force=force)
        return Database.local(root, realm=self.realm, cache_dir=self._provider.cache.directory if self._provider.cache else None)

    # ------------------------------------------------------------------------ info
    @property
    def provider(self) -> Provider:
        return self._provider

    @property
    def cache_dir(self) -> Path | None:
        return self._provider.cache.directory if self._provider.cache else None

    def build_index(self, *, progress: Any = None, force: bool = False) -> int:
        """Build the name index used by :meth:`ItemStore.search`."""

        return self.items.build_name_index(progress=progress, force=force)

    def close(self) -> None:
        self._provider.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"Database(realm={self.realm!r}, provider={type(self._provider).__name__})"

"""Item icons: URLs, downloading and local caching."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from ..errors import DatabaseNotFound
from .items import ItemStore
from .providers import Provider

__all__ = ["IconStore"]

ProgressCallback = Callable[[str, int, int], Any]


class IconStore:
    """Access to the PNG icons of one realm (``db.icons``)."""

    def __init__(self, provider: Provider, items: ItemStore) -> None:
        self.provider = provider
        self._items = items

    def path(self, item_id: str) -> str | None:
        """Realm-relative icon path (``icons/weapon/pistol/0n9q.png``)."""

        return self._items.index.icon_for(item_id)

    def url(self, item_id: str) -> str | None:
        """Public URL of the icon (``None`` if the source has no URL)."""

        path = self.path(item_id)
        return self.provider.url(path) if path else None

    def bytes(self, item_id: str) -> bytes:
        """Raw PNG bytes of the icon."""

        path = self.path(item_id)
        if path is None:
            raise DatabaseNotFound(f"icon for item {item_id!r} not found")
        return self.provider.read_bytes(path)

    def save(self, item_id: str, dest: str | Path, *, overwrite: bool = False) -> Path:
        """Save a single icon into ``dest`` (kept under its original file name)."""

        path = self.path(item_id)
        if path is None:
            raise DatabaseNotFound(f"icon for item {item_id!r} not found")
        target_dir = Path(dest)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / Path(path).name
        if target.exists() and not overwrite:
            return target
        target.write_bytes(self.provider.read_bytes(path))
        return target

    def download_all(
        self,
        dest: str | Path,
        *,
        categories: Iterable[str] | None = None,
        overwrite: bool = False,
        progress: ProgressCallback | None = None,
    ) -> int:
        """Download every icon (or the given categories) preserving folder structure."""

        destination = Path(dest)
        prefixes = None
        if categories is not None:
            prefixes = tuple(f"icons/{category.strip('/')}/" for category in categories)

        paths = [
            path
            for path in self._items.index.icon_paths
            if prefixes is None or path.startswith(prefixes)
        ]
        total = len(paths)
        saved = 0
        for done, path in enumerate(paths, start=1):
            target = destination / path
            if target.exists() and not overwrite:
                if progress is not None:
                    progress(path, done, total)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.provider.read_bytes(path))
            saved += 1
            if progress is not None:
                progress(path, done, total)
        return saved

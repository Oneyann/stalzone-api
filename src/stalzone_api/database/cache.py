"""Small on-disk cache used by the items database providers."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

__all__ = ["DiskCache", "default_cache_dir"]


def default_cache_dir() -> Path:
    """Return the platform-specific cache directory (``STALZONE_CACHE_DIR`` overrides it)."""

    override = os.environ.get("STALZONE_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "stalzone-api"


class DiskCache:
    """Tiny JSON/bytes cache with TTL and ETag support.

    Every entry is stored as a payload file plus a ``.meta`` sidecar. Writes are
    atomic, so concurrent processes cannot read half-written data.
    """

    def __init__(self, directory: str | os.PathLike[str] | None = None, ttl: float = 12 * 3600) -> None:
        self.directory = Path(directory).expanduser() if directory else default_cache_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.ttl = float(ttl)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ internals
    def _paths(self, key: str) -> tuple[Path, Path]:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.meta", self.directory / digest

    def _read_meta(self, key: str) -> dict[str, Any] | None:
        meta_path, _ = self._paths(key)
        try:
            with meta_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def _write_atomic(self, path: Path, data: bytes) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as fh:
            fh.write(data)
        tmp.replace(path)

    def _read_payload(self, key: str, suffix: str) -> bytes | None:
        _, base = self._paths(key)
        path = base.with_suffix(suffix)
        try:
            return path.read_bytes()
        except OSError:
            return None

    def _age(self, meta: dict[str, Any]) -> float:
        try:
            return time.time() - float(meta.get("cached_at") or 0)
        except (TypeError, ValueError):
            return float("inf")

    # --------------------------------------------------------------------- public
    def get_json(
        self,
        key: str,
        *,
        allow_stale: bool = False,
        ttl: float | None = None,
    ) -> tuple[Any | None, str | None, bool]:
        """Return ``(value, etag, fresh)``; ``value`` is ``None`` when absent."""

        meta = self._read_meta(key)
        if meta is None:
            return None, None, False
        payload = self._read_payload(key, ".json")
        if payload is None:
            return None, None, False
        try:
            value = json.loads(payload)
        except ValueError:
            return None, meta.get("etag"), False
        fresh = self._age(meta) <= (self.ttl if ttl is None else ttl)
        if not fresh and not allow_stale:
            return None, meta.get("etag"), False
        return value, meta.get("etag"), fresh

    def set_json(self, key: str, value: Any, etag: str | None = None) -> None:
        meta_path, base = self._paths(key)
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        with self._lock:
            self._write_atomic(base.with_suffix(".json"), data)
            meta = {"key": key, "cached_at": time.time(), "etag": etag}
            self._write_atomic(meta_path, json.dumps(meta).encode("utf-8"))

    def get_bytes(self, key: str, *, ttl: float | None = None) -> bytes | None:
        meta = self._read_meta(key)
        if meta is None:
            return None
        payload = self._read_payload(key, ".bin")
        if payload is None:
            return None
        if ttl is not None and self._age(meta) > ttl:
            return None
        return payload

    def set_bytes(self, key: str, value: bytes) -> None:
        meta_path, base = self._paths(key)
        with self._lock:
            self._write_atomic(base.with_suffix(".bin"), value)
            meta = {"key": key, "cached_at": time.time()}
            self._write_atomic(meta_path, json.dumps(meta).encode("utf-8"))

    def delete(self, key: str) -> None:
        meta_path, base = self._paths(key)
        for suffix in (".meta", ".json", ".bin"):
            path = meta_path if suffix == ".meta" else base.with_suffix(suffix)
            try:
                path.unlink()
            except OSError:
                pass

    def clear(self) -> int:
        """Remove every cached entry; returns the number of deleted files."""

        removed = 0
        for path in self.directory.glob("*"):
            if path.is_file() and path.suffix in (".meta", ".json", ".bin"):
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed

"""Sources of the items database: local checkout, GitHub or a downloaded snapshot."""

from __future__ import annotations

import json
import os
import shutil
import uuid
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx

from ..constants import (
    DATABASE_REF,
    DATABASE_REPO,
    DEFAULT_DATABASE_TIMEOUT,
    DEFAULT_USER_AGENT,
)
from ..errors import DatabaseError, DatabaseNotFound, DatabaseUnavailable
from ..models.common import Realm
from .cache import DiskCache

__all__ = ["GitHubProvider", "LocalProvider", "Provider"]


class Provider(ABC):
    """Read-only access to one realm of the stalzone-database repository."""

    realm: str
    is_bulk: bool = False
    cache: DiskCache | None = None

    @property
    @abstractmethod
    def namespace(self) -> str:
        """Unique cache namespace for this source."""

    @abstractmethod
    def list_item_paths(self) -> list[str]:
        """Realm-relative paths of every item JSON (``items/...``)."""

    @abstractmethod
    def list_icon_paths(self) -> list[str]:
        """Realm-relative paths of every icon (``icons/...``)."""

    @abstractmethod
    def read_json(self, path: str) -> dict[str, Any]: ...

    @abstractmethod
    def read_bytes(self, path: str) -> bytes: ...

    @abstractmethod
    def url(self, path: str) -> str | None:
        """Public URL for a file, if the source exposes one."""

    def download_archive(self, dest: str | os.PathLike[str] | None = None, *, force: bool = False) -> Path:
        raise DatabaseError(f"{type(self).__name__} does not support archive downloads")

    def close(self) -> None:
        return None


def _decode_json(raw: bytes, path: str) -> dict[str, Any]:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise DatabaseError(f"invalid JSON in {path}") from exc


class LocalProvider(Provider):
    """Reads the database from a local clone (or a downloaded snapshot)."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        realm: str | Realm | None = None,
        *,
        cache: DiskCache | None = None,
    ) -> None:
        root_path = Path(root).expanduser().resolve()
        inferred: str | None = None
        if (root_path / "items").is_dir():
            base = root_path
            inferred = root_path.name
        else:
            requested = str(Realm(realm)) if realm is not None else None
            candidates = [requested] if requested else ["ru", "global"]
            for candidate in candidates:
                if candidate and (root_path / candidate / "items").is_dir():
                    base = root_path / candidate
                    inferred = candidate
                    break
            else:
                raise DatabaseError(
                    f"{root_path} does not look like a stalzone-database checkout "
                    "(expected <root>/ru/items or <root>/global/items)"
                )
        self.root = base
        self.realm = inferred or str(realm or Realm.RU)
        self.is_bulk = True
        self.cache = cache
        self._items: list[str] | None = None
        self._icons: list[str] | None = None

    @property
    def namespace(self) -> str:
        return f"local:{self.root.as_posix()}"

    def _walk(self, sub: str, suffix: str) -> list[str]:
        base = self.root / sub
        if not base.is_dir():
            return []
        result: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(base):
            for filename in filenames:
                if filename.endswith(suffix):
                    full = Path(dirpath) / filename
                    result.append(full.relative_to(self.root).as_posix())
        result.sort()
        return result

    def list_item_paths(self) -> list[str]:
        if self._items is None:
            self._items = self._walk("items", ".json")
        return list(self._items)

    def list_icon_paths(self) -> list[str]:
        if self._icons is None:
            self._icons = self._walk("icons", ".png")
        return list(self._icons)

    def read_json(self, path: str) -> dict[str, Any]:
        file_path = self.root / path
        try:
            return _decode_json(file_path.read_bytes(), path)
        except FileNotFoundError as exc:
            raise DatabaseNotFound(path) from exc
        except OSError as exc:
            raise DatabaseError(f"cannot read {file_path}: {exc}") from exc

    def read_bytes(self, path: str) -> bytes:
        file_path = self.root / path
        try:
            return file_path.read_bytes()
        except FileNotFoundError as exc:
            raise DatabaseNotFound(path) from exc
        except OSError as exc:
            raise DatabaseError(f"cannot read {file_path}: {exc}") from exc

    def url(self, path: str) -> str | None:
        return (self.root / path).as_uri()


class GitHubProvider(Provider):
    """Fetches files from GitHub on demand, with a disk cache and ETag revalidation."""

    def __init__(
        self,
        realm: str | Realm = Realm.RU,
        *,
        repo: str = DATABASE_REPO,
        ref: str = DATABASE_REF,
        token: str | None = None,
        cache: DiskCache | None = None,
        timeout: float = DEFAULT_DATABASE_TIMEOUT,
        user_agent: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.realm = str(Realm(realm))
        self.repo = repo
        self.ref = ref
        self.token = (
            token
            or os.environ.get("STALZONE_GITHUB_TOKEN")
            or os.environ.get("GITHUB_TOKEN")
            or None
        )
        self.cache = cache or DiskCache()
        self.timeout = timeout
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self._client = client
        self._owns_client = client is None
        self._items: list[str] | None = None
        self._icons: list[str] | None = None

    @property
    def namespace(self) -> str:
        return f"github:{self.repo}@{self.ref}/{self.realm}"

    @property
    def is_bulk(self) -> bool:
        return False

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            )
        return self._client

    # --------------------------------------------------------------------- urls
    @property
    def raw_base(self) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/{self.ref}/{self.realm}"

    def raw_url(self, path: str) -> str:
        return f"{self.raw_base}/{path.lstrip('/')}"

    def url(self, path: str) -> str | None:
        return self.raw_url(path)

    def web_url(self, path: str) -> str:
        return f"https://github.com/{self.repo}/blob/{self.ref}/{self.realm}/{path.lstrip('/')}"

    # --------------------------------------------------------------------- tree
    def _tree(self) -> list[str]:
        cache_key = f"tree:{self.repo}@{self.ref}"
        cached, etag, fresh = self.cache.get_json(cache_key, allow_stale=True)
        if fresh and isinstance(cached, list):
            return cached

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if etag:
            headers["If-None-Match"] = etag

        url = f"https://api.github.com/repos/{self.repo}/git/trees/{self.ref}?recursive=1"
        try:
            response = self.client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            if isinstance(cached, list):
                return cached
            raise DatabaseUnavailable(f"cannot reach GitHub API: {exc}") from exc

        if response.status_code == 304 and isinstance(cached, list):
            self.cache.set_json(cache_key, cached, etag=etag)
            return cached
        if response.status_code == 200:
            payload = response.json()
            paths = [
                entry["path"]
                for entry in payload.get("tree") or []
                if entry.get("type") == "blob" and isinstance(entry.get("path"), str)
            ]
            self.cache.set_json(cache_key, paths, etag=response.headers.get("etag"))
            return paths
        if response.status_code in (403, 429):
            if isinstance(cached, list):
                return cached
            raise DatabaseUnavailable(
                "GitHub API rate limit reached. Pass github_token=..., use Database.local() "
                "or download a snapshot with Database.sync()"
            )
        raise DatabaseUnavailable(f"GitHub tree request failed with HTTP {response.status_code}")

    def _filtered(self, kind: str, suffix: str) -> list[str]:
        prefix = f"{self.realm}/{kind}/"
        return sorted(
            path[len(self.realm) + 1 :]
            for path in self._tree()
            if path.startswith(prefix) and path.endswith(suffix)
        )

    def list_item_paths(self) -> list[str]:
        if self._items is None:
            self._items = self._filtered("items", ".json")
        return list(self._items)

    def list_icon_paths(self) -> list[str]:
        if self._icons is None:
            self._icons = self._filtered("icons", ".png")
        return list(self._icons)

    # --------------------------------------------------------------------- files
    def read_json(self, path: str) -> dict[str, Any]:
        cache_key = f"json:{self.namespace}:{path}"
        cached, etag, fresh = self.cache.get_json(cache_key, allow_stale=True)
        if fresh and cached is not None:
            return cached

        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if etag:
            headers["If-None-Match"] = etag
        try:
            response = self.client.get(self.raw_url(path), headers=headers)
        except httpx.HTTPError as exc:
            if cached is not None:
                return cached
            raise DatabaseUnavailable(f"cannot download {path}: {exc}") from exc

        if response.status_code == 304 and cached is not None:
            self.cache.set_json(cache_key, cached, etag=etag)
            return cached
        if response.status_code == 404:
            raise DatabaseNotFound(path)
        if response.status_code >= 400:
            raise DatabaseUnavailable(f"cannot download {path}: HTTP {response.status_code}")
        data = _decode_json(response.content, path)
        self.cache.set_json(cache_key, data, etag=response.headers.get("etag"))
        return data

    def read_bytes(self, path: str) -> bytes:
        cache_key = f"bytes:{self.namespace}:{path}"
        cached = self.cache.get_bytes(cache_key)
        if cached is not None:
            return cached
        try:
            response = self.client.get(self.raw_url(path), headers={"User-Agent": self.user_agent})
        except httpx.HTTPError as exc:
            raise DatabaseUnavailable(f"cannot download {path}: {exc}") from exc
        if response.status_code == 404:
            raise DatabaseNotFound(path)
        if response.status_code >= 400:
            raise DatabaseUnavailable(f"cannot download {path}: HTTP {response.status_code}")
        self.cache.set_bytes(cache_key, response.content)
        return response.content

    # ------------------------------------------------------------------- archive
    def download_archive(
        self,
        dest: str | os.PathLike[str] | None = None,
        *,
        force: bool = False,
    ) -> Path:
        """Download the repository zipball and extract it; returns the repository root."""

        destination = Path(dest).expanduser() if dest else self.cache.directory / "snapshots"
        destination.mkdir(parents=True, exist_ok=True)
        final = destination / f"stalzone-database-{self.ref}"

        if (final / str(self.realm) / "items").is_dir() and not force:
            return final

        url = f"https://codeload.github.com/{self.repo}/zip/{self.ref}"
        archive = destination / f".archive-{self.ref}.zip"
        extract_dir = destination / f".extract-{uuid.uuid4().hex}"

        try:
            with self.client.stream("GET", url, timeout=None) as response:
                if response.status_code >= 400:
                    raise DatabaseUnavailable(f"cannot download archive: HTTP {response.status_code}")
                with archive.open("wb") as fh:
                    for chunk in response.iter_bytes():
                        fh.write(chunk)

            with zipfile.ZipFile(archive) as zf:
                root = extract_dir.resolve()
                for member in zf.infolist():
                    target = (extract_dir / member.filename).resolve()
                    if root != target and root not in target.parents:
                        raise DatabaseError("refusing to extract an unsafe archive path")
                zf.extractall(extract_dir)

            top = next((entry for entry in extract_dir.iterdir() if entry.is_dir()), None)
            if top is None:
                raise DatabaseUnavailable("database archive is empty")
            if final.exists():
                shutil.rmtree(final)
            shutil.move(str(top), str(final))
            return final
        except (OSError, zipfile.BadZipFile) as exc:
            raise DatabaseUnavailable(f"cannot unpack database archive: {exc}") from exc
        finally:
            archive.unlink(missing_ok=True)
            shutil.rmtree(extract_dir, ignore_errors=True)

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None


def snapshot_from_directory(
    root: str | os.PathLike[str],
    realm: str | Realm | None = None,
    *,
    cache_dir: str | os.PathLike[str] | None = None,
) -> LocalProvider:
    """Convenience factory used by :meth:`Database.local`."""

    cache = DiskCache(cache_dir) if cache_dir else None
    return LocalProvider(root, realm=realm, cache=cache)

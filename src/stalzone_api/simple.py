"""A deliberately tiny facade over :mod:`stalzone_api`.

The goal of this module is to make the first line of code work without reading
the documentation::

    from stalzone_api import AppClient

    client = AppClient()                       # env vars, or the demo server
    emission = await client.emission()
    lots = await client.auction("zyv9").lots(limit=3)

Use :class:`SyncAppClient` when you do not want ``async``/``await``.
"""

from __future__ import annotations

import os
from typing import Any

from .auth import AuthError
from .client import AsyncClient, Client
from .models.auction import Lot, LotPage, PricePage, PriceSummary
from .models.character import Character, CharacterProfile
from .models.clan import ClanList
from .models.common import Region, RegionInfo
from .models.emission import Emission
from .models.operations import SessionPage

__all__ = ["AppClient", "SyncAppClient", "Auction", "SyncAuction"]


def _env(*names: str) -> str | None:
    """First non-empty environment variable from ``names``."""

    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def _resolve_credentials(
    client_id: str | int | None,
    client_secret: str | None,
    token: str | None,
    demo: bool | None,
) -> tuple[str, str | int | None, str | None]:
    """Return ``(mode, client_id, secret)``; ``mode`` is demo/token/secret."""

    token = token or _env("STALZONE_ACCESS_TOKEN", "APP_TOKEN")
    client_id = client_id or _env("STALZONE_APP_ID", "CLIENT_ID")
    client_secret = client_secret or _env("STALZONE_APP_SECRET", "CLIENT_SECRET")

    if demo is True:
        return "demo", None, None
    if token:
        return "token", token, None
    if client_id and client_secret:
        return "secret", client_id, client_secret
    if demo is False:
        raise AuthError(
            "No credentials found. Pass client_id/client_secret or token, "
            "set STALZONE_APP_ID/STALZONE_APP_SECRET / STALZONE_ACCESS_TOKEN, "
            "or use AppClient.demo()."
        )
    # Nothing configured: the public demo server is always available.
    return "demo", None, None


def _normalize_region(region: str | Region) -> str:
    return str(Region(region))


class Auction:
    """Auction methods for one item, returned by :meth:`AppClient.auction`."""

    def __init__(self, client: AsyncClient, item_id: str) -> None:
        self._client = client
        self.item_id = str(item_id)

    async def lots(
        self,
        limit: int = 20,
        offset: int = 0,
        *,
        sort: str | None = None,
        order: str | None = None,
        region: str | Region | None = None,
    ) -> LotPage:
        """Active lots, cheapest (or newest) first."""

        return await self._client.auction.lots(
            self.item_id,
            limit=limit,
            offset=offset,
            sort=sort,
            order=order,
            region=region,
        )

    async def history(
        self,
        limit: int = 20,
        offset: int = 0,
        *,
        region: str | Region | None = None,
    ) -> PricePage:
        """Completed sales, newest first."""

        return await self._client.auction.history(
            self.item_id, limit=limit, offset=offset, region=region
        )

    async def summary(
        self,
        limit: int = 200,
        *,
        region: str | Region | None = None,
    ) -> PriceSummary:
        """Min/max/mean/median price over the last ``limit`` sales."""

        page = await self.history(limit=limit, region=region)
        return PriceSummary.from_prices(page.prices)

    async def all_lots(
        self,
        limit: int | None = None,
        *,
        region: str | Region | None = None,
    ) -> list[Lot]:
        """Every active lot (pages are fetched automatically)."""

        return [
            lot
            async for lot in self._client.auction.iter_lots(
                self.item_id, limit=limit, region=region
            )
        ]

    def __repr__(self) -> str:
        return f"Auction({self.item_id!r})"


class SyncAuction:
    """Synchronous twin of :class:`Auction`."""

    def __init__(self, client: Client, item_id: str) -> None:
        self._client = client
        self.item_id = str(item_id)

    def lots(
        self,
        limit: int = 20,
        offset: int = 0,
        *,
        sort: str | None = None,
        order: str | None = None,
        region: str | Region | None = None,
    ) -> LotPage:
        return self._client.auction.lots(
            self.item_id,
            limit=limit,
            offset=offset,
            sort=sort,
            order=order,
            region=region,
        )

    def history(
        self,
        limit: int = 20,
        offset: int = 0,
        *,
        region: str | Region | None = None,
    ) -> PricePage:
        return self._client.auction.history(
            self.item_id, limit=limit, offset=offset, region=region
        )

    def summary(
        self,
        limit: int = 200,
        *,
        region: str | Region | None = None,
    ) -> PriceSummary:
        page = self.history(limit=limit, region=region)
        return PriceSummary.from_prices(page.prices)

    def all_lots(
        self,
        limit: int | None = None,
        *,
        region: str | Region | None = None,
    ) -> list[Lot]:
        return list(self._client.auction.iter_lots(self.item_id, limit=limit, region=region))

    def __repr__(self) -> str:
        return f"SyncAuction({self.item_id!r})"


class AppClient:
    """The simplest asynchronous client.

    ``AppClient()`` reads credentials from the environment; if none are set it
    silently uses the public demo server. All methods are ``await``-able except
    :meth:`auction`, which returns a small helper object.
    """

    def __init__(
        self,
        client_id: str | int | None = None,
        client_secret: str | None = None,
        *,
        token: str | None = None,
        region: str | Region = Region.RU,
        demo: bool | None = None,
        **kwargs: Any,
    ) -> None:
        mode, identity, secret = _resolve_credentials(client_id, client_secret, token, demo)
        self.mode = mode
        self.demo = mode == "demo"
        self.region = _normalize_region(region)
        options = {"region": self.region, **kwargs}

        if mode == "demo":
            self._client = AsyncClient.demo(user=True, **options)
        elif mode == "token":
            self._client = AsyncClient(access_token=str(identity), **options)
        else:
            self._client = AsyncClient(
                app_id=identity, app_secret=secret, auth="secret", **options
            )

    @classmethod
    def demo(cls, **kwargs: Any) -> "AppClient":
        """Create a client for the public demo server."""

        return cls(demo=True, **kwargs)

    def auction(self, item_id: str) -> Auction:
        """Select an item for auction calls: ``await client.auction("zyv9").lots()``."""

        return Auction(self._client, item_id)

    async def regions(self) -> list[RegionInfo]:
        return await self._client.regions()

    async def emission(self, region: str | Region | None = None) -> Emission:
        """Current/previous emission times."""

        return await self._client.emission(region)

    async def profile(
        self,
        character: str,
        *,
        uuid: bool = False,
        region: str | Region | None = None,
    ) -> CharacterProfile:
        """Public profile by character name, or by uuid with ``uuid=True``."""

        if uuid:
            return await self._client.characters.profile_by_uuid(character, region=region)
        return await self._client.characters.profile(character, region=region)

    async def characters(self, region: str | Region | None = None) -> list[Character]:
        """Characters visible to the current token (demo has three)."""

        return await self._client.characters.list(region=region)

    async def friends(
        self, character: str, *, region: str | Region | None = None
    ) -> list[str]:
        return await self._client.friends(character, region=region)

    async def clans(
        self,
        limit: int = 20,
        offset: int = 0,
        *,
        region: str | Region | None = None,
    ) -> ClanList:
        return await self._client.clans.list(limit=limit, offset=offset, region=region)

    async def sessions(
        self,
        limit: int = 20,
        *,
        region: str | Region | None = None,
        **filters: Any,
    ) -> SessionPage:
        """Operation sessions; filters: ``username``, ``map``, ``after``, ``before``."""

        return await self._client.operations.sessions(limit=limit, region=region, **filters)

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Raw API call, for endpoints not covered by the models."""

        return await self._client.request(method, path, **kwargs)

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> "AppClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"AppClient(mode={self.mode!r}, region={self.region!r})"


class SyncAppClient:
    """The same facade without ``async``/``await``."""

    def __init__(
        self,
        client_id: str | int | None = None,
        client_secret: str | None = None,
        *,
        token: str | None = None,
        region: str | Region = Region.RU,
        demo: bool | None = None,
        **kwargs: Any,
    ) -> None:
        mode, identity, secret = _resolve_credentials(client_id, client_secret, token, demo)
        self.mode = mode
        self.demo = mode == "demo"
        self.region = _normalize_region(region)
        options = {"region": self.region, **kwargs}

        if mode == "demo":
            self._client = Client.demo(user=True, **options)
        elif mode == "token":
            self._client = Client(access_token=str(identity), **options)
        else:
            self._client = Client(
                app_id=identity, app_secret=secret, auth="secret", **options
            )

    @classmethod
    def demo(cls, **kwargs: Any) -> "SyncAppClient":
        return cls(demo=True, **kwargs)

    def auction(self, item_id: str) -> SyncAuction:
        return SyncAuction(self._client, item_id)

    def regions(self) -> list[RegionInfo]:
        return self._client.regions()

    def emission(self, region: str | Region | None = None) -> Emission:
        return self._client.emission(region)

    def profile(
        self,
        character: str,
        *,
        uuid: bool = False,
        region: str | Region | None = None,
    ) -> CharacterProfile:
        if uuid:
            return self._client.characters.profile_by_uuid(character, region=region)
        return self._client.characters.profile(character, region=region)

    def characters(self, region: str | Region | None = None) -> list[Character]:
        return self._client.characters.list(region=region)

    def friends(self, character: str, *, region: str | Region | None = None) -> list[str]:
        return self._client.friends(character, region=region)

    def clans(
        self,
        limit: int = 20,
        offset: int = 0,
        *,
        region: str | Region | None = None,
    ) -> ClanList:
        return self._client.clans.list(limit=limit, offset=offset, region=region)

    def sessions(
        self,
        limit: int = 20,
        *,
        region: str | Region | None = None,
        **filters: Any,
    ) -> SessionPage:
        return self._client.operations.sessions(limit=limit, region=region, **filters)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        return self._client.request(method, path, **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SyncAppClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"SyncAppClient(mode={self.mode!r}, region={self.region!r})"

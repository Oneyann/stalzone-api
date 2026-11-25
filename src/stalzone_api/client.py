"""The one client you need: :class:`AppClient`."""

from __future__ import annotations

import os
from typing import Any, Mapping
from urllib.parse import quote

from ._http import HttpClient
from .constants import (
    DEFAULT_REGION,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    DEMO_CLIENT_ID,
    DEMO_CLIENT_SECRET,
    DEMO_URL,
    PROD_URL,
)
from .errors import StalzoneError
from .models import (
    Character,
    Clan,
    ClanMember,
    Emission,
    Lot,
    Page,
    Price,
    Profile,
    Region,
    RegionInfo,
    Session,
)


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


def _credentials(
    client_id: str | int | None,
    client_secret: str | None,
    token: str | None,
    demo: bool,
) -> tuple[str, dict[str, str]]:
    """Return ``(base_url, auth_headers)``.

    ``token`` wins over id/secret, explicit values over the environment, and
    with nothing configured at all the public demo server is used.
    """

    client_id = client_id or _env("STALZONE_APP_ID")
    client_secret = client_secret or _env("STALZONE_APP_SECRET")
    token = token or _env("STALZONE_ACCESS_TOKEN")

    if demo:
        return DEMO_URL, {"Client-Id": DEMO_CLIENT_ID, "Client-Secret": DEMO_CLIENT_SECRET}
    if token:
        return PROD_URL, {"Authorization": f"Bearer {token}"}
    if client_id and client_secret:
        return PROD_URL, {"Client-Id": str(client_id), "Client-Secret": str(client_secret)}
    if client_id or client_secret:
        raise StalzoneError("client_id and client_secret must be provided together")
    return DEMO_URL, {"Client-Id": DEMO_CLIENT_ID, "Client-Secret": DEMO_CLIENT_SECRET}


class Auction:
    """Auction calls for one item, created by :meth:`AppClient.auction`."""

    def __init__(self, client: "AppClient", item_id: str) -> None:
        self._client = client
        self.item_id = str(item_id)

    async def lots(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        sort: str | None = None,
        order: str | None = None,
        region: Region | str | None = None,
    ) -> Page[Lot]:
        """Active lots for the item."""

        data = await self._client.request(
            "GET",
            f"{self._client._region(region)}/auction/{quote(self.item_id, safe='')}/lots",
            limit=limit,
            offset=offset,
            sort=sort,
            order=order,
        )
        return Page(
            [Lot.from_dict(lot) for lot in data.get("lots") or []],
            int(data.get("total") or 0),
            offset,
        )

    async def history(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        region: Region | str | None = None,
    ) -> Page[Price]:
        """Completed sales, newest first."""

        data = await self._client.request(
            "GET",
            f"{self._client._region(region)}/auction/{quote(self.item_id, safe='')}/history",
            limit=limit,
            offset=offset,
        )
        return Page(
            [Price.from_dict(price) for price in data.get("prices") or []],
            int(data.get("total") or 0),
            offset,
        )

    def __repr__(self) -> str:
        return f"Auction({self.item_id!r})"


class AppClient:
    """Async client for the Stalzone API.

    Credentials are optional: they are read from ``STALZONE_APP_ID`` /
    ``STALZONE_APP_SECRET`` / ``STALZONE_ACCESS_TOKEN``, and when nothing is
    configured the public demo server is used.
    """

    def __init__(
        self,
        client_id: str | int | None = None,
        client_secret: str | None = None,
        *,
        token: str | None = None,
        region: Region | str = DEFAULT_REGION,
        demo: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        base_url, auth_headers = _credentials(client_id, client_secret, token, demo)
        self.region = Region(region)
        self.demo = base_url == DEMO_URL
        self._http = HttpClient(
            base_url,
            {**auth_headers, **(headers or {})},
            timeout=timeout,
            retries=retries,
        )

    def _region(self, region: Region | str | None) -> str:
        return str(Region(region) if region is not None else self.region)

    def auction(self, item_id: str) -> Auction:
        """Select an item: ``await client.auction("y1q9").lots(limit=3)``."""

        return Auction(self, item_id)

    async def request(self, method: str, path: str, **params: Any) -> Any:
        """Raw call for endpoints not covered by the helpers below."""

        return await self._http.request(method, path, params)

    async def regions(self) -> list[RegionInfo]:
        data = await self.request("GET", "regions")
        return [RegionInfo.from_dict(item) for item in data or []]

    async def emission(self, region: Region | str | None = None) -> Emission:
        data = await self.request("GET", f"{self._region(region)}/emission")
        return Emission.from_dict(data)

    async def profile(
        self,
        character: str,
        *,
        uuid: bool = False,
        region: Region | str | None = None,
    ) -> Profile:
        """Public profile by character name, or by uuid with ``uuid=True``."""

        key = "by-uuid" if uuid else "by-name"
        data = await self.request(
            "GET",
            f"{self._region(region)}/character/{key}/{quote(str(character), safe='')}/profile",
        )
        return Profile.from_dict(data)

    async def characters(self, region: Region | str | None = None) -> list[Character]:
        """Characters visible to the current token (needs a user token)."""

        data = await self.request("GET", f"{self._region(region)}/characters")
        return [Character.from_dict(item) for item in data or []]

    async def friends(
        self, character: str, region: Region | str | None = None
    ) -> list[str]:
        """Friend names (needs a user token)."""

        data = await self.request(
            "GET", f"{self._region(region)}/friends/{quote(str(character), safe='')}"
        )
        return [
            str(item.get("name") or item.get("username") or "") if isinstance(item, dict) else str(item)
            for item in data or []
        ]

    async def clans(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        region: Region | str | None = None,
    ) -> Page[Clan]:
        data = await self.request(
            "GET", f"{self._region(region)}/clans", limit=limit, offset=offset
        )
        return Page(
            [Clan.from_dict(item) for item in data.get("data") or []],
            int(data.get("totalClans") or 0),
            offset,
        )

    async def clan(self, clan_id: str, region: Region | str | None = None) -> Clan:
        data = await self.request(
            "GET", f"{self._region(region)}/clan/{quote(str(clan_id), safe='')}/info"
        )
        return Clan.from_dict(data)

    async def clan_members(
        self, clan_id: str, region: Region | str | None = None
    ) -> list[ClanMember]:
        data = await self.request(
            "GET", f"{self._region(region)}/clan/{quote(str(clan_id), safe='')}/members"
        )
        if isinstance(data, dict):
            data = data.get("members") or data.get("data") or []
        return [ClanMember.from_dict(item) for item in data]

    async def sessions(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        username: str | None = None,
        map: str | None = None,
        after: str | None = None,
        before: str | None = None,
        sort: str | None = None,
        order: str | None = None,
        region: Region | str | None = None,
    ) -> Page[Session]:
        """Operation sessions with optional filters."""

        data = await self.request(
            "GET",
            f"{self._region(region)}/operations/sessions",
            limit=limit,
            offset=offset,
            username=username,
            map=map,
            after=after,
            before=before,
            sort=sort,
            order=order,
        )
        return Page(
            [Session.from_dict(item) for item in data.get("sessions") or []],
            int(data.get("total") or 0),
            offset,
        )

    async def close(self) -> None:
        await self._http.close()

    async def __aenter__(self) -> "AppClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"AppClient(region={self.region}, demo={self.demo})"

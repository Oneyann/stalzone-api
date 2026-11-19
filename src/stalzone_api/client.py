"""High-level clients for the Stalzone API."""

from __future__ import annotations

import os
from typing import Any, Iterable, Mapping
from urllib.parse import quote

from ._http import AsyncTransport, RateLimiter, SyncTransport
from .auth import (
    AppSecretCredentials,
    Credentials,
    OAuth,
    StaticTokenCredentials,
    TokenCredentials,
    UserInfo,
    async_fetch_user_info,
    fetch_user_info,
)
from .constants import (
    DEFAULT_TIMEOUT,
    DEMO_APP_SECRET,
    DEMO_APP_TOKEN,
    DEMO_APP_ID,
    DEMO_URL,
    DEMO_USER_TOKEN,
    PROD_URL,
)
from .errors import AuthError
from .models.auction import LotPage, PricePage, PriceSummary
from .models.character import Character, CharacterProfile
from .models.clan import Clan, ClanList, ClanMember
from .models.common import Region, RegionInfo, format_datetime, region_value
from .models.emission import Emission
from .models.operations import SessionPage
from .pagination import paginate

__all__ = ["AsyncClient", "Client"]


def _resolve_region(region: str | Region | None, default: str | None) -> str:
    value = region if region is not None else default
    if value is None:
        raise ValueError(
            "region is required: pass region='EU' or create the client with Client(region='EU')"
        )
    return region_value(value)


def _env_credentials(
    app_id: str | int | None,
    app_secret: str | None,
    access_token: str | None,
) -> tuple[str | int | None, str | None, str | None]:
    """Fill missing credentials from ``STALZONE_*`` environment variables.

    Explicit arguments always win; a token from the environment takes precedence
    over application credentials from the environment.
    """

    if access_token or app_id is not None or app_secret is not None:
        return app_id, app_secret, access_token
    env_token = os.environ.get("STALZONE_ACCESS_TOKEN")
    if env_token:
        return app_id, app_secret, env_token
    env_id = os.environ.get("STALZONE_APP_ID")
    env_secret = os.environ.get("STALZONE_APP_SECRET")
    return env_id or None, env_secret or None, access_token


def _as_list(payload: Any, keys: Iterable[str] = ("data", "items", "members", "characters")) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        for value in payload.values():
            if isinstance(value, list):
                return value
    return []


def _lot_params(
    offset: int | None,
    limit: int | None,
    sort: str | None,
    order: str | None,
    additional: bool | None,
) -> dict[str, Any]:
    return {
        "offset": offset,
        "limit": limit,
        "sort": sort,
        "order": order,
        "additional": additional,
    }


def _session_params(
    *,
    username: str | None,
    limit: int | None,
    offset: int | None,
    after: Any,
    before: Any,
    map: str | None,
    sort: str | None,
    order: str | None,
) -> dict[str, Any]:
    return {
        "username": username,
        "limit": limit,
        "offset": offset,
        "after": format_datetime(after) if after is not None else None,
        "before": format_datetime(before) if before is not None else None,
        "map": map,
        "sort": sort,
        "order": order,
    }


def _build_credentials(
    *,
    app_id: str | int | None,
    app_secret: str | None,
    access_token: str | None,
    auth: str | None,
    oauth: OAuth | None,
    timeout: float,
    user_agent: str | None,
    on_token_update: Any,
) -> tuple[Credentials | None, OAuth | None]:
    if access_token:
        return StaticTokenCredentials(access_token), oauth
    if app_id is not None and app_secret:
        mode = (auth or "secret").strip().lower()
        if mode in ("secret", "headers", "client"):
            return AppSecretCredentials(app_id, app_secret), oauth
        if mode in ("token", "oauth", "client_credentials"):
            oauth = oauth or OAuth(app_id, app_secret, timeout=timeout, user_agent=user_agent)
            return TokenCredentials(oauth, on_update=on_token_update), oauth
        raise ValueError("auth must be one of: 'secret', 'token'")
    if app_id is not None or app_secret:
        raise ValueError("app_id and app_secret must be provided together")
    return None, oauth


# --------------------------------------------------------------------- resources
class AuctionAPI:
    """Auction endpoints (``/{region}/auction/{item}/...``)."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def lots(
        self,
        item: str,
        *,
        region: str | Region | None = None,
        offset: int = 0,
        limit: int = 20,
        sort: str | None = None,
        order: str | None = None,
        additional: bool | None = None,
    ) -> LotPage:
        """Active lots for an item, sorted by ``time_created``/``time_left``/``current_price``/``buyout_price``."""

        resolved = _resolve_region(region, self._client.region)
        data = self._client.request(
            "GET",
            f"{resolved}/auction/{quote(str(item), safe='')}/lots",
            params=_lot_params(offset, limit, sort, order, additional),
        )
        return LotPage.from_dict(data or {}, offset=offset)

    def history(
        self,
        item: str,
        *,
        region: str | Region | None = None,
        offset: int = 0,
        limit: int = 20,
        additional: bool | None = None,
    ) -> PricePage:
        """Completed purchases for an item, newest first."""

        resolved = _resolve_region(region, self._client.region)
        data = self._client.request(
            "GET",
            f"{resolved}/auction/{quote(str(item), safe='')}/history",
            params=_lot_params(offset, limit, None, None, additional),
        )
        return PricePage.from_dict(data or {}, offset=offset)

    def iter_lots(
        self,
        item: str,
        *,
        region: str | Region | None = None,
        page_size: int = 200,
        limit: int | None = None,
        sort: str | None = None,
        order: str | None = None,
        additional: bool | None = None,
    ):
        """Iterate over every active lot, handling pagination automatically."""

        def fetch(offset: int, size: int) -> LotPage:
            return self.lots(
                item,
                region=region,
                offset=offset,
                limit=size,
                sort=sort,
                order=order,
                additional=additional,
            )

        return paginate(fetch, page_size=page_size, limit=limit)

    def iter_history(
        self,
        item: str,
        *,
        region: str | Region | None = None,
        page_size: int = 200,
        limit: int | None = None,
        additional: bool | None = None,
    ):
        """Iterate over the full price history of an item."""

        def fetch(offset: int, size: int) -> PricePage:
            return self.history(item, region=region, offset=offset, limit=size, additional=additional)

        return paginate(fetch, page_size=page_size, limit=limit)

    def price_summary(
        self,
        item: str,
        *,
        region: str | Region | None = None,
        limit: int = 200,
    ) -> PriceSummary:
        """Aggregate the latest ``limit`` purchases into min/max/mean/median values."""

        page = self.history(item, region=region, limit=min(limit, 200))
        prices = list(page.prices)
        if limit > 200:
            prices = list(self.iter_history(item, region=region, limit=limit, page_size=200))
        return PriceSummary.from_prices(prices)


class CharactersAPI:
    """Character endpoints."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def list(self, *, region: str | Region | None = None) -> list[Character]:
        """Characters of the user the access token belongs to (user token required)."""

        resolved = _resolve_region(region, self._client.region)
        data = self._client.request("GET", f"{resolved}/characters")
        return [Character.from_dict(entry) for entry in _as_list(data)]

    def profile(self, character: str, *, region: str | Region | None = None) -> CharacterProfile:
        """Public character profile looked up by name (case-insensitive)."""

        resolved = _resolve_region(region, self._client.region)
        data = self._client.request(
            "GET",
            f"{resolved}/character/by-name/{quote(str(character), safe='')}/profile",
        )
        return CharacterProfile.from_dict(data or {})

    def profile_by_uuid(self, uuid: str, *, region: str | Region | None = None) -> CharacterProfile:
        """Public character profile looked up by its persistent UUID."""

        resolved = _resolve_region(region, self._client.region)
        data = self._client.request(
            "GET",
            f"{resolved}/character/by-uuid/{quote(str(uuid), safe='')}/profile",
        )
        return CharacterProfile.from_dict(data or {})


class ClansAPI:
    """Clan endpoints."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def list(
        self,
        *,
        region: str | Region | None = None,
        offset: int = 0,
        limit: int = 200,
    ) -> ClanList:
        """All clans registered on the region (paginated)."""

        resolved = _resolve_region(region, self._client.region)
        data = self._client.request(
            "GET",
            f"{resolved}/clans",
            params={"offset": offset, "limit": limit},
        )
        return ClanList.from_dict(data or {}, offset=offset)

    def iter_all(
        self,
        *,
        region: str | Region | None = None,
        page_size: int = 200,
        limit: int | None = None,
    ):
        """Iterate over every clan on the region."""

        def fetch(offset: int, size: int) -> ClanList:
            return self.list(region=region, offset=offset, limit=size)

        return paginate(fetch, page_size=page_size, limit=limit)

    def info(self, clan_id: str, *, region: str | Region | None = None) -> Clan:
        resolved = _resolve_region(region, self._client.region)
        data = self._client.request(
            "GET",
            f"{resolved}/clan/{quote(str(clan_id), safe='')}/info",
        )
        return Clan.from_dict(data or {})

    def members(self, clan_id: str, *, region: str | Region | None = None) -> list[ClanMember]:
        """Clan members (requires a user token of a clan member)."""

        resolved = _resolve_region(region, self._client.region)
        data = self._client.request(
            "GET",
            f"{resolved}/clan/{quote(str(clan_id), safe='')}/members",
        )
        return [ClanMember.from_dict(entry) for entry in _as_list(data)]


class OperationsAPI:
    """Operation session endpoints."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def sessions(
        self,
        *,
        region: str | Region | None = None,
        username: str | None = None,
        limit: int = 100,
        offset: int = 0,
        after: Any = None,
        before: Any = None,
        map: str | None = None,
        sort: str | None = None,
        order: str | None = None,
    ) -> SessionPage:
        """List operation sessions (no authentication required)."""

        resolved = _resolve_region(region, self._client.region)
        data = self._client.request(
            "GET",
            f"{resolved}/operations/sessions",
            params=_session_params(
                username=username,
                limit=limit,
                offset=offset,
                after=after,
                before=before,
                map=map,
                sort=sort,
                order=order,
            ),
        )
        return SessionPage.from_dict(data or {}, offset=offset)

    def iter_sessions(
        self,
        *,
        region: str | Region | None = None,
        username: str | None = None,
        page_size: int = 100,
        limit: int | None = None,
        after: Any = None,
        before: Any = None,
        map: str | None = None,
        sort: str | None = None,
        order: str | None = None,
    ):
        def fetch(offset: int, size: int) -> SessionPage:
            return self.sessions(
                region=region,
                username=username,
                limit=size,
                offset=offset,
                after=after,
                before=before,
                map=map,
                sort=sort,
                order=order,
            )

        return paginate(fetch, page_size=page_size, limit=limit)


class Client:
    """Synchronous client for the Stalzone API.

    Three authentication modes are supported:

    * ``Client(app_id=..., app_secret=...)`` — secret headers (stateless, default);
    * ``Client(app_id=..., app_secret=..., auth="token")`` — OAuth client credentials;
    * ``Client(access_token=...)`` — a user or application access token.
    """

    def __init__(
        self,
        *,
        app_id: str | int | None = None,
        app_secret: str | None = None,
        access_token: str | None = None,
        auth: str | None = None,
        base_url: str = PROD_URL,
        region: str | Region | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = 3,
        backoff: float = 0.5,
        user_agent: str | None = None,
        rate_limit: float | None = None,
        credentials: Credentials | None = None,
        oauth: OAuth | None = None,
        client: Any = None,
        on_token_update: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.region = region_value(region) if region is not None else None
        self._oauth = oauth
        if credentials is None:
            app_id, app_secret, access_token = _env_credentials(app_id, app_secret, access_token)
            credentials, self._oauth = _build_credentials(
                app_id=app_id,
                app_secret=app_secret,
                access_token=access_token,
                auth=auth,
                oauth=oauth,
                timeout=timeout,
                user_agent=user_agent,
                on_token_update=on_token_update,
            )
        self._credentials = credentials
        self._rate_limiter = RateLimiter(rate_limit) if rate_limit else None
        self._http = SyncTransport(
            base_url,
            credentials=credentials,
            headers=headers,
            timeout=timeout,
            retries=retries,
            backoff=backoff,
            rate_limiter=self._rate_limiter,
            user_agent=user_agent,
            client=client,
        )
        self.auction = AuctionAPI(self)
        self.characters = CharactersAPI(self)
        self.clans = ClansAPI(self)
        self.operations = OperationsAPI(self)

    # ------------------------------------------------------------------- factory
    @classmethod
    def demo(
        cls,
        *,
        user: bool = False,
        token: str | None = None,
        **kwargs: Any,
    ) -> "Client":
        """Client preconfigured for ``dapi.stalzone.com`` with the published demo token."""

        kwargs.setdefault("base_url", DEMO_URL)
        kwargs.setdefault("access_token", token or (DEMO_USER_TOKEN if user else DEMO_APP_TOKEN))
        return cls(**kwargs)

    @classmethod
    def secret(
        cls,
        app_id: str | int,
        app_secret: str,
        **kwargs: Any,
    ) -> "Client":
        """Shortcut for the secret-headers authentication mode."""

        kwargs.setdefault("base_url", DEMO_URL if app_id == DEMO_APP_ID and app_secret == DEMO_APP_SECRET else PROD_URL)
        return cls(app_id=app_id, app_secret=app_secret, auth="secret", **kwargs)

    @classmethod
    def demo_secret(cls, **kwargs: Any) -> "Client":
        kwargs.setdefault("base_url", DEMO_URL)
        return cls(app_id=DEMO_APP_ID, app_secret=DEMO_APP_SECRET, auth="secret", **kwargs)

    # ------------------------------------------------------------------ requests
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Escape hatch for calling a raw API path."""

        return self._http.request(method, path, params=params, headers=headers)

    def request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        return self._http.request_bytes(method, path, params=params, headers=headers)

    # ----------------------------------------------------------------- endpoints
    def regions(self) -> list[RegionInfo]:
        """List of regions available through the API."""

        data = self.request("GET", "regions")
        return [RegionInfo.from_dict(entry) for entry in _as_list(data)]

    def emission(self, region: str | Region | None = None) -> Emission:
        """Current and previous emission timestamps."""

        resolved = _resolve_region(region, self.region)
        return Emission.from_dict(self.request("GET", f"{resolved}/emission") or {})

    def friends(self, character: str, *, region: str | Region | None = None) -> list[str]:
        """Friend list of a character (requires a user token that owns the character)."""

        resolved = _resolve_region(region, self.region)
        data = self.request(
            "GET",
            f"{resolved}/friends/{quote(str(character), safe='')}",
        )
        result: list[str] = []
        for entry in _as_list(data, keys=("friends", "data")):
            if isinstance(entry, str):
                result.append(entry)
            elif isinstance(entry, dict):
                name = entry.get("name") or entry.get("username") or entry.get("character")
                if name:
                    result.append(str(name))
        return result

    def user_info(self) -> UserInfo:
        """EXBO account of the current user access token (or of the app token owner)."""

        if self._credentials is None:
            raise AuthError("user_info() requires an access token")
        token = self._credentials.ensure_token()
        if not token:
            raise AuthError("user_info() requires a user access token")
        return fetch_user_info(token, timeout=self._http.timeout, user_agent=self._http.user_agent)

    @property
    def credentials(self) -> Credentials | None:
        return self._credentials

    @property
    def oauth(self) -> OAuth | None:
        return self._oauth

    @property
    def access_token(self) -> str | None:
        """Current access token, if one is configured or can be obtained."""

        if self._credentials is None:
            return None
        return self._credentials.ensure_token()

    def close(self) -> None:
        self._http.close()
        if self._oauth is not None:
            self._oauth.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        auth = type(self._credentials).__name__ if self._credentials else "none"
        return f"Client(base_url={self._http.base_url!r}, auth={auth})"


# ------------------------------------------------------------------------- async
class AsyncAuctionAPI:
    def __init__(self, client: "AsyncClient") -> None:
        self._client = client

    async def lots(
        self,
        item: str,
        *,
        region: str | Region | None = None,
        offset: int = 0,
        limit: int = 20,
        sort: str | None = None,
        order: str | None = None,
        additional: bool | None = None,
    ) -> LotPage:
        resolved = _resolve_region(region, self._client.region)
        data = await self._client.request(
            "GET",
            f"{resolved}/auction/{quote(str(item), safe='')}/lots",
            params=_lot_params(offset, limit, sort, order, additional),
        )
        return LotPage.from_dict(data or {}, offset=offset)

    async def history(
        self,
        item: str,
        *,
        region: str | Region | None = None,
        offset: int = 0,
        limit: int = 20,
        additional: bool | None = None,
    ) -> PricePage:
        resolved = _resolve_region(region, self._client.region)
        data = await self._client.request(
            "GET",
            f"{resolved}/auction/{quote(str(item), safe='')}/history",
            params=_lot_params(offset, limit, None, None, additional),
        )
        return PricePage.from_dict(data or {}, offset=offset)

    async def iter_lots(
        self,
        item: str,
        *,
        region: str | Region | None = None,
        page_size: int = 200,
        limit: int | None = None,
        sort: str | None = None,
        order: str | None = None,
        additional: bool | None = None,
    ):
        offset = 0
        produced = 0
        while True:
            page = await self.lots(
                item,
                region=region,
                offset=offset,
                limit=page_size,
                sort=sort,
                order=order,
                additional=additional,
            )
            for lot in page.lots:
                yield lot
                produced += 1
                if limit is not None and produced >= limit:
                    return
            if page.is_last:
                return
            offset += len(page.lots)

    async def iter_history(
        self,
        item: str,
        *,
        region: str | Region | None = None,
        page_size: int = 200,
        limit: int | None = None,
        additional: bool | None = None,
    ):
        offset = 0
        produced = 0
        while True:
            page = await self.history(
                item, region=region, offset=offset, limit=page_size, additional=additional
            )
            for entry in page.prices:
                yield entry
                produced += 1
                if limit is not None and produced >= limit:
                    return
            if page.is_last:
                return
            offset += len(page.prices)

    async def price_summary(
        self,
        item: str,
        *,
        region: str | Region | None = None,
        limit: int = 200,
    ) -> PriceSummary:
        if limit <= 200:
            page = await self.history(item, region=region, limit=limit)
            return PriceSummary.from_prices(page.prices)
        prices = [entry async for entry in self.iter_history(item, region=region, limit=limit)]
        return PriceSummary.from_prices(prices)


class AsyncCharactersAPI:
    def __init__(self, client: "AsyncClient") -> None:
        self._client = client

    async def list(self, *, region: str | Region | None = None) -> list[Character]:
        resolved = _resolve_region(region, self._client.region)
        data = await self._client.request("GET", f"{resolved}/characters")
        return [Character.from_dict(entry) for entry in _as_list(data)]

    async def profile(self, character: str, *, region: str | Region | None = None) -> CharacterProfile:
        resolved = _resolve_region(region, self._client.region)
        data = await self._client.request(
            "GET",
            f"{resolved}/character/by-name/{quote(str(character), safe='')}/profile",
        )
        return CharacterProfile.from_dict(data or {})

    async def profile_by_uuid(self, uuid: str, *, region: str | Region | None = None) -> CharacterProfile:
        resolved = _resolve_region(region, self._client.region)
        data = await self._client.request(
            "GET",
            f"{resolved}/character/by-uuid/{quote(str(uuid), safe='')}/profile",
        )
        return CharacterProfile.from_dict(data or {})


class AsyncClansAPI:
    def __init__(self, client: "AsyncClient") -> None:
        self._client = client

    async def list(
        self,
        *,
        region: str | Region | None = None,
        offset: int = 0,
        limit: int = 200,
    ) -> ClanList:
        resolved = _resolve_region(region, self._client.region)
        data = await self._client.request(
            "GET",
            f"{resolved}/clans",
            params={"offset": offset, "limit": limit},
        )
        return ClanList.from_dict(data or {}, offset=offset)

    async def iter_all(
        self,
        *,
        region: str | Region | None = None,
        page_size: int = 200,
        limit: int | None = None,
    ):
        offset = 0
        produced = 0
        while True:
            page = await self.list(region=region, offset=offset, limit=page_size)
            for clan in page.data:
                yield clan
                produced += 1
                if limit is not None and produced >= limit:
                    return
            if page.is_last:
                return
            offset += len(page.data)

    async def info(self, clan_id: str, *, region: str | Region | None = None) -> Clan:
        resolved = _resolve_region(region, self._client.region)
        data = await self._client.request(
            "GET",
            f"{resolved}/clan/{quote(str(clan_id), safe='')}/info",
        )
        return Clan.from_dict(data or {})

    async def members(self, clan_id: str, *, region: str | Region | None = None) -> list[ClanMember]:
        resolved = _resolve_region(region, self._client.region)
        data = await self._client.request(
            "GET",
            f"{resolved}/clan/{quote(str(clan_id), safe='')}/members",
        )
        return [ClanMember.from_dict(entry) for entry in _as_list(data)]


class AsyncOperationsAPI:
    def __init__(self, client: "AsyncClient") -> None:
        self._client = client

    async def sessions(
        self,
        *,
        region: str | Region | None = None,
        username: str | None = None,
        limit: int = 100,
        offset: int = 0,
        after: Any = None,
        before: Any = None,
        map: str | None = None,
        sort: str | None = None,
        order: str | None = None,
    ) -> SessionPage:
        resolved = _resolve_region(region, self._client.region)
        data = await self._client.request(
            "GET",
            f"{resolved}/operations/sessions",
            params=_session_params(
                username=username,
                limit=limit,
                offset=offset,
                after=after,
                before=before,
                map=map,
                sort=sort,
                order=order,
            ),
        )
        return SessionPage.from_dict(data or {}, offset=offset)

    async def iter_sessions(
        self,
        *,
        region: str | Region | None = None,
        username: str | None = None,
        page_size: int = 100,
        limit: int | None = None,
        after: Any = None,
        before: Any = None,
        map: str | None = None,
        sort: str | None = None,
        order: str | None = None,
    ):
        offset = 0
        produced = 0
        while True:
            page = await self.sessions(
                region=region,
                username=username,
                limit=page_size,
                offset=offset,
                after=after,
                before=before,
                map=map,
                sort=sort,
                order=order,
            )
            for session in page.sessions:
                yield session
                produced += 1
                if limit is not None and produced >= limit:
                    return
            if page.is_last:
                return
            offset += len(page.sessions)


class AsyncClient:
    """Asynchronous counterpart of :class:`Client` (same API surface, ``await`` everything)."""

    def __init__(
        self,
        *,
        app_id: str | int | None = None,
        app_secret: str | None = None,
        access_token: str | None = None,
        auth: str | None = None,
        base_url: str = PROD_URL,
        region: str | Region | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = 3,
        backoff: float = 0.5,
        user_agent: str | None = None,
        rate_limit: float | None = None,
        credentials: Credentials | None = None,
        oauth: OAuth | None = None,
        client: Any = None,
        on_token_update: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.region = region_value(region) if region is not None else None
        self._oauth = oauth
        if credentials is None:
            app_id, app_secret, access_token = _env_credentials(app_id, app_secret, access_token)
            credentials, self._oauth = _build_credentials(
                app_id=app_id,
                app_secret=app_secret,
                access_token=access_token,
                auth=auth,
                oauth=oauth,
                timeout=timeout,
                user_agent=user_agent,
                on_token_update=on_token_update,
            )
        self._credentials = credentials
        self._rate_limiter = RateLimiter(rate_limit) if rate_limit else None
        self._http = AsyncTransport(
            base_url,
            credentials=credentials,
            headers=headers,
            timeout=timeout,
            retries=retries,
            backoff=backoff,
            rate_limiter=self._rate_limiter,
            user_agent=user_agent,
            client=client,
        )
        self.auction = AsyncAuctionAPI(self)
        self.characters = AsyncCharactersAPI(self)
        self.clans = AsyncClansAPI(self)
        self.operations = AsyncOperationsAPI(self)

    @classmethod
    def demo(
        cls,
        *,
        user: bool = False,
        token: str | None = None,
        **kwargs: Any,
    ) -> "AsyncClient":
        kwargs.setdefault("base_url", DEMO_URL)
        kwargs.setdefault("access_token", token or (DEMO_USER_TOKEN if user else DEMO_APP_TOKEN))
        return cls(**kwargs)

    @classmethod
    def secret(cls, app_id: str | int, app_secret: str, **kwargs: Any) -> "AsyncClient":
        kwargs.setdefault("base_url", DEMO_URL if app_id == DEMO_APP_ID and app_secret == DEMO_APP_SECRET else PROD_URL)
        return cls(app_id=app_id, app_secret=app_secret, auth="secret", **kwargs)

    @classmethod
    def demo_secret(cls, **kwargs: Any) -> "AsyncClient":
        kwargs.setdefault("base_url", DEMO_URL)
        return cls(app_id=DEMO_APP_ID, app_secret=DEMO_APP_SECRET, auth="secret", **kwargs)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return await self._http.request(method, path, params=params, headers=headers)

    async def request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        return await self._http.request_bytes(method, path, params=params, headers=headers)

    async def regions(self) -> list[RegionInfo]:
        data = await self.request("GET", "regions")
        return [RegionInfo.from_dict(entry) for entry in _as_list(data)]

    async def emission(self, region: str | Region | None = None) -> Emission:
        resolved = _resolve_region(region, self.region)
        return Emission.from_dict(await self.request("GET", f"{resolved}/emission") or {})

    async def friends(self, character: str, *, region: str | Region | None = None) -> list[str]:
        resolved = _resolve_region(region, self.region)
        data = await self.request(
            "GET",
            f"{resolved}/friends/{quote(str(character), safe='')}",
        )
        result: list[str] = []
        for entry in _as_list(data, keys=("friends", "data")):
            if isinstance(entry, str):
                result.append(entry)
            elif isinstance(entry, dict):
                name = entry.get("name") or entry.get("username") or entry.get("character")
                if name:
                    result.append(str(name))
        return result

    async def user_info(self) -> UserInfo:
        if self._credentials is None:
            raise AuthError("user_info() requires an access token")
        token = await self._credentials.async_ensure_token()
        if not token:
            raise AuthError("user_info() requires a user access token")
        return await async_fetch_user_info(
            token, timeout=self._http.timeout, user_agent=self._http.user_agent
        )

    @property
    def credentials(self) -> Credentials | None:
        return self._credentials

    @property
    def oauth(self) -> OAuth | None:
        return self._oauth

    @property
    def access_token(self) -> str | None:
        """Cached access token (may be ``None`` until the first request)."""

        if self._credentials is None:
            return None
        return self._credentials.token

    async def fetch_access_token(self) -> str | None:
        """Return an access token, obtaining or refreshing it when needed."""

        if self._credentials is None:
            return None
        return await self._credentials.async_ensure_token()

    async def close(self) -> None:
        await self._http.aclose()
        if self._oauth is not None:
            await self._oauth.aclose()

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    def __repr__(self) -> str:
        auth = type(self._credentials).__name__ if self._credentials else "none"
        return f"AsyncClient(base_url={self._http.base_url!r}, auth={auth})"

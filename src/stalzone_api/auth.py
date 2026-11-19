"""OAuth 2.0 helpers and credential providers for the Stalzone API."""

from __future__ import annotations

import base64
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlencode

import httpx

from .constants import (
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    OAUTH_AUTHORIZE_URL,
    OAUTH_TOKEN_URL,
    OAUTH_USERINFO_URL,
)
from .errors import AuthError, JwtError, error_from_response

__all__ = [
    "AppSecretCredentials",
    "Credentials",
    "OAuth",
    "StaticTokenCredentials",
    "Token",
    "TokenCredentials",
    "UserInfo",
    "decode_jwt",
    "fetch_user_info",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def decode_jwt(token: str) -> dict[str, Any]:
    """Decode a JWT payload **without** verifying the signature.

    Stalzone tokens are RS256 JWTs. Signature verification requires EXBO's public
    keys, which are not published, so this helper is only useful for reading
    ``exp``/``sub``/``aud`` and for debugging.
    """

    try:
        payload = token.split(".")[1]
    except IndexError as exc:  # pragma: no cover - defensive
        raise JwtError("malformed JWT: expected three dot-separated parts") from exc
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + padding)
        decoded = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise JwtError("malformed JWT payload") from exc
    if not isinstance(decoded, dict):
        raise JwtError("malformed JWT payload: expected an object")
    return decoded


@dataclass
class Token:
    """An OAuth access token (optionally with a refresh token)."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
    acquired_at: datetime = field(default_factory=_utcnow)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Token":
        return cls(
            access_token=str(data.get("access_token", "")),
            token_type=str(data.get("token_type") or "Bearer"),
            expires_in=data.get("expires_in"),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
            raw=dict(data),
        )

    @property
    def payload(self) -> dict[str, Any]:
        return decode_jwt(self.access_token)

    @property
    def expires_at(self) -> datetime | None:
        try:
            exp = self.payload.get("exp")
        except JwtError:
            exp = None
        if exp is not None:
            return datetime.fromtimestamp(int(exp), tz=timezone.utc)
        if self.expires_in is not None:
            return self.acquired_at + timedelta(seconds=int(self.expires_in))
        return None

    def is_expired(self, leeway: int = 60) -> bool:
        expires_at = self.expires_at
        if expires_at is None:
            return False
        return expires_at <= _utcnow() + timedelta(seconds=leeway)

    def authorization(self) -> str:
        return f"{self.token_type or 'Bearer'} {self.access_token}"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "access_token": self.access_token,
            "token_type": self.token_type,
        }
        if self.expires_in is not None:
            data["expires_in"] = self.expires_in
        if self.refresh_token:
            data["refresh_token"] = self.refresh_token
        if self.scope is not None:
            data["scope"] = self.scope
        return data


@dataclass
class UserInfo:
    """Response of ``GET https://exbo.net/oauth/user``."""

    id: int | None = None
    uuid: str | None = None
    login: str | None = None
    display_login: str | None = None
    distributor: str | None = None
    distributor_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserInfo":
        return cls(
            id=data.get("id"),
            uuid=data.get("uuid"),
            login=data.get("login"),
            display_login=data.get("display_login"),
            distributor=data.get("distributor"),
            distributor_id=data.get("distributor_id"),
            raw=dict(data),
        )


class OAuth:
    """OAuth 2.0 client for EXBO (authorization code, refresh and client credentials)."""

    def __init__(
        self,
        client_id: str | int,
        client_secret: str = "",
        *,
        authorize_url: str = OAUTH_AUTHORIZE_URL,
        token_url: str = OAUTH_TOKEN_URL,
        userinfo_url: str = OAUTH_USERINFO_URL,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: str | None = None,
        client: httpx.Client | None = None,
        async_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.client_id = str(client_id)
        self.client_secret = client_secret
        self.authorize_endpoint = authorize_url
        self.token_url = token_url
        self.userinfo_url = userinfo_url
        self.timeout = timeout
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self._client = client
        self._async_client = async_client
        self._owns_client = client is None
        self._owns_async_client = async_client is None

    # ------------------------------------------------------------------ helpers
    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            )
        return self._client

    def _ahttp(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            )
        return self._async_client

    def _token_from_response(self, response: httpx.Response, context: str) -> Token:
        if response.status_code >= 400:
            try:
                payload: Any = response.json()
            except ValueError:
                payload = response.text
            error = error_from_response(
                response.status_code,
                payload,
                url=str(response.request.url),
                body=response.text[:2000],
            )
            raise AuthError(f"{context}: {error}") from None
        try:
            data = response.json()
        except ValueError as exc:
            raise AuthError(f"{context}: response is not valid JSON") from exc
        token = Token.from_dict(data)
        if not token.access_token:
            raise AuthError(f"{context}: response does not contain an access token")
        return token

    def _userinfo_from_response(self, response: httpx.Response) -> UserInfo:
        if response.status_code >= 400:
            try:
                payload: Any = response.json()
            except ValueError:
                payload = response.text
            raise AuthError(f"user info request failed: {error_from_response(response.status_code, payload)}")
        return UserInfo.from_dict(response.json())

    # ------------------------------------------------------------------ sync API
    def authorize_url(
        self,
        redirect_uri: str,
        *,
        state: str | None = None,
        scope: str = "",
    ) -> str:
        """Build the URL the user should be redirected to in order to grant access."""

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "response_type": "code",
        }
        if state is not None:
            params["state"] = state
        return f"{self.authorize_endpoint}?{urlencode(params)}"

    def client_credentials(self, scope: str = "") -> Token:
        """Obtain an application access token (client credentials grant)."""

        response = self._http().post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
                "scope": scope,
            },
        )
        return self._token_from_response(response, "client_credentials grant failed")

    def exchange_code(self, code: str, redirect_uri: str) -> Token:
        """Exchange an authorization code for an access/refresh token pair."""

        response = self._http().post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        return self._token_from_response(response, "authorization code exchange failed")

    def refresh(self, refresh_token: str, scope: str = "") -> Token:
        """Refresh an expired user access token."""

        response = self._http().post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": scope,
            },
        )
        return self._token_from_response(response, "token refresh failed")

    def user_info(self, access_token: str) -> UserInfo:
        """Fetch the EXBO account attached to a user access token."""

        response = self._http().get(
            self.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return self._userinfo_from_response(response)

    # ----------------------------------------------------------------- async API
    async def async_client_credentials(self, scope: str = "") -> Token:
        response = await self._ahttp().post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
                "scope": scope,
            },
        )
        return self._token_from_response(response, "client_credentials grant failed")

    async def async_exchange_code(self, code: str, redirect_uri: str) -> Token:
        response = await self._ahttp().post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        return self._token_from_response(response, "authorization code exchange failed")

    async def async_refresh(self, refresh_token: str, scope: str = "") -> Token:
        response = await self._ahttp().post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": scope,
            },
        )
        return self._token_from_response(response, "token refresh failed")

    async def async_user_info(self, access_token: str) -> UserInfo:
        response = await self._ahttp().get(
            self.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return self._userinfo_from_response(response)

    # -------------------------------------------------------------------- close
    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    async def aclose(self) -> None:
        if self._owns_async_client and self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None
        self.close()

    def __enter__(self) -> "OAuth":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    async def __aenter__(self) -> "OAuth":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()


def fetch_user_info(
    access_token: str,
    *,
    userinfo_url: str = OAUTH_USERINFO_URL,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str | None = None,
) -> UserInfo:
    """Standalone helper to fetch EXBO account info for a token."""

    oauth = OAuth("", "", userinfo_url=userinfo_url, timeout=timeout, user_agent=user_agent)
    try:
        return oauth.user_info(access_token)
    finally:
        oauth.close()


async def async_fetch_user_info(
    access_token: str,
    *,
    userinfo_url: str = OAUTH_USERINFO_URL,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str | None = None,
) -> UserInfo:
    oauth = OAuth("", "", userinfo_url=userinfo_url, timeout=timeout, user_agent=user_agent)
    try:
        return await oauth.async_user_info(access_token)
    finally:
        await oauth.aclose()


# --------------------------------------------------------------------- credentials
class Credentials:
    """Credential provider used by the HTTP transports."""

    token: str | None = None

    def headers(self) -> dict[str, str]:
        return {}

    async def async_headers(self) -> dict[str, str]:
        return self.headers()

    def ensure_token(self) -> str | None:
        return self.token

    async def async_ensure_token(self) -> str | None:
        return self.ensure_token()

    def refresh(self) -> bool:
        return False

    async def async_refresh(self) -> bool:
        return self.refresh()


class StaticTokenCredentials(Credentials):
    """Use an access token obtained elsewhere (user or application token)."""

    def __init__(self, token: str) -> None:
        self.token = token
        self._headers = {"Authorization": f"Bearer {token}"}

    def headers(self) -> dict[str, str]:
        return dict(self._headers)


class AppSecretCredentials(Credentials):
    """Secret-based authentication using ``Client-Id``/``Client-Secret`` headers."""

    def __init__(self, client_id: str | int, client_secret: str) -> None:
        self.client_id = str(client_id)
        self.client_secret = client_secret
        self._headers = {"Client-Id": self.client_id, "Client-Secret": self.client_secret}

    def headers(self) -> dict[str, str]:
        return dict(self._headers)


class TokenCredentials(Credentials):
    """Client-credentials flow with automatic caching and refresh on ``401``."""

    def __init__(
        self,
        oauth: OAuth,
        *,
        token: Token | None = None,
        refresh_token: str | None = None,
        on_update: Callable[[Token], Any] | None = None,
    ) -> None:
        self.oauth = oauth
        self._token = token
        self._refresh_token = refresh_token or (token.refresh_token if token else None)
        self._on_update = on_update
        self._lock = threading.Lock()

    @property
    def token(self) -> str | None:  # type: ignore[override]
        return self._token.access_token if self._token is not None else None

    def _store(self, token: Token) -> Token:
        self._token = token
        if token.refresh_token:
            self._refresh_token = token.refresh_token
        if self._on_update is not None:
            try:
                self._on_update(token)
            except Exception:  # pragma: no cover - user callback must not break requests
                pass
        return token

    def _ensure(self) -> Token:
        if self._token is not None and not self._token.is_expired():
            return self._token
        with self._lock:
            if self._token is not None and not self._token.is_expired():
                return self._token
            token = self.oauth.client_credentials()
            return self._store(token)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._ensure().access_token}"}

    def ensure_token(self) -> str:
        return self._ensure().access_token

    def refresh(self) -> bool:
        with self._lock:
            try:
                if self._refresh_token:
                    self._store(self.oauth.refresh(self._refresh_token))
                else:
                    self._store(self.oauth.client_credentials())
            except AuthError:
                return False
            return True

    async def async_headers(self) -> dict[str, str]:
        token = await self.async_ensure_token()
        return {"Authorization": f"Bearer {token}"}

    async def async_ensure_token(self) -> str:
        if self._token is not None and not self._token.is_expired():
            return self._token.access_token
        token = await self.oauth.async_client_credentials()
        return self._store(token).access_token

    async def async_refresh(self) -> bool:
        try:
            if self._refresh_token:
                self._store(await self.oauth.async_refresh(self._refresh_token))
            else:
                self._store(await self.oauth.async_client_credentials())
        except AuthError:
            return False
        return True

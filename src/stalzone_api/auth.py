"""Minimal OAuth 2.0 helper for EXBO accounts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx

from .constants import (
    OAUTH_AUTHORIZE_URL,
    OAUTH_TOKEN_URL,
    OAUTH_USERINFO_URL,
    USER_AGENT,
)
from .errors import error_from_response


@dataclass(slots=True)
class Token:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Token":
        return cls(
            access_token=str(data.get("access_token", "")),
            token_type=str(data.get("token_type") or "Bearer"),
            expires_in=data.get("expires_in"),
            refresh_token=data.get("refresh_token"),
            raw=data,
        )

    @property
    def authorization(self) -> str:
        return f"{self.token_type} {self.access_token}"


@dataclass(slots=True)
class UserInfo:
    id: int
    uuid: str
    login: str
    display_login: str | None
    distributor: str
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "UserInfo":
        return cls(
            id=int(data.get("id") or 0),
            uuid=str(data.get("uuid") or ""),
            login=str(data.get("login") or ""),
            display_login=data.get("display_login"),
            distributor=str(data.get("distributor") or ""),
            raw=data,
        )

    def __str__(self) -> str:
        return f"{self.login} ({self.id})"


class OAuth:
    """Authorization-code and client-credentials flows for EXBO."""

    def __init__(
        self,
        client_id: str | int,
        client_secret: str,
        *,
        redirect_uri: str = "http://localhost",
        scope: str = "",
        timeout: float = 10.0,
    ) -> None:
        self.client_id = str(client_id)
        self.client_secret = str(client_secret)
        self.redirect_uri = redirect_uri
        self.scope = scope
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    def authorize_url(self, state: str | None = None) -> str:
        """URL to send the user to in order to grant access."""

        query = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scope,
            "response_type": "code",
            "state": state,
        }
        return f"{OAUTH_AUTHORIZE_URL}?{urlencode({k: v for k, v in query.items() if v is not None})}"

    async def _token(self, payload: dict[str, Any]) -> Token:
        response = await self._http.post(
            OAUTH_TOKEN_URL,
            data={"client_id": self.client_id, "client_secret": self.client_secret, **payload},
        )
        if not response.is_success:
            raise error_from_response(response)
        return Token.from_dict(response.json())

    async def exchange_code(self, code: str) -> Token:
        """Turn an authorization code into a user access token."""

        return await self._token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
            }
        )

    async def refresh(self, refresh_token: str) -> Token:
        return await self._token(
            {"grant_type": "refresh_token", "refresh_token": refresh_token, "scope": self.scope}
        )

    async def client_credentials(self) -> Token:
        """Application access token."""

        return await self._token({"grant_type": "client_credentials", "scope": self.scope})

    async def user_info(self, token: str | Token) -> UserInfo:
        access_token = token.access_token if isinstance(token, Token) else token
        response = await self._http.get(
            OAUTH_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        if not response.is_success:
            raise error_from_response(response)
        return UserInfo.from_dict(response.json())

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "OAuth":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"OAuth(client_id={self.client_id!r})"

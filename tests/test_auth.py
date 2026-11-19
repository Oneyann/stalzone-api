"""Тесты OAuth, JWT и провайдеров авторизации."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from stalzone_api import (
    AppSecretCredentials,
    AuthError,
    OAuth,
    StaticTokenCredentials,
    Token,
    TokenCredentials,
    decode_jwt,
)
from stalzone_api.errors import JwtError


def make_jwt(payload: dict) -> str:
    def encode(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{encode({'alg': 'RS256', 'typ': 'JWT'})}.{encode(payload)}.signature"


def test_decode_jwt_without_verification():
    token = make_jwt({"sub": "1", "exp": 4827397838, "aud": "1"})

    payload = decode_jwt(token)

    assert payload["sub"] == "1"
    assert payload["aud"] == "1"


def test_decode_jwt_errors():
    with pytest.raises(JwtError):
        decode_jwt("not-a-token")
    with pytest.raises(JwtError):
        decode_jwt("a.%%%%.c")


def test_token_expiration_and_serialization():
    expired = Token(access_token=make_jwt({"exp": 1}))
    alive = Token(
        access_token=make_jwt({"exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())})
    )

    assert expired.is_expired() is True
    assert alive.is_expired() is False
    assert alive.expires_at is not None
    assert alive.authorization().startswith("Bearer ")
    assert alive.to_dict()["access_token"] == alive.access_token


def test_token_uses_expires_in_without_jwt():
    token = Token(access_token="plain-token", expires_in=3600)

    assert token.expires_at is not None
    assert token.is_expired() is False


def test_static_and_secret_credentials():
    assert StaticTokenCredentials("abc").headers() == {"Authorization": "Bearer abc"}
    assert AppSecretCredentials(123, "secret").headers() == {
        "Client-Id": "123",
        "Client-Secret": "secret",
    }


def test_authorize_url():
    oauth = OAuth(123, "secret")
    try:
        url = oauth.authorize_url("https://example.com/cb", state="state-1", scope="profile")
    finally:
        oauth.close()

    assert url.startswith("https://exbo.net/oauth/authorize?")
    assert "client_id=123" in url
    assert "state=state-1" in url
    assert "scope=profile" in url
    assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcb" in url


def test_oauth_flows(router):
    http = httpx.Client(transport=httpx.MockTransport(router))
    oauth = OAuth(123, "secret", client=http, timeout=1)
    try:
        router.add(
            "/oauth/token",
            {
                "access_token": "token-1",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "refresh-1",
            },
        )
        token = oauth.client_credentials()
        assert token.access_token == "token-1"
        assert token.refresh_token == "refresh-1"
        assert b"grant_type=client_credentials" in router.last_request.content

        router.add("/oauth/token", {"access_token": "token-2", "token_type": "Bearer"})
        token = oauth.exchange_code("code-1", "https://example.com/cb")
        assert token.access_token == "token-2"
        assert b"grant_type=authorization_code" in router.last_request.content
        assert b"code=code-1" in router.last_request.content

        router.add("/oauth/token", {"access_token": "token-3", "token_type": "Bearer"})
        token = oauth.refresh("refresh-1")
        assert token.access_token == "token-3"
        assert b"grant_type=refresh_token" in router.last_request.content

        router.add("/oauth/user", {"id": 1, "login": "player", "uuid": "u-1"})
        info = oauth.user_info("token-3")
        assert info.login == "player"
        assert router.last_request.headers["Authorization"] == "Bearer token-3"
    finally:
        oauth.close()
        http.close()


def test_oauth_error(router):
    http = httpx.Client(transport=httpx.MockTransport(router))
    oauth = OAuth(123, "secret", client=http, timeout=1)
    try:
        router.add(
            "/oauth/token",
            {"error": "invalid_client", "error_description": "bad secret"},
            status=401,
        )
        with pytest.raises(AuthError, match="invalid_client"):
            oauth.client_credentials()
    finally:
        oauth.close()
        http.close()


@pytest.mark.asyncio
async def test_async_oauth_flow(router):
    http = httpx.AsyncClient(transport=httpx.MockTransport(router))
    oauth = OAuth(123, "secret", async_client=http, timeout=1)
    try:
        router.add("/oauth/token", {"access_token": "async-token", "token_type": "Bearer"})
        token = await oauth.async_client_credentials()
        assert token.access_token == "async-token"

        router.add("/oauth/user", {"id": 2, "login": "async-player"})
        info = await oauth.async_user_info("async-token")
        assert info.login == "async-player"
    finally:
        await oauth.aclose()
        await http.aclose()


def test_token_credentials_cache_and_fetch(router):
    http = httpx.Client(transport=httpx.MockTransport(router))
    oauth = OAuth(123, "secret", client=http, timeout=1)
    token = Token(access_token="cached", expires_in=3600)
    credentials = TokenCredentials(oauth, token=token)

    try:
        assert credentials.headers() == {"Authorization": "Bearer cached"}
        assert router.requests == []

        router.add("/oauth/token", {"access_token": "fresh", "token_type": "Bearer", "expires_in": 3600})
        credentials = TokenCredentials(oauth)
        assert credentials.headers() == {"Authorization": "Bearer fresh"}
        assert len(router.requests) == 1
    finally:
        oauth.close()
        http.close()

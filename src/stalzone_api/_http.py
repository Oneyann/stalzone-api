"""HTTP transports: retries, rate limiting, authentication and error mapping."""

from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from email.utils import parsedate_to_datetime
from typing import Any, Mapping

import httpx

from .auth import Credentials
from .constants import DEFAULT_TIMEOUT, DEFAULT_USER_AGENT
from .errors import ApiError, TransportError, error_from_response

__all__ = ["AsyncTransport", "RateLimiter", "SyncTransport"]

logger = logging.getLogger("stalzone_api")

RETRY_STATUSES = (429, 500, 502, 503, 504)


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    return max(0.0, parsed.timestamp() - time.time())


def _clean_params(params: Mapping[str, Any] | None) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    if not params:
        return cleaned
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = "true" if value else "false"
        else:
            cleaned[key] = str(value)
    return cleaned


class RateLimiter:
    """Simple client-side rate limiter (minimum interval between requests)."""

    def __init__(self, rate: float, per: float = 1.0) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self.interval = per / rate
        self._next = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next = max(now, self._next) + self.interval

    async def async_acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next - now)
            self._next = now + wait + self.interval
        if wait > 0:
            await asyncio.sleep(wait)


class _TransportBase:
    def __init__(
        self,
        base_url: str,
        *,
        credentials: Credentials | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = 3,
        backoff: float = 0.5,
        max_backoff: float = 8.0,
        retry_statuses: tuple[int, ...] = RETRY_STATUSES,
        rate_limiter: RateLimiter | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.timeout = timeout
        self.retries = max(0, int(retries))
        self.backoff = backoff
        self.max_backoff = max_backoff
        self.retry_statuses = tuple(retry_statuses)
        self.rate_limiter = rate_limiter
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.default_headers: dict[str, str] = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if headers:
            self.default_headers.update({str(k): str(v) for k, v in headers.items()})

    # ------------------------------------------------------------------ helpers
    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = dict(self.default_headers)
        if self.credentials is not None:
            headers.update(self.credentials.headers())
        if extra:
            headers.update({str(k): str(v) for k, v in extra.items()})
        return headers

    async def _async_headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = dict(self.default_headers)
        if self.credentials is not None:
            headers.update(await self.credentials.async_headers())
        if extra:
            headers.update({str(k): str(v) for k, v in extra.items()})
        return headers

    def _delay(self, attempt: int, retry_after: float | None = None) -> float:
        if retry_after is not None:
            return retry_after
        base = min(self.max_backoff, self.backoff * (2**attempt))
        return base + random.uniform(0, base * 0.1)

    @staticmethod
    def _error(response: httpx.Response) -> ApiError:
        try:
            payload: Any = response.json()
        except ValueError:
            payload = response.text
        return error_from_response(
            response.status_code,
            payload,
            url=str(response.request.url),
            body=response.text[:2000],
            retry_after=_parse_retry_after(response.headers.get("Retry-After")),
        )

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(
                "response is not valid JSON",
                status=response.status_code,
                url=str(response.request.url),
                body=response.text[:2000],
            ) from exc


class SyncTransport(_TransportBase):
    """Blocking HTTP transport."""

    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.Client | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(base_url, **kwargs)
        self._client = client
        self._owns_client = client is None
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers=self.default_headers,
                follow_redirects=True,
            )

    @property
    def client(self) -> httpx.Client:
        return self._client  # type: ignore[return-value]

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return self._execute(method, path, params=params, headers=headers, raw=False)

    def request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        return self._execute(method, path, params=params, headers=headers, raw=True)

    def _execute(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
        raw: bool,
    ) -> Any:
        url = self._url(path)
        query = _clean_params(params)
        attempt = 0
        refreshed = False
        while True:
            if self.rate_limiter is not None:
                self.rate_limiter.acquire()
            try:
                response = self._client.request(
                    method,
                    url,
                    params=query or None,
                    headers=self._headers(headers),
                )
            except httpx.HTTPError as exc:
                if attempt < self.retries:
                    delay = self._delay(attempt)
                    logger.debug("request to %s failed (%s), retrying in %.2fs", url, exc, delay)
                    time.sleep(delay)
                    attempt += 1
                    continue
                raise TransportError(f"request to {url} failed: {exc}", url=url, cause=exc) from exc

            if response.status_code == 401 and not refreshed and self.credentials is not None:
                if self.credentials.refresh():
                    refreshed = True
                    logger.debug("access token refreshed after 401 from %s", url)
                    continue

            if response.status_code in self.retry_statuses and attempt < self.retries:
                delay = self._delay(attempt, _parse_retry_after(response.headers.get("Retry-After")))
                logger.debug("got %s from %s, retrying in %.2fs", response.status_code, url, delay)
                time.sleep(delay)
                attempt += 1
                continue

            if response.is_success:
                return response.content if raw else self._json(response)
            raise self._error(response)

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()

    def __enter__(self) -> "SyncTransport":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class AsyncTransport(_TransportBase):
    """Asynchronous HTTP transport."""

    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(base_url, **kwargs)
        self._client = client
        self._owns_client = client is None
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=self.default_headers,
                follow_redirects=True,
            )

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client  # type: ignore[return-value]

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return await self._execute(method, path, params=params, headers=headers, raw=False)

    async def request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        return await self._execute(method, path, params=params, headers=headers, raw=True)

    async def _execute(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
        raw: bool,
    ) -> Any:
        url = self._url(path)
        query = _clean_params(params)
        attempt = 0
        refreshed = False
        while True:
            if self.rate_limiter is not None:
                await self.rate_limiter.async_acquire()
            try:
                response = await self._client.request(
                    method,
                    url,
                    params=query or None,
                    headers=await self._async_headers(headers),
                )
            except httpx.HTTPError as exc:
                if attempt < self.retries:
                    delay = self._delay(attempt)
                    logger.debug("request to %s failed (%s), retrying in %.2fs", url, exc, delay)
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                raise TransportError(f"request to {url} failed: {exc}", url=url, cause=exc) from exc

            if response.status_code == 401 and not refreshed and self.credentials is not None:
                if await self.credentials.async_refresh():
                    refreshed = True
                    continue

            if response.status_code in self.retry_statuses and attempt < self.retries:
                delay = self._delay(attempt, _parse_retry_after(response.headers.get("Retry-After")))
                await asyncio.sleep(delay)
                attempt += 1
                continue

            if response.is_success:
                return response.content if raw else self._json(response)
            raise self._error(response)

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def __aenter__(self) -> "AsyncTransport":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

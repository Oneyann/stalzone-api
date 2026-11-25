"""Minimal async HTTP layer: one client, retries, error mapping."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping

import httpx

from .constants import DEFAULT_RETRIES, DEFAULT_TIMEOUT, USER_AGENT
from .errors import TransportError, error_from_response

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


def clean_params(params: Mapping[str, Any] | None) -> dict[str, str]:
    """Drop ``None`` values and stringify the rest for the query string."""

    cleaned: dict[str, str] = {}
    for key, value in (params or {}).items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = "true" if value else "false"
        elif hasattr(value, "isoformat"):
            cleaned[key] = value.isoformat().replace("+00:00", "Z")
        else:
            cleaned[key] = str(value)
    return cleaned


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return max(0.0, float(response.headers.get("Retry-After", "")))
    except ValueError:
        return None


class HttpClient:
    """Thin wrapper around :class:`httpx.AsyncClient`."""

    def __init__(
        self,
        base_url: str,
        headers: Mapping[str, str],
        *,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        self.retries = max(0, retries)
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json", **headers},
            timeout=timeout,
            follow_redirects=True,
        )

    async def request(self, method: str, path: str, params: Mapping[str, Any] | None = None) -> Any:
        query = clean_params(params) or None
        for attempt in range(self.retries + 1):
            try:
                response = await self._client.request(method, path.lstrip("/"), params=query)
            except httpx.HTTPError as exc:
                if attempt < self.retries:
                    await asyncio.sleep(0.5 * 2**attempt)
                    continue
                raise TransportError(f"{method} {path} failed: {exc}") from exc

            if response.status_code in RETRY_STATUSES and attempt < self.retries:
                await asyncio.sleep(_retry_after(response) or 0.5 * 2**attempt)
                continue

            if response.is_success:
                return response.json() if response.content else None
            raise error_from_response(response)

        raise AssertionError("unreachable")  # pragma: no cover

    async def close(self) -> None:
        await self._client.aclose()

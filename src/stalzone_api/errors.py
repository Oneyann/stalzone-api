"""Exceptions raised by :mod:`stalzone_api`."""

from __future__ import annotations

from typing import Any


class StalzoneError(Exception):
    """Base class for every error raised by this library."""


class TransportError(StalzoneError):
    """The request could not be completed (network problem, timeout)."""


class ApiError(StalzoneError):
    """The API returned an unsuccessful HTTP status."""

    def __init__(
        self,
        status: int,
        title: str = "",
        details: Any = None,
        *,
        url: str | None = None,
    ) -> None:
        super().__init__(status, title, details)
        self.status = status
        self.title = title
        self.details = details
        self.url = url

    def __str__(self) -> str:
        return f"{self.status} {self.title}" + (f" ({self.url})" if self.url else "")


class BadRequest(ApiError):
    """400 — one of the parameters is invalid."""


class Unauthorized(ApiError):
    """401 — the token is missing, expired or invalid."""


class Forbidden(ApiError):
    """403 — the token does not grant access to this resource."""


class NotFound(ApiError):
    """404 — the requested object does not exist."""


class RateLimited(ApiError):
    """429 — too many requests."""


class ServerError(ApiError):
    """5xx — a problem on the API side."""


_STATUS_MAP: dict[int, type[ApiError]] = {
    400: BadRequest,
    401: Unauthorized,
    403: Forbidden,
    404: NotFound,
    429: RateLimited,
}


def error_from_response(response: Any) -> ApiError:
    """Build the most specific :class:`ApiError` for an httpx response."""

    try:
        payload = response.json()
    except ValueError:
        payload = None

    title = response.reason_phrase or "HTTP error"
    details = None
    if isinstance(payload, dict):
        title = str(payload.get("title") or payload.get("message") or title)
        details = payload.get("details", payload)
    elif isinstance(payload, str) and payload.strip():
        title = payload.strip().splitlines()[0][:200]

    status = response.status_code
    cls = _STATUS_MAP.get(status) or (ServerError if status >= 500 else ApiError)
    return cls(status, title, details, url=str(response.request.url))

"""Exception hierarchy used across the package."""

from __future__ import annotations

from typing import Any


class StalzoneError(Exception):
    """Base class for every error raised by ``stalzone_api``."""


class TransportError(StalzoneError):
    """Network-level failure (DNS, timeout, connection reset, ...)."""

    def __init__(self, message: str, *, url: str | None = None, cause: BaseException | None = None) -> None:
        self.url = url
        self.cause = cause
        super().__init__(message)


class ApiError(StalzoneError):
    """Non-2xx response returned by the API."""

    status: int | None = None
    title: str | None = None
    details: Any = None
    url: str | None = None

    def __init__(
        self,
        title: str,
        *,
        status: int | None = None,
        details: Any = None,
        url: str | None = None,
        body: str | None = None,
    ) -> None:
        self.title = title
        self.status = status
        self.details = details if details is not None else {}
        self.url = url
        self.body = body
        super().__init__(str(self))

    def __str__(self) -> str:
        prefix = f"{self.status} " if self.status is not None else ""
        message = f"{prefix}{self.title or self.__class__.__name__}"
        if self.url:
            message = f"{message} ({self.url})"
        return message


class BadRequest(ApiError):
    """400 — one of the parameters is invalid."""


class Unauthorized(ApiError):
    """401 — missing, expired or unsuitable access token."""


class Forbidden(ApiError):
    """403 — the token is not allowed to perform the request."""


class NotFound(ApiError):
    """404 — the resource does not exist."""


class UnprocessableEntity(ApiError):
    """422 — the payload is syntactically valid but semantically wrong."""


class RateLimited(ApiError):
    """429 — request rate exceeded."""

    def __init__(self, *args: Any, retry_after: float | None = None, **kwargs: Any) -> None:
        self.retry_after = retry_after
        super().__init__(*args, **kwargs)


class ServerError(ApiError):
    """5xx — the API failed to process the request."""


class AuthError(StalzoneError):
    """OAuth flow failed (invalid grant, bad client credentials, ...)."""


class JwtError(StalzoneError):
    """A JWT token could not be decoded."""


class DatabaseError(StalzoneError):
    """Base class for item-database errors."""


class DatabaseNotFound(DatabaseError):
    """The requested item/icon is not present in the database."""


class DatabaseUnavailable(DatabaseError):
    """The database source could not be reached (network, GitHub rate limit, ...)."""


_STATUS_MAP: dict[int, type[ApiError]] = {
    400: BadRequest,
    401: Unauthorized,
    403: Forbidden,
    404: NotFound,
    422: UnprocessableEntity,
    429: RateLimited,
}


def error_from_response(
    status: int,
    payload: Any = None,
    *,
    url: str | None = None,
    body: str | None = None,
    retry_after: float | None = None,
) -> ApiError:
    """Build the most specific :class:`ApiError` for an HTTP status code."""

    title: str | None = None
    details: Any = {}
    if isinstance(payload, dict):
        title = payload.get("title") or payload.get("message") or payload.get("error")
        details = payload.get("details", payload)
    elif isinstance(payload, str) and payload.strip():
        title = payload.strip().splitlines()[0][:200]

    cls = _STATUS_MAP.get(status, ServerError if status >= 500 else ApiError)
    if title is None:
        title = f"HTTP {status}"
    if cls is RateLimited:
        return RateLimited(title, status=status, details=details, url=url, body=body, retry_after=retry_after)
    return cls(title, status=status, details=details, url=url, body=body)

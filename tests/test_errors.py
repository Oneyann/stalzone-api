"""Тесты исключений и маппинга HTTP-статусов."""

from __future__ import annotations

import pytest

from stalzone_api import (
    ApiError,
    BadRequest,
    Forbidden,
    NotFound,
    RateLimited,
    ServerError,
    Unauthorized,
    UnprocessableEntity,
    error_from_response,
)


def test_status_mapping():
    assert isinstance(error_from_response(400, {"title": "bad"}), BadRequest)
    assert isinstance(error_from_response(401, {"title": "auth"}), Unauthorized)
    assert isinstance(error_from_response(403, {"title": "forbidden"}), Forbidden)
    assert isinstance(error_from_response(404, {"title": "missing"}), NotFound)
    assert isinstance(error_from_response(422, {"title": "invalid"}), UnprocessableEntity)
    assert isinstance(error_from_response(500, {"title": "boom"}), ServerError)
    assert isinstance(error_from_response(418, {"title": "teapot"}), ApiError)


def test_error_fields_and_string():
    error = error_from_response(
        404,
        {"title": "Not Found", "status": 404, "details": {"item": "x"}},
        url="https://example.com/x",
    )

    assert error.status == 404
    assert error.title == "Not Found"
    assert error.details == {"item": "x"}
    assert "404" in str(error)
    assert "https://example.com/x" in str(error)


def test_error_from_plain_text():
    error = error_from_response(502, "Bad gateway\nsecond line")

    assert isinstance(error, ServerError)
    assert error.title == "Bad gateway"


def test_rate_limited_retry_after():
    error = error_from_response(429, {"title": "slow"}, retry_after=3.5)

    assert isinstance(error, RateLimited)
    assert error.retry_after == 3.5


def test_unknown_status_without_payload():
    error = error_from_response(500, None)

    assert error.title == "HTTP 500"
    assert error.details == {}


def test_api_error_defaults():
    error = ApiError("custom")

    assert error.status is None
    assert str(error) == "custom"
    with pytest.raises(ApiError):
        raise error

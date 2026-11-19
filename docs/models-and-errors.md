# Models, pagination, and errors

## Typed models

Successful API calls return typed dataclasses rather than raw dictionaries.
Models are available from the top-level `stalzone_api` package. Important
families include:

- Common: `Region`, `Realm`, `Alliance`, `RegionInfo`.
- Characters: `Character`, `CharacterProfile`, `CharacterInformation`,
  `CharacterClan`, `CharacterStat`, `StatType`.
- Clans: `Clan`, `ClanList`, `ClanMember`, `ClanRank`.
- Auctions: `Lot`, `LotPage`, `PriceEntry`, `PricePage`, `PriceSummary`.
- Operations: `OperationSession`, `SessionParticipant`, `SessionPage`.
- Emission: `Emission`.

Timestamps are parsed into timezone-aware `datetime` values when the response
contains a valid timestamp. Fields not represented by a known dataclass
attribute are generally retained in an `extra` mapping, allowing callers to
inspect fields introduced by the upstream API.

`Lot.price` is the current bid if present, otherwise the starting price;
`Lot.total_price` multiplies that price by the lot amount. Pages are
iterable, have a length, and support indexing.

## Pagination

Page objects expose `items`, `total`, `offset`, `next_offset`, and `is_last`.
Auction page items are `lots` or `prices`; clan and session page data are
available as `data` and `sessions` respectively.

Use low-level `iter_*` helpers to avoid manually maintaining offsets:

```python
for lot in client.auction.iter_lots("zyv9", page_size=100, limit=500):
    ...
```

Available automatic iterators:

- Auctions: `iter_lots`, `iter_history`.
- Clans: `iter_all`.
- Operations: `iter_sessions`.

They stop when the page reports the end of the result set, an empty page is
returned, or the optional total `limit` is reached. The simple facade exposes
`auction(...).all_lots(...)` as a list convenience, not a streaming iterator.

## HTTP behavior

The HTTP transport:

- Sends `User-Agent` and `Accept: application/json` headers by default.
- Omits `None` query parameters and serializes booleans as lowercase
  `true`/`false`.
- Retries network errors and HTTP `429`, `500`, `502`, `503`, and `504` up to
  `retries` times, with exponential backoff and jitter.
- Honors a valid `Retry-After` value.
- Attempts one credential refresh after a `401` response when supported by
  the configured provider.
- Parses successful responses as JSON, or returns bytes via `request_bytes`.

Retries apply at the transport layer to any HTTP method submitted through
`request()`. See the [analysis](analysis.md) for the implication when using
non-idempotent methods.

## Exception hierarchy

All package exceptions derive from `StalzoneError`.

| Exception | Meaning |
| --- | --- |
| `TransportError` | Network failure after retries are exhausted; includes `url` and `cause` |
| `ApiError` | Other non-success API response; includes `status`, `title`, `details`, `url`, and `body` |
| `BadRequest` | HTTP 400 |
| `Unauthorized` | HTTP 401 |
| `Forbidden` | HTTP 403 |
| `NotFound` | HTTP 404 |
| `UnprocessableEntity` | HTTP 422 |
| `RateLimited` | HTTP 429; may include `retry_after` |
| `ServerError` | HTTP 5xx |
| `AuthError` | OAuth or credential operation failed |
| `JwtError` | JWT payload could not be decoded |
| `DatabaseError` | Base item database failure |
| `DatabaseNotFound` | Requested item or icon is missing |
| `DatabaseUnavailable` | Database source is unavailable or rate-limited |

Example:

```python
from stalzone_api import ApiError, RateLimited, TransportError

try:
    ...
except RateLimited as exc:
    print(exc.retry_after)
except TransportError as exc:
    print(exc.url, exc.cause)
except ApiError as exc:
    print(exc.status, exc.details)
```

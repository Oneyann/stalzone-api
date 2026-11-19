# Architecture and code analysis

This page records the package structure and behavior review for version
`0.1.0`. It is a code-reading analysis, not a guarantee about upstream API
behavior. Findings are separated from documented behavior and should be
rechecked against later versions.

## Architecture

```text
AppClient / SyncAppClient
            |
       Client / AsyncClient
       /       |        \
  resources   auth     HTTP transport
       |                  |
     models          httpx / retries

Database
   |-- GitHubProvider -- DiskCache
   |-- LocalProvider
   |-- ItemStore / ItemIndex
   `-- IconStore
```

- `simple.py` is the convenience facade. It selects demo, token, or secret
  auth and delegates to the low-level client.
- `client.py` defines sync/async endpoint resources and maps JSON responses
  into model objects.
- `auth.py` handles OAuth token operations and credential providers.
- `_http.py` centralizes URL construction, headers, rate limiting, retries,
  JSON parsing, and HTTP-status-to-exception conversion.
- `models/` contains typed API responses and tolerant parsing of unknown
  fields.
- `database/` provides GitHub/local file sources, disk caching, item parsing,
  lookup/search indexes, and icon access.
- `tests/` covers unit, mock-transport, auth, models, pagination, and opt-in
  integration behavior.

## Review findings

### Medium: synchronous price summary can fetch the first page twice

`src/stalzone_api/client.py`, `AuctionAPI.price_summary` first fetches history
with a cap of 200, then when `limit > 200` replaces that result with
`iter_history(...)`, which starts again from offset zero. This duplicates
work/network traffic for the common `limit > 200` case. The async
implementation does not make this initial extra request. The resulting
summary data should still cover the requested history limit, but the
sync/async request counts differ.

### Medium: transport retries all HTTP methods

`src/stalzone_api/_http.py`, `SyncTransport._execute` and
`AsyncTransport._execute` retry network failures and configured transient
statuses without checking the HTTP method. This is appropriate for GET-like
operations, but raw `request()` supports arbitrary methods. A POST or another
non-idempotent operation could be applied more than once if the server
processed it but the response was lost, or returned a retryable status after
partial processing. Callers should avoid relying on automatic retries for
non-idempotent operations.

### Low: unexpected list payloads may be interpreted permissively

`src/stalzone_api/client.py`, `_as_list` looks first for known list-valued
keys, then returns the first list found anywhere in a dictionary. This makes
the client tolerant of response wrappers, but a changed or unexpected
response schema can yield an unrelated list rather than an explicit parse
failure. Review such responses when upstream schemas change.

### Low: pagination stops based on server totals and empty pages

`src/stalzone_api/pagination.py`, `paginate` stops on an empty page or when
`offset + len(items) >= total`. If the upstream total is missing, stale, or
inconsistent, iteration may stop earlier than expected (or continue until an
empty page). The current models normalize absent totals to zero, which makes
the `is_last` calculation especially dependent on the API returning a valid
total.

### Security note: JWT decoding does not verify signatures

`src/stalzone_api/auth.py`, `decode_jwt` decodes only the payload. Its
docstring correctly says it does not verify signatures. Never use values
returned by this helper as proof of identity, authorization, or token
validity.

## Positive design properties

- Sync and async transports and resource classes are intentionally parallel.
- Context manager support makes HTTP resource cleanup straightforward.
- `httpx` injection and mock transports make unit tests independent of the
  live service.
- API error subclasses preserve status and response details.
- Unknown API fields and unknown item database block/element kinds are
  retained rather than discarded.
- GitHub-backed database reads use caching, ETags, and stale JSON fallback;
  the archive extractor validates member paths before extraction.
- Tests are opt-in for live API calls; ordinary unit test runs do not require
  network access.

## Verification performed for this review

- `python -m pytest -q`: **85 passed, 2 skipped**.
- The skipped tests are live integration tests and require
  `STALZONE_RUN_INTEGRATION=1`.
- No code behavior was changed as part of writing this documentation.

## Suggested follow-up

1. Add a regression test for sync/async `price_summary` request counts when
   the requested limit exceeds 200.
2. Consider allowing retries only for safe/idempotent methods by default, or
   making retry behavior configurable per request.
3. Add malformed/unexpected API response tests around `_as_list` and
   pagination totals.
4. Keep the sync and async implementations covered by paired tests whenever
   endpoint behavior changes.

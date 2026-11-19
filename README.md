# stalzone-api

The simplest Python client for the **Stalzone API** (Stalcraft) and the official
**items database**. One import, one client, no boilerplate.

```bash
pip install stalzone-api
```

## 30-second start

```python
import asyncio
from stalzone_api import AppClient

async def main():
    async with AppClient() as client:          # env vars, or the demo server
        print(await client.emission())
        print(await client.profile("ZIV"))
        print(await client.auction("zyv9").lots(limit=3))

asyncio.run(main())
```

`AppClient()` reads credentials from the environment; if none are set it
automatically uses the public demo server. It always works.

No `async`? Use the identical synchronous facade:

```python
from stalzone_api import SyncAppClient

with SyncAppClient() as client:
    print(client.emission())
    print(client.profile("ZIV"))
    print(client.auction("zyv9").lots(limit=3))
```

Objects know how to print themselves:

```
Emission: inactive, last ended 2026-11-19 10:24 UTC
ZIV · 105 stats
3 of 93
zyv9: 100 x 1 (ends 2026-11-19 22:50)
zyv9: 100 x 1 (ends 2026-11-21 10:49)
zyv9: 1 x 1 (ends 2026-11-21 10:44)
```

## Authentication

| Variable | Meaning |
| --- | --- |
| `STALZONE_APP_ID` (or `CLIENT_ID`) | application id (`Client-Id`) |
| `STALZONE_APP_SECRET` (or `CLIENT_SECRET`) | application secret (`Client-Secret`) |
| `STALZONE_ACCESS_TOKEN` (or `APP_TOKEN`) | ready bearer token — wins over id/secret |

Explicit values work too:

```python
AppClient(client_id=123, client_secret="…", region="RU")
AppClient(token="eyJ0eXAiOiJKV1Qi…")
AppClient.demo()                       # public demo server
```

Region defaults to `RU`; pass `region="EU"` or `region=Region.EU` to change it.

## Everything the simple client can do

```python
await client.regions()                          # list of regions
await client.emission()                         # emission status
await client.profile("ZIV")                     # public profile by name
await client.profile("uuid…", uuid=True)        # by uuid
await client.characters()                       # characters visible to the token
await client.friends("ZIV")                     # friend names
await client.clans(limit=20)                    # clan list
await client.sessions(limit=20, map="big_cleanup")
await client.request("GET", "RU/regions")       # any raw endpoint

auction = client.auction("zyv9")
await auction.lots(limit=20, sort="current_price", order="asc")
await auction.history(limit=50)
await auction.summary(limit=200)                # min / mean / median / max
await auction.all_lots()                        # every page, automatically
```

`SyncAppClient` has the same methods without `await`.

## Items database

```python
from stalzone_api import Database

db = Database("ru").sync()          # one request: download a full offline snapshot
db = Database.local("./stalzone-database")   # or use your own local clone

item = db.items.get("knmpy")
print(item.name.ru, item.weight, item.damage)

for found in db.items.search("винторез", lang="ru", limit=5):
    print(found.id, found.name.en)

png = db.icons.bytes("knmpy")
```

On-demand GitHub loading also works (`Database("ru")`), but the snapshot or a
local clone is recommended for search and bulk access. GitHub responds with
`403` when the unauthenticated rate limit is exhausted; set
`STALZONE_GITHUB_TOKEN`, use `.sync()` once, or call `Database.local(...)`.

## Advanced API

The low-level clients are still available when you need full control:
`Client` and `AsyncClient` expose resources `auction`, `characters`, `clans`
and `operations`, plus `regions()`, `emission()`, `friends()`, `user_info()`
and raw `request()` / `request_bytes()`.

```python
from stalzone_api import Client

with Client(app_id=123, app_secret="…", region="EU") as client:
    page = client.auction.lots("y1q9", limit=20)
    for lot in page:
        print(lot.price, lot.end_time)
    for session in client.operations.iter_sessions(map="shock_therapy"):
        print(session.id, len(session.participants))
```

Features of the core layer:

* both sync and async clients with the same API;
* automatic pagination via `iter_lots`, `iter_history`, `clans.iter_all`,
  `operations.iter_sessions`; pages expose `items`, `total`, `offset`,
  `next_offset`, `is_last`;
* retries on `429`/`5xx` and network errors with exponential backoff and
  `Retry-After`, optional `rate_limit=`;
* typed dataclass models; unknown API fields stay in `.extra`, unknown item
  blocks/elements become `RawBlock` / `RawElement`;
* OAuth 2.0 helpers: `OAuth(...).authorize_url()`, `exchange_code()`,
  `refresh()`, `client_credentials()`, `user_info()`;
* precise errors: `BadRequest`, `Unauthorized`, `Forbidden`, `NotFound`,
  `RateLimited`, `ServerError`, `TransportError`;
* `auth="token"` for OAuth client credentials, `Client.demo(user=True)` for the
  demo server, percent-encoded names and int64 session ids handled for you.

Client options: `base_url`, `region`, `timeout`, `retries`, `backoff`,
`user_agent`, `rate_limit`, `headers`. A `User-Agent` is always sent —
Cloudflare rejects requests without it.

## Tests

```bash
python -m pip install -e ".[test]"
python -m pytest -q
```

No network is needed (`httpx.MockTransport`). Live requests are opt-in:

```bash
$env:STALZONE_RUN_INTEGRATION="1"
python -m pytest -m integration
```

## Documentation

The detailed guides are in [`docs/`](docs/index.md):

* [Installation and supported Python versions](docs/installation.md)
* [Clients and API endpoint reference](docs/clients-and-api.md)
* [Authentication and OAuth](docs/authentication.md)
* [Items database](docs/database.md)
* [Models, pagination, and errors](docs/models-and-errors.md)
* [Architecture and code analysis](docs/analysis.md)
* [Development and release](docs/development.md)

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md).

## Disclaimer

Unofficial library. Stalcraft, Stalzone and the items database belong to EXBO.
MIT license.

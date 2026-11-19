# Clients and API reference

## Choosing a client

| Client | Style | Intended use |
| --- | --- | --- |
| `AppClient` | Async facade | Common endpoints with compact method calls |
| `SyncAppClient` | Sync facade | The same common operations without `await` |
| `AsyncClient` | Async resource client | Full resource API, custom transports and credentials |
| `Client` | Sync resource client | Synchronous equivalent of `AsyncClient` |

Always close clients so their HTTP connections are released. The facades and
low-level clients support context managers:

```python
async with AppClient(region="EU") as client:
    profile = await client.profile("ZIV")
```

```python
with SyncAppClient(region="EU") as client:
    profile = client.profile("ZIV")
```

For externally managed `httpx` clients, pass `client=...` to a low-level
client. The library does not close an HTTP client it did not create.

## Simple facade

`AppClient` and `SyncAppClient` default to region `RU`. Pass `region="EU"` or
`region=Region.EU` to change it. The methods have the same names and return
the same model types; async methods require `await`.

```python
async with AppClient() as client:
    print(await client.regions())
    print(await client.emission())
    print(await client.profile("ZIV"))
    print(await client.profile("character-uuid", uuid=True))
    print(await client.characters())
    print(await client.friends("ZIV"))
    print(await client.clans(limit=20, offset=0))
    print(await client.sessions(limit=20, map="big_cleanup"))

    auction = client.auction("zyv9")
    print(await auction.lots(limit=20, sort="current_price", order="asc"))
    print(await auction.history(limit=50))
    print(await auction.summary(limit=200))
    print(await auction.all_lots(limit=500))
```

Facade endpoint methods:

| Method | Result / notes |
| --- | --- |
| `regions()` | Available regions |
| `emission(region=None)` | Current and previous emission times |
| `profile(character, uuid=False, region=None)` | Public profile by name or UUID |
| `characters(region=None)` | Characters available to the current token |
| `friends(character, region=None)` | Friend names; requires an appropriate user token |
| `clans(limit=20, offset=0, region=None)` | One page of clans |
| `sessions(limit=20, region=None, **filters)` | One page of operation sessions |
| `auction(item_id)` | Returns an auction helper bound to an item ID |
| `request(method, path, **kwargs)` | Raw API request for an uncovered endpoint |

Auction helper methods are `lots`, `history`, `summary`, and `all_lots`.
`lots` accepts `limit`, `offset`, `sort`, `order`, and `region`; `history`
accepts `limit`, `offset`, and `region`. The facade's `all_lots` returns a
list and supports an optional maximum `limit`.

Session filters accepted by the facade include `username`, `map`, `after`,
`before`, `offset`, `sort`, and `order` (as supported by the underlying
endpoint).

## Low-level resource clients

`Client` and `AsyncClient` expose:

- `auction`: `lots`, `history`, `iter_lots`, `iter_history`,
  `price_summary`.
- `characters`: `list`, `profile`, `profile_by_uuid`.
- `clans`: `list`, `iter_all`, `info`, `members`.
- `operations`: `sessions`, `iter_sessions`.
- Client methods `regions`, `emission`, `friends`, `user_info`, `request`,
  and `request_bytes`.

The methods are synchronous on `Client` and awaitable on `AsyncClient`.
Iterators on `Client` are ordinary iterators; async variants are asynchronous
iterators.

```python
from stalzone_api import Client

with Client(app_id="your-id", app_secret="your-secret", region="EU") as client:
    for lot in client.auction.iter_lots("zyv9", page_size=100, limit=500):
        print(lot.price, lot.end_time)
```

## Low-level configuration

Both low-level clients accept:

| Option | Meaning |
| --- | --- |
| `app_id`, `app_secret` | Application credentials; must be provided together |
| `access_token` | Existing bearer token |
| `auth` | `"secret"` (default) or `"token"` / `"oauth"` / `"client_credentials"` |
| `base_url` | API root; defaults to the production endpoint |
| `region` | Default region; if omitted, region-specific calls need a region |
| `timeout` | HTTP timeout in seconds |
| `retries`, `backoff` | Retry count and exponential-backoff base |
| `rate_limit` | Client-side maximum requests per second |
| `user_agent`, `headers` | Request identification and extra default headers |
| `credentials`, `oauth` | Custom credential provider or OAuth helper |
| `client` | Injected `httpx.Client` / `httpx.AsyncClient` |
| `on_token_update` | Callback invoked with refreshed OAuth `Token` values |

`Client.demo()` and `AsyncClient.demo()` target the public demo server.
`Client.secret(...)` and its async counterpart are convenience constructors
for secret-header auth; `demo_secret()` uses the documented demo credentials.

## Endpoint details

The resource client builds these paths (where `{region}` is typically `RU` or
`EU`):

| Operation | HTTP path | Common query parameters |
| --- | --- | --- |
| Regions | `/regions` | — |
| Emission | `/{region}/emission` | — |
| Character list | `/{region}/characters` | — |
| Profile by name | `/{region}/character/by-name/{name}/profile` | — |
| Profile by UUID | `/{region}/character/by-uuid/{uuid}/profile` | — |
| Friends | `/{region}/friends/{character}` | — |
| Clan list | `/{region}/clans` | `offset`, `limit` |
| Clan info | `/{region}/clan/{clan_id}/info` | — |
| Clan members | `/{region}/clan/{clan_id}/members` | — |
| Auction lots | `/{region}/auction/{item}/lots` | `offset`, `limit`, `sort`, `order`, `additional` |
| Auction history | `/{region}/auction/{item}/history` | `offset`, `limit`, `additional` |
| Operation sessions | `/{region}/operations/sessions` | `username`, `limit`, `offset`, `after`, `before`, `map`, `sort`, `order` |

Path components are percent-encoded by the client. `request()` and
`request_bytes()` accept an API-relative path or an absolute HTTP(S) URL.
The latter returns raw response bytes; normal `request()` parses JSON.

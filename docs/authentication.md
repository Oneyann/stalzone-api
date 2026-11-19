# Authentication and OAuth

## Credential selection

The simple facades look for credentials in this order:

1. Explicit constructor arguments.
2. Environment variables.
3. Public demo server, unless `demo=False` was requested.

Environment variable aliases:

| Purpose | Preferred variable | Alias |
| --- | --- | --- |
| Application ID | `STALZONE_APP_ID` | `CLIENT_ID` |
| Application secret | `STALZONE_APP_SECRET` | `CLIENT_SECRET` |
| Access token | `STALZONE_ACCESS_TOKEN` | `APP_TOKEN` |

For the low-level `Client` and `AsyncClient`, the documented environment
lookup is `STALZONE_APP_ID`, `STALZONE_APP_SECRET`, and
`STALZONE_ACCESS_TOKEN`. An explicit access token takes precedence over the
other values in the simple facade. Keep production credentials in a secret
manager or environment configuration; never commit them.

To require configured credentials rather than silently falling back to the
demo:

```python
client = AppClient(demo=False)
```

## Authentication modes

### Secret headers

The low-level client defaults to application secret headers when both
`app_id` and `app_secret` are provided:

```python
client = Client(app_id="123", app_secret="secret", region="EU")
```

Requests carry `Client-Id` and `Client-Secret` headers. This is the default
`auth="secret"` mode.

### Bearer token

Supply a token obtained separately:

```python
client = AsyncClient(access_token="access-token", region="RU")
```

The token is sent as an `Authorization: Bearer ...` header. The simple facade
accepts the token as `AppClient(token=...)`.

### OAuth client credentials

Use `auth="token"` with application ID and secret to request an application
token and refresh it automatically when needed:

```python
client = AsyncClient(
    app_id="123",
    app_secret="secret",
    auth="token",
    region="RU",
)
```

The low-level clients also expose their `oauth` helper and
`fetch_access_token()` on `AsyncClient`. The synchronous `access_token`
property may obtain a token when needed; the async property's value is the
cached token, so use `await client.fetch_access_token()` to ensure one has
been obtained.

## Authorization-code flow

The `OAuth` class provides URL construction, code exchange, refresh,
client-credentials, and user-info operations:

```python
from stalzone_api import OAuth

oauth = OAuth("client-id", "client-secret")
url = oauth.authorize_url(
    "https://your-app.example/callback",
    state="random-csrf-token",
    scope="",
)
# Redirect the user to `url`; validate returned state in your application.
token = oauth.exchange_code(
    "authorization-code",
    "https://your-app.example/callback",
)
print(token.access_token)
```

`OAuth` has matching `async_*` methods for asynchronous applications:
`async_exchange_code`, `async_refresh`, `async_client_credentials`, and
`async_user_info`. `Token` exposes `access_token`, `token_type`,
`expires_in`, `refresh_token`, `scope`, `expires_at`, `is_expired()`,
`authorization()`, and `to_dict()`.

State generation, callback routing, state validation, and secure storage of
tokens are application responsibilities. The helper builds the authorization
URL but does not run a browser or callback server.

## Token inspection warning

`decode_jwt()` and `Token.payload` decode a JWT payload without validating its
signature. Use them only to inspect claims for debugging; decoded claims must
not be trusted for authorization or security decisions.

## User-only endpoints

Some endpoints require a suitable user token rather than application
credentials, including listing the token owner's characters, friends, clan
members, and account `user_info()`. The API remains authoritative about
permissions; expect `Unauthorized` or `Forbidden` if the token is absent or
does not have the required access.

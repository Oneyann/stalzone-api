# stalzone-api documentation

`stalzone-api` is a typed Python client for the Stalzone API for Stalcraft and
the official EXBO item database. It offers matching synchronous and
asynchronous interfaces, a small facade for common use, and lower-level
clients when more control is needed.

## Guides

1. [Installation](installation.md)
2. [Clients and endpoint reference](clients-and-api.md)
3. [Authentication and OAuth](authentication.md)
4. [Official item database](database.md)
5. [Models, pagination, and errors](models-and-errors.md)
6. [Architecture and code analysis](analysis.md)
7. [Development, tests, and releases](development.md)

## At a glance

```python
import asyncio
from stalzone_api import AppClient


async def main():
    async with AppClient() as client:
        profile = await client.profile("ZIV")
        print(profile)
        lots = await client.auction("zyv9").lots(limit=5)
        for lot in lots:
            print(lot)


asyncio.run(main())
```

The facade uses credentials supplied to its constructor or environment. If
none are provided, it uses the published demo API credentials. For production
applications, use credentials issued for your application and keep secrets
outside source control.

## Scope and disclaimer

This is an unofficial client library. Stalcraft, Stalzone, the API, and the
official item database are operated/owned by EXBO and their respective
rights-holders. API availability, response schemas, and rate limits are
controlled by those services, not by this package.

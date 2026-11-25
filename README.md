# stalzone-api

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://pypi.org/project/stalzone-api/)

Асинхронный Python-клиент для API Stalzone (Stalcraft).

```bash
pip install stalzone-api
```

## Быстрый старт

```python
import asyncio
from stalzone_api import AppClient

async def main():
    async with AppClient() as client:
        print(await client.emission())
        print(await client.profile("ZIV"))
        print(await client.auction("y1q9").lots(limit=3))

asyncio.run(main())
```

## Авторизация

| Переменная | Назначение |
| --- | --- |
| `STALZONE_APP_ID` | ID приложения (`Client-Id`) |
| `STALZONE_APP_SECRET` | Секрет приложения (`Client-Secret`) |
| `STALZONE_ACCESS_TOKEN` | Готовый токен, приоритетнее ID и секрета |

Можно передать явно: `AppClient(client_id=1454, client_secret="…")` или `AppClient(token="…")`.
Если учётные данные не заданы, используется публичный демо-сервер. Принудительно: `AppClient(demo=True)`.

## Методы

```python
await client.regions()
await client.emission()
await client.profile("ZIV")
await client.characters()
await client.friends("ZIV")
await client.clans(limit=20)
await client.clan(clan_id)
await client.clan_members(clan_id)
await client.sessions(map="operation_bigcleanup")
await client.auction("y1q9").lots(limit=20, sort="current_price", order="asc")
await client.auction("y1q9").history(limit=50)
await client.request("GET", "RU/emission")
```

Регион по умолчанию — `RU`. Чтобы сменить, передайте `region="EU"` или `Region.EU`.
Методы `characters`, `friends` и `clan_members` требуют токен пользователя.

## Токен пользователя (OAuth)

```python
from stalzone_api import OAuth

oauth = OAuth(client_id=1454, client_secret="…", redirect_uri="https://example.com/code")
print(oauth.authorize_url(state="xyz"))
token = await oauth.exchange_code(code)
client = AppClient(token=token.access_token)
```

Ошибки наследуют `StalzoneError`: `NotFound`, `Unauthorized`, `RateLimited`, `TransportError` и другие.

Неофициальная библиотека. Stalcraft и Stalzone принадлежат EXBO.

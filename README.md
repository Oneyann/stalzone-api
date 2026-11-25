# stalzone-api

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://pypi.org/project/stalzone-api/)

Асинхронный Python-клиент для API Stalzone (Stalcraft). Один импорт, один клиент
— без лишнего кода.

```bash
pip install stalzone-api
```

## Быстрый старт

```python
import asyncio
from stalzone_api import AppClient

async def main():
    async with AppClient() as client:          # переменные окружения или демо-сервер
        print(await client.emission())
        print(await client.profile("ZIV"))
        print(await client.auction("y1q9").lots(limit=3))

asyncio.run(main())
```

## Авторизация

| Переменная | Назначение |
| --- | --- |
| `STALZONE_APP_ID` | идентификатор приложения (`Client-Id`) |
| `STALZONE_APP_SECRET` | секрет приложения (`Client-Secret`) |
| `STALZONE_ACCESS_TOKEN` | готовый токен — имеет приоритет над id/secret |

Можно передать значения явно:
`AppClient(client_id=1454, client_secret="…")`, `AppClient(token="eyJ0eXAi…")`.
Если учётные данные не заданы, автоматически используется публичный демо-сервер
(`AppClient(demo=True)` включает его принудительно).

## Методы

```python
await client.regions()
await client.emission()
await client.profile("ZIV")              # uuid=True — поиск по UUID
await client.characters()                # нужен токен пользователя
await client.friends("ZIV")              # нужен токен пользователя
await client.clans(limit=20)
await client.clan(clan_id)
await client.clan_members(clan_id)       # нужен токен пользователя
await client.sessions(map="operation_bigcleanup")
await client.auction("y1q9").lots(limit=20, sort="current_price", order="asc")
await client.auction("y1q9").history(limit=50)
await client.request("GET", "RU/emission")   # любая конечная точка
```

Регион по умолчанию — `RU`; передайте `region="EU"` или `Region.EU` в любой метод.

## Токены пользователя (OAuth)

```python
from stalzone_api import OAuth

oauth = OAuth(client_id=1454, client_secret="…", redirect_uri="https://example.com/code")
print(oauth.authorize_url(state="xyz"))   # перенаправьте пользователя по этому адресу
token = await oauth.exchange_code(code)   # затем передайте токен клиенту
client = AppClient(token=token.access_token)
```

Ошибки — подклассы `StalzoneError`: `NotFound`, `Unauthorized`, `RateLimited`,
`TransportError` и другие.

Неофициальная библиотека. Stalcraft и Stalzone принадлежат EXBO.

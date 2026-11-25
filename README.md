# stalzone-api

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://pypi.org/project/stalzone-api/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Асинхронный Python-клиент для API Stalzone (Stalcraft). Один импорт, один клиент.

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

## Методы

| Метод | Назначение |
| --- | --- |
| `regions()` | Список регионов |
| `emission()` | Текущий выброс |
| `profile(name, uuid=False)` | Профиль игрока по нику или UUID |
| `characters()` | Персонажи пользователя (нужен токен) |
| `friends(name)` | Друзья игрока (нужен токен) |
| `clans(limit=...)` | Список кланов |
| `clan(clan_id)` | Информация о клане |
| `clan_members(clan_id)` | Участники клана (нужен токен) |
| `sessions(map=...)` | Игровые сессии |
| `auction(item_id).lots(...)` | Лоты аукциона |
| `auction(item_id).history(...)` | История аукциона |
| `request(method, path)` | Любая конечная точка API |

Регион по умолчанию — `RU`. Чтобы сменить, передайте `region="EU"` или `Region.EU`.

## Авторизация

| Переменная | Назначение |
| --- | --- |
| `STALZONE_APP_ID` | ID приложения (`Client-Id`) |
| `STALZONE_APP_SECRET` | Секрет приложения (`Client-Secret`) |
| `STALZONE_ACCESS_TOKEN` | Готовый токен, приоритетнее ID и секрета |

Если учётные данные не заданы, используется публичный демо-сервер. Принудительно: `AppClient(demo=True)`.

## Токен пользователя (OAuth)

```python
from stalzone_api import OAuth

oauth = OAuth(client_id=1454, client_secret="…", redirect_uri="https://example.com/code")
print(oauth.authorize_url(state="xyz"))
token = await oauth.exchange_code(code)
client = AppClient(token=token.access_token)
```

## Тесты

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Примечания

- Ошибки наследуют `StalzoneError`: `NotFound`, `Unauthorized`, `RateLimited`, `TransportError` и другие.

Неофициальная библиотека. Stalcraft и Stalzone принадлежат EXBO.

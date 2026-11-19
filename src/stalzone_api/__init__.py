"""``stalzone_api`` — an insanely simple Python client for Stalzone (Stalcraft).

Quick start::

    import asyncio
    from stalzone_api import AppClient

    async def main():
        async with AppClient() as client:      # env vars, or the demo server
            print(await client.emission())
            print(await client.profile("ZIV"))
            print(await client.auction("zyv9").lots(limit=3))

    asyncio.run(main())

The lower-level :class:`Client` / :class:`AsyncClient` and :class:`Database`
remain available for advanced use.
"""

from ._version import __version__
from .auth import (
    AppSecretCredentials,
    Credentials,
    OAuth,
    StaticTokenCredentials,
    Token,
    TokenCredentials,
    UserInfo,
    async_fetch_user_info,
    decode_jwt,
    fetch_user_info,
)
from .client import AsyncClient, Client
from .constants import (
    DATABASE_REF,
    DATABASE_REPO,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    DEMO_APP_ID,
    DEMO_APP_SECRET,
    DEMO_APP_TOKEN,
    DEMO_URL,
    DEMO_USER_TOKEN,
    OAUTH_AUTHORIZE_URL,
    OAUTH_TOKEN_URL,
    OAUTH_USERINFO_URL,
    PROD_URL,
)
from .database import (
    Database,
    GitHubProvider,
    IconStore,
    Item,
    ItemStore,
    LocalProvider,
    Provider,
    Text,
    default_cache_dir,
)
from .database.items import (
    Block,
    DamageBlock,
    Element,
    Formatted,
    GroupedBlock,
    ItemElement,
    ItemStatus,
    KeyValueElement,
    ListBlock,
    NumericElement,
    PriceElement,
    RangeElement,
    RawBlock,
    RawElement,
    TextBlock,
    TextElement,
)
from .errors import (
    ApiError,
    AuthError,
    BadRequest,
    DatabaseError,
    DatabaseNotFound,
    DatabaseUnavailable,
    Forbidden,
    JwtError,
    NotFound,
    RateLimited,
    ServerError,
    StalzoneError,
    TransportError,
    Unauthorized,
    UnprocessableEntity,
    error_from_response,
)
from .models import (
    Alliance,
    Character,
    CharacterClan,
    CharacterInformation,
    CharacterProfile,
    CharacterStat,
    Clan,
    ClanList,
    ClanMember,
    ClanRank,
    Emission,
    Lot,
    LotPage,
    OperationSession,
    PriceEntry,
    PricePage,
    PriceSummary,
    Realm,
    Region,
    RegionInfo,
    SessionPage,
    SessionParticipant,
    StatType,
)
from .pagination import paginate
from .simple import AppClient, Auction, SyncAppClient, SyncAuction

__all__ = [
    "__version__",
    # simple facade
    "AppClient",
    "SyncAppClient",
    "Auction",
    "SyncAuction",
    # clients
    "AsyncClient",
    "Client",
    # auth
    "AppSecretCredentials",
    "Credentials",
    "OAuth",
    "StaticTokenCredentials",
    "Token",
    "TokenCredentials",
    "UserInfo",
    "async_fetch_user_info",
    "decode_jwt",
    "fetch_user_info",
    # constants
    "DATABASE_REF",
    "DATABASE_REPO",
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
    "DEMO_APP_ID",
    "DEMO_APP_SECRET",
    "DEMO_APP_TOKEN",
    "DEMO_URL",
    "DEMO_USER_TOKEN",
    "OAUTH_AUTHORIZE_URL",
    "OAUTH_TOKEN_URL",
    "OAUTH_USERINFO_URL",
    "PROD_URL",
    # database
    "Database",
    "GitHubProvider",
    "IconStore",
    "Item",
    "ItemStore",
    "LocalProvider",
    "Provider",
    "Text",
    "default_cache_dir",
    "Block",
    "DamageBlock",
    "Element",
    "Formatted",
    "GroupedBlock",
    "ItemElement",
    "ItemStatus",
    "KeyValueElement",
    "ListBlock",
    "NumericElement",
    "PriceElement",
    "RangeElement",
    "RawBlock",
    "RawElement",
    "TextBlock",
    "TextElement",
    # errors
    "ApiError",
    "AuthError",
    "BadRequest",
    "DatabaseError",
    "DatabaseNotFound",
    "DatabaseUnavailable",
    "Forbidden",
    "JwtError",
    "NotFound",
    "RateLimited",
    "ServerError",
    "StalzoneError",
    "TransportError",
    "Unauthorized",
    "UnprocessableEntity",
    "error_from_response",
    # models
    "Alliance",
    "Character",
    "CharacterClan",
    "CharacterInformation",
    "CharacterProfile",
    "CharacterStat",
    "Clan",
    "ClanList",
    "ClanMember",
    "ClanRank",
    "Emission",
    "Lot",
    "LotPage",
    "OperationSession",
    "PriceEntry",
    "PricePage",
    "PriceSummary",
    "Realm",
    "Region",
    "RegionInfo",
    "SessionPage",
    "SessionParticipant",
    "StatType",
    # helpers
    "paginate",
]

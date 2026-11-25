"""A small async client for the Stalzone API (Stalcraft).

    import asyncio
    from stalzone_api import AppClient

    async def main():
        async with AppClient() as client:      # env vars, or the demo server
            print(await client.emission())
            print(await client.profile("ZIV"))
            print(await client.auction("y1q9").lots(limit=3))

    asyncio.run(main())
"""

from .auth import OAuth, Token, UserInfo
from .client import AppClient, Auction
from .constants import DEMO_URL, PROD_URL, __version__
from .errors import (
    ApiError,
    BadRequest,
    Forbidden,
    NotFound,
    RateLimited,
    ServerError,
    StalzoneError,
    TransportError,
    Unauthorized,
)
from .models import (
    Character,
    Clan,
    ClanMember,
    Emission,
    Lot,
    Page,
    Participant,
    Price,
    Profile,
    Region,
    RegionInfo,
    Session,
)

__all__ = [
    "__version__",
    "AppClient",
    "Auction",
    "OAuth",
    "Token",
    "UserInfo",
    "PROD_URL",
    "DEMO_URL",
    "Region",
    "Page",
    "RegionInfo",
    "Emission",
    "Lot",
    "Price",
    "Clan",
    "ClanMember",
    "Character",
    "Profile",
    "Participant",
    "Session",
    "StalzoneError",
    "ApiError",
    "BadRequest",
    "Unauthorized",
    "Forbidden",
    "NotFound",
    "RateLimited",
    "ServerError",
    "TransportError",
]

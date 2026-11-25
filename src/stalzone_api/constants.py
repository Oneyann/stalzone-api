"""URLs, defaults and the public demo credentials published by EXBO."""

__version__ = "0.1.0"

PROD_URL = "https://eapi.stalzone.com"
DEMO_URL = "https://dapi.stalzone.com"

OAUTH_AUTHORIZE_URL = "https://exbo.net/oauth/authorize"
OAUTH_TOKEN_URL = "https://exbo.net/oauth/token"
OAUTH_USERINFO_URL = "https://exbo.net/oauth/user"

DEFAULT_REGION = "RU"
DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 3
USER_AGENT = f"stalzone-api/{__version__}"

# Public demo credentials from https://eapi.stalzone.com/overview.html.
DEMO_CLIENT_ID = "1"
DEMO_CLIENT_SECRET = "E98cm6J9NNjTQopph0c2eIXNKafg4R1Cjz0TZh2D"

# Installation

## Requirements

- Python 3.10 or newer.
- `httpx` (installed automatically as the package's runtime dependency).
- Network access for API requests and for the default GitHub-backed item
  database provider.

Install the released package:

```console
python -m pip install stalzone-api
```

Install from a source checkout with test dependencies:

```console
python -m pip install -e ".[test]"
```

The optional `gui` extra installs PySide6 for applications that integrate the
library with Qt. The core API client and item database do not require Qt.

## Verify the installation

```console
python -c "import stalzone_api; print(stalzone_api.__version__)"
```

## Import surface

The package re-exports its supported public classes from `stalzone_api`, for
example:

```python
from stalzone_api import (
    AppClient,
    AsyncClient,
    Client,
    Database,
    OAuth,
    SyncAppClient,
)
```

`stalzone_api.__version__` reports the installed package version. The package
ships `py.typed` for type checkers.

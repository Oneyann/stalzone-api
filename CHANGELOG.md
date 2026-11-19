# Changelog

Notable user-facing changes are listed here. The project follows semantic
versioning once it reaches a stable public API.

## 0.1.0 — initial release

- Synchronous and asynchronous Stalzone API clients.
- Simple `AppClient` and `SyncAppClient` facades with environment credential
  lookup and the public demo server fallback.
- OAuth helpers, typed response models, pagination, retries, rate limiting,
  and API error mapping.
- Read-only access to the official Stalcraft item database from GitHub, local
  checkouts, or downloaded snapshots, including item search and icons.
- Python 3.10+ support and PEP 561 typing marker.

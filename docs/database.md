# Official item database

`Database` exposes the official
[`EXBO-Studio/stalzone-database`](https://github.com/EXBO-Studio/stalzone-database)
repository. A database instance represents one realm (`ru` or `global`) and
provides `db.items` and `db.icons`.

## Providers and recommended usage

### On-demand GitHub access

```python
from stalzone_api import Database

with Database("ru") as db:
    item = db.items.get("knmpy")
    print(item.name.ru, item.weight, item.damage)
```

`Database(...)` uses GitHub by default. It fetches the repository tree and
item files on demand and stores results in a disk cache. Unauthenticated
GitHub rate limits can be reached; optionally pass `github_token=...` or set
`STALZONE_GITHUB_TOKEN` / `GITHUB_TOKEN`.

### Download an offline snapshot

```python
db = Database("ru").sync()  # download/extract the repository archive once
try:
    print(db.items.get("knmpy"))
finally:
    db.close()
```

`sync(dest=None, force=False)` downloads a zip snapshot into the cache's
`snapshots` subdirectory and returns a new `Database` backed by the extracted
local files. Pass `dest` to choose the snapshot directory. `force=True`
downloads it again.

### Local checkout or snapshot

```python
db = Database.local("./stalzone-database", realm="ru")
```

The path can point directly to a realm directory containing `items/`, or to
the repository root containing `ru/items/` or `global/items/`. If the realm
is not specified at the repository root, the provider tries `ru` then
`global`.

## Items

```python
item = db.items.get("knmpy")       # one matching ID
all_matches = db.items.get_all("knmpy")
variants = db.items.variants("knmpy")

for item in db.items.all(category="weapon"):
    print(item.id, item.name.en)
```

`ItemStore` also supports:

- `ids()`, `categories()`, and `subcategories(category)`.
- `len(db.items)`, iteration, and `"item-id" in db.items`.
- `get`, `get_all`, `variants`, and `all(category=None)`.
- `build_name_index(...)` and localized `search(...)`.

IDs are not guaranteed to be unique; `get()` returns the first indexed match,
while `get_all()` returns all matches.

### Search

Search by name is ranked exact match, prefix, then substring. The name index
uses localized names and defaults to English with fallback to another
available translation.

```python
# For GitHub-backed access, build/download the name index once:
db.build_index()
matches = db.items.search("винторез", lang="ru", limit=5)
```

Local and snapshot providers build the index automatically on first search.
For GitHub-backed providers, building the index reads every item name and may
make many requests the first time; caching and an optional GitHub token help.
Use `include_variants=True` when building/searching variants.

An optional progress callback has the form `callback(path, completed, total)`.
`build_index(progress=..., force=False)` is a convenience wrapper for building
the name index.

## Item model

`Item` includes `id`, `category`, localized `name`, optional `color` and
`status`, `info_blocks`, `path`, `realm`, and unknown fields in `extra`.
Convenience properties include:

- `category_type` / `type` and `category_subtype` / `subtype`.
- `blocks`, `blocks_of(kind)`, `find(translation_key)`, `stats`, and
  `stat(key, default)`.
- `weight`, `damage`, and `description`.
- `to_dict()`.

Localization is represented by `Text`. Use `text.get("ru")`, `.ru`, or `.en`;
`Text.format(**kwargs)` attempts safe placeholder formatting. Known block and
element kinds have typed classes; unrecognized kinds are preserved as
`RawBlock` or `RawElement`, and additional fields are kept in `extra`.

## Icons

```python
icon_url = db.icons.url("knmpy")
png_bytes = db.icons.bytes("knmpy")
saved = db.icons.save("knmpy", "./icons")
count = db.icons.download_all("./database-icons", categories=["weapon"])
```

`path()` and `url()` return `None` if no icon is indexed.
`download_all()` preserves paths and accepts optional category filters,
`overwrite`, and a progress callback. Icon bytes are cached by the provider.

## Cache and lifecycle

The default cache location is controlled by `STALZONE_CACHE_DIR`; otherwise
the library uses the platform's conventional user cache location, ending in
`stalzone-api`. The GitHub provider uses a 12-hour default TTL and supports
ETag revalidation and stale cached JSON as a fallback when GitHub is
unavailable. Close the database (or use it as a context manager) to release
provider HTTP resources.

Common database errors are `DatabaseNotFound`, `DatabaseUnavailable`, and
`DatabaseError`.

# Development and release

## Set up a checkout

```console
git clone https://github.com/Oneyann/stalzone-api.git
cd stalzone-api
python -m venv .venv
```

Activate the virtual environment, then install editable package and test
dependencies:

```console
python -m pip install -e ".[test]"
```

Install the documentation theme and preview the site locally:

```console
python -m pip install -e ".[docs]"
python -m mkdocs serve
```

The preview is served locally and refreshes as Markdown or style files change.
Build the static site and validate its links before publishing:

```console
python -m mkdocs build --strict
```

## Tests

```console
python -m pytest -q
```

Most tests use `httpx.MockTransport` and do not require network access. Live
API integration tests are opt-in:

```powershell
$env:STALZONE_RUN_INTEGRATION = "1"
python -m pytest -m integration
```

Do not enable live tests in an environment where requests to the public API
are not intended.

## Project layout

```text
src/stalzone_api/     Package implementation
  client.py           Sync/async resource clients
  simple.py           Friendly sync/async facades
  auth.py             OAuth and credential providers
  _http.py            HTTP transport, retries and errors
  models/             Typed API response models
  database/           Item database providers, models, cache and icons
tests/                Unit and opt-in integration tests
docs/                 User and developer documentation
```

The package uses a `src` layout and Hatchling build backend. `pyproject.toml`
declares Python 3.10+, `httpx>=0.27`, and the `test`, `gui`, and `docs`
optional dependency groups.

## Build and inspect distributions

```console
python -m pip install build twine
python -m build
python -m twine check dist/*
```

Before release, confirm the package version in `pyproject.toml` and
`src/stalzone_api/_version.py` agree, inspect the wheel and source archive,
run tests, and review `git status` for accidental secrets or generated files.

## Publishing

Use a protected PyPI API token or a configured trusted-publishing workflow.
Do not place credentials in the repository. Upload first to TestPyPI when
validating a new release process, then publish to PyPI:

```console
python -m twine upload --repository testpypi dist/*
python -m twine upload dist/*
```

PyPI does not allow replacing an existing file for the same package version;
increment the version before rebuilding a correction.

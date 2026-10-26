# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

Populates a videogame library in Notion. Reads a source Notion database for URLs pointing to IGDB game slugs and Steam app IDs, fetches metadata from IGDB (over the Twitch OAuth-authenticated API), HowLongToBeat, and SteamSpy, then creates/updates a constellation of related Notion databases under a configured root page.

## Tooling and commands

Dependencies are managed with `uv` (lockfile-driven); tasks are exposed through `just` (PowerShell-backed `justfile`). Run `just` with no recipe to list everything.

- `just sync` — install dev deps from `uv.lock` (`uv sync --frozen`)
- `just run` — `uv run -m notion_videogames.main`
- `just lock` — `uv lock --upgrade` (and `just uv-export` to refresh `requirements.txt`)
- `just qa` — runs `format` → `lint` → `type-check` in sequence
  - `just format` — `ty check --fix`, `ruff check --fix`, `ruff format`
  - `just lint` — `ruff check`, `flake8 notion_videogames`, `pylint notion_videogames`
  - `just type-check` — `ty check`, `mypy notion_videogames`
- `just prek [hook]` — run all pre-commit hooks, or a single one (use a hook id like `uv-lock-upgrade` to invoke a manual-stage hook)
- `just proto` — re-download `igdbapi.proto` and regenerate `notion_videogames/proto/` with `betterproto2` (run this if IGDB updates their schema)

There is no test suite in this repo. Don't invent one; if a change calls for verification, run `just qa` and (with credentials present) `just run`.

## Dependency updates

Renovate (`.github/renovate.json`) works together with the **Post-Renovate Hooks** workflow (`.github/workflows/update-dependencies.yml`):

- Renovate bumps the `pyproject.toml` ranges and writes `uv.lock` for each PR's own bumps. The workflow adds the transitive refresh (`uv lock --upgrade`, on the weekly group PR `renovate/pep621-pre-commit` only), then runs `sync-with-uv` → `uv-export` → `pyproject-fmt` and commits the result as `github-actions[bot]`.
- `gitIgnoredAuthors` lists that bot so Renovate doesn't treat its branches as hand-edited ("PR Edited (Blocked)"), and `vulnerabilityAlerts.rangeStrategy: "bump"` keeps security PRs from being lockfile-only, which would make Renovate and the workflow force-push in a loop. Change neither without the other, and keep the workflow's pinned `commit_author`.
- Hook `rev`s and every `additional_dependencies` line tagged `# sync-with-uv` are exact `uv.lock` pins owned by sync-with-uv; never hand-edit those versions. Change the range in `pyproject.toml`, re-lock, and let the `sync-with-uv` hook re-pin (`just prek sync-with-uv`). A newly tagged package must be in `uv.lock` (add it to the `dev` or `hooks` group), or sync-with-uv exits 123.
- mypy, ty and deptry are local `uv run --exact` hooks, so they run in the `uv.lock` environment rather than an isolated one.
- `constraints.python` in `renovate.json` is the `requires-python` floor as a full version (`"3.12.0"`): Renovate filters releases by it and also installs exactly that Python for its `uv lock` runs, so a bare `"3.12"` breaks every lockfile update. Move the two together.

## Required environment

`main.py` calls `load_dotenv()` and reads these from `.env` or the shell:

- `IGDB_CLIENT_ID`, `IGDB_CLIENT_SECRET` — Twitch app credentials used to mint an IGDB OAuth token
- `SOURCE_DB_ID` — Notion database id whose pages have a `URL` property pointing to igdb.com or store.steampowered.com
- `MAIN_PAGE_ID` — Notion page under which all generated databases live (created if missing, otherwise rebound)
- `MAIN_GAMES_DB_NAME` — title of the top-level "Custom Game" database (required, no default)
- Notion auth itself flows through `ultimate_notion`'s `Session.get_or_create()` (see its docs for the env var it expects)

## Architecture

### Data flow (`notion_videogames/main.py`)

1. Pull all pages from `SOURCE_DB_ID`; parse their `URL` props into `(hostname, path-parts)` tuples.
2. From igdb.com URLs, extract slugs and query the IGDB protobuf endpoint in batches of 25 for `games.pb`.
3. From store.steampowered.com URLs, extract Steam app IDs and query `external_games.pb` with `external_game_source=1` (Steam), pulling the linked IGDB game in the same response.
4. For every database title in `notion_db_types`, either create it under `MAIN_PAGE_ID` or rebind the existing one via `rebind_db` (which merges existing Select/MultiSelect options into the schema before binding, since `ultimate_notion` does not do this automatically).
5. For each game, retrieve HowLongToBeat best-match and (if a Steam id is present) SteamSpy data, then upsert one `CustomGamePage` per game.

To update already-existing pages, uncomment `notion.NotionPageType.update = True` near the end of `main.py`. Default behavior is create-only.

### Module layout

- `notion.py` — abstract base `NotionPageType[T]`. Owns the `retrieve_or_create_from_data` flow: schema validation via `to_pydantic_model`, `tenacity` retry on `HTTPResponseError`/`RequestTimeoutError`, and an `lru_cache` so each data object hits the API once per run.
- `igdb_notion.py` — one `NotionPageType` subclass per IGDB protobuf message (Game, Platform, Cover, etc.). Subclasses follow IGDB's relation graph; `get_query_fields` controls what fields are pulled. Monkey-patches `betterproto2.Message.__hash__` so messages are usable as `lru_cache` keys.
- `hltb_notion.py` — `HowLongToBeatGame` dataclass + `HLTBNotionPage`; performs best-match lookup against the HLTB API by game name.
- `steamspy_notion.py` — `SteamSpyGame` dataclass + `SteamSpyNotionPage` + `SteamSpySession` (a `requests.Session` with retry adapter; closed via `atexit`).
- `custom_notion.py` — the user-facing "Custom Game" schema. Aggregates IGDB/HLTB/SteamSpy relations with rollup properties (playtime, ratings, etc.) and adds personal-tracking props (Owned, Notes, "VAMOS JOGAR").
- `proto/` — generated `betterproto2` output for `igdbapi.proto`. Excluded from black, ruff, isort, pylint, deptry, and mypy (the relevant tools all have explicit excludes in `pyproject.toml`). Never hand-edit; regenerate with `just proto`.

### Notion model conventions

- Each `NotionPageType.schema` (a `uno.Schema` subclass) defines a Notion database. Relations between schemas mirror the IGDB graph; rollups in `CustomGamePageSchema` surface fields across those relations.
- Pages are looked up by their source-system id (IGDB id, HLTB game_id, Steam appid) via `retrieve_from_data` — usually a `query.filter(uno.prop("ID") == data.id)` on the bound database.
- `validate_and_build_schema_model` reuses `ultimate_notion`'s pydantic schema model to validate properties before calling `pages.create`/`pages.update`. Read-only props are stripped via `get_ro_props()`.

## Code style notes (in addition to what the tooling enforces)

- Python 3.12+; `from __future__ import annotations` at the top of each module is the established pattern.
- Linting is maximal: `ruff lint.select = ["ALL"]` with a curated ignore list, plus the full flake8-plugin stack, plus pylint, plus mypy strict-ish (`disallow_untyped_defs`, `warn_return_any`, etc.), plus `ty`. Run `just format` before committing — most rules autofix.
- Line length is 99 across black, ruff, isort, and flake8.
- `notion_videogames/proto/` is off-limits to formatters/linters; the excludes are already wired in.

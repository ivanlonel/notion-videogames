# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

Populates a videogame library in Notion. Reads a source Notion database for URLs pointing to IGDB game slugs and Steam app IDs, fetches metadata from IGDB (over the Twitch OAuth-authenticated API), HowLongToBeat, and Steam, then creates/updates a constellation of related Notion databases under a configured root page.

## Tooling and commands

Dependencies are managed with `uv` (lockfile-driven); tasks are exposed through `just` (PowerShell-backed `justfile`). Run `just` with no recipe to list everything.

- `just sync` — install dev deps from `uv.lock` (`uv sync --frozen`)
- `just run [flags]` — `uv run notion-videogames`, with `--dry-run`, `--limit N`, `--update`, `--refresh-steam`, `-v`
- `just lock` — `uv lock --upgrade` (and `just uv-export` to refresh `requirements.txt`). To change a dependency without upgrading everything else, use plain `uv lock`.
- `just qa` — runs `format` → `lint` → `type-check` → `test` in sequence
  - `just format` — `ty check --fix`, `ruff check --fix`, `ruff format`
  - `just lint` — `ruff check`, `flake8 notion_videogames tests`, `pylint notion_videogames tests`
  - `just type-check` — `ty check`, `mypy notion_videogames tests`
  - `just test` — `pytest`
- `just prek [hook]` — run all pre-commit hooks, or a single one (use a hook id like `uv-lock-upgrade` to invoke a manual-stage hook)
- `just proto` — re-download `igdbapi.proto` and regenerate `notion_videogames/proto/` with `betterproto2` (run this if IGDB updates their schema)

Tests live in one file, `tests/test_offline.py`, and use no network, credentials or Notion. Keep it that way, and add to that file rather than building up a larger suite. Real verification against Notion is `uv run notion-videogames --dry-run` (read-only), then `--limit N`. `--update` edits existing pages and every page related to them (16 games took 28 minutes), so ask before running it against the user's library.

On Windows, VS Code language servers running from `.venv` can lock compiled modules, which makes `uv sync` fail with "Acesso negado"/"Access denied" when removing or upgrading one. Reloading the VS Code window releases them.

## Dependency updates

Renovate (`.github/renovate.json`) works together with the **Post-Renovate Hooks** workflow (`.github/workflows/update-dependencies.yml`):

- Renovate bumps the `pyproject.toml` ranges and writes `uv.lock` for each PR's own bumps. The workflow adds the transitive refresh (`uv lock --upgrade`, on the weekly group PR `renovate/pep621-pre-commit` only), then runs `sync-with-uv` → `uv-export` → `pyproject-fmt` and commits the result as `github-actions[bot]`.
- `gitIgnoredAuthors` lists that bot so Renovate doesn't treat its branches as hand-edited ("PR Edited (Blocked)"), and `vulnerabilityAlerts.rangeStrategy: "bump"` keeps security PRs from being lockfile-only, which would make Renovate and the workflow force-push in a loop. Change neither without the other, and keep the workflow's pinned `commit_author`.
- Hook `rev`s and every `additional_dependencies` line tagged `# sync-with-uv` are exact `uv.lock` pins owned by sync-with-uv; never hand-edit those versions. Change the range in `pyproject.toml`, re-lock, and let the `sync-with-uv` hook re-pin (`just prek sync-with-uv`). A newly tagged package must be in `uv.lock` (add it to the `dev` or `hooks` group), or sync-with-uv exits 123.
- mypy, ty, deptry and pytest are local `uv run --exact` hooks, so they run in the `uv.lock` environment rather than an isolated one, and CI's prek job runs the tests without a workflow of their own.
- `constraints.python` in `renovate.json` is the `requires-python` floor as a full version (`"3.12.0"`): Renovate filters releases by it and also installs exactly that Python for its `uv lock` runs, so a bare `"3.12"` breaks every lockfile update. Move the two together.
- `uv-build` in `[build-system]` has an upper bound that has to follow uv's minor version. Renovate's pep621 manager should handle it as one more range, but no bump has come through yet to confirm that.
- `requirements.txt` is exported with `--no-emit-project`. Without it, the export gains a `-e .` line now that the project is a package.

## Required environment

`main()` reads these from the shell or from a `.env` file, searched from the current directory upward (`.env.example` lists them). Plain `load_dotenv()` would search from the calling file's folder instead, which breaks for an installed package and for scripts kept outside the repo. `Settings.from_env` names everything missing at once:

- `IGDB_CLIENT_ID`, `IGDB_CLIENT_SECRET` — Twitch app credentials used to mint an IGDB OAuth token
- `NOTION_TOKEN` — read by `ultimate_notion` itself, which also accepts a token in its own config file
- `SOURCE_DB_ID` — Notion database id whose pages have a `URL` property pointing to igdb.com or store.steampowered.com
- `MAIN_PAGE_ID` — Notion page under which all generated databases live (created if missing, otherwise rebound)
- `MAIN_GAMES_DB_NAME` — title of the top-level "Custom Game" database (required, no default)

## Architecture

### Data flow (`notion_videogames/main.py`)

1. Pull all pages from `SOURCE_DB_ID`; `parse_source_urls` sorts their `URL` props into IGDB slugs, Steam app ids, and unrecognized URLs, which get reported.
2. For every database title in `DB_PAGE_TYPES` plus the main one, either create it under `MAIN_PAGE_ID` or rebind the existing one via `rebind_db`. That merges existing Select/MultiSelect options into the schema, since `ultimate_notion` doesn't, and tolerates columns added by hand in Notion. The dict's order matters: a database must come after the ones its relations point to.
3. `custom_notion.find_imported` reads the library once, so that only what's missing gets fetched. `--update` skips this and goes through everything.
4. Query IGDB's protobuf endpoints in batches of 25: `games.pb` by slug, and `external_games.pb` with `external_game_source=1` (Steam) by app id, pulling the linked IGDB game in the same response.
5. For each game, retrieve the HowLongToBeat best match and (if a Steam id is present) Steam's data, then upsert one `CustomGamePage`.

`--refresh-steam` replaces steps 3–5: after binding, it rewrites every page of `Steam Games` from Steam. It's the only way to reach games that aren't in the source database, and it touches nothing else. It took 28 minutes for 465 pages.

A failed game or IGDB batch is logged and reported at the end, and the exit status is 1. A failed HLTB or Steam lookup still creates the game, without that link. Rejected requests (4xx) and schema mismatches end the run with a one-line message (`-v` for the traceback).

A no-op rerun still costs about two GETs per database: `root_page.sub_dss` resolves each one, and that's inside `ultimate_notion`.

### Module layout

- `notion.py` — abstract base `NotionPageType[T]`, which owns the `retrieve_or_create_from_data` flow. Its `_pages` map (keyed by page type and source id) makes each page get looked up and written once per run. `retry_transient` covers 409, 429, 5xx, timeouts and transport errors, and wraps single API calls only: related pages get resolved between those calls, because a retry around that recursion would multiply attempts at every nesting level. `--update` sets the `update` class variable.
- `igdb_notion.py` — `IGDBSession`, plus a schema and a `NotionPageType` subclass per IGDB protobuf message (Game, Platform, Cover, etc.). `IGDBNotionPage` builds properties and query fields from the schema alone; subclasses declare only an `image` rule or a `computed` value.
- `hltb_notion.py` — `HowLongToBeatGame` dataclass + `HLTBNotionPage`; performs best-match lookup against the HLTB API by game name, requiring `MIN_SIMILARITY` and breaking ties by release year.
- `steam_notion.py` — `SteamGame` dataclass + `SteamNotionPage` + `SteamSession` (a `requests.Session` with retry adapter). `get_game` costs 4 to 6 calls per game. It returns `None` if Steam doesn't have the app and raises if a request fails.
- `custom_notion.py` — the user-facing "Custom Game" schema. Aggregates IGDB/HLTB/Steam relations with rollup properties (playtime, ratings, etc.) and adds personal-tracking props (Owned, Notes, "VAMOS JOGAR"). Also has `find_imported`.
- `proto/` — generated `betterproto2` output for `igdbapi.proto`. Excluded from ruff, flake8, pylint, deptry, and mypy (the relevant tools all have explicit excludes). Never hand-edit; regenerate with `just proto`.

### Notion model conventions

- Each `NotionPageType.schema` (a `uno.Schema` subclass, passed as `schema=` in the class statement) defines a Notion database. Relations between schemas mirror the IGDB graph; rollups in `CustomGamePageSchema` surface fields across those relations.
- Changing a schema's Notion-facing names breaks binding to existing databases. Python attribute names can change freely, but in IGDB schemas they must match the message's fields.
- In IGDB schemas, a property reads the message field named like its attribute; a relation's target comes from `schema=`. `related_to_*` relations are the far side of two-way relations and are neither written nor queried, and neither are self-references. Anything else goes in `computed`. Adding a property is one line, and `test_every_schema_prop_maps_to_a_message_field` catches a wrong name, since type checkers can't see through the generic mapping.
- 22 IGDB entity types are dormant: their classes exist and their `DB_PAGE_TYPES` entries are commented out. Enabling one means uncommenting its entry (mind the order) and, for it to be reachable from a game, adding the relation to `GameSchema`.
- Pages are looked up by their source-system id (IGDB id, HLTB game_id, Steam appid) via `get_lookup_condition`, usually `uno.prop("ID") == cls.get_id(data)` on the bound database.
- `prop.prop_value` and `prop.readonly` raise on an unbound `Relation`, so use `props.Relations` directly and don't reach for those in offline code.

### What `--update` overwrites

It mirrors the sources, so IGDB removing a value or a list entry clears it in Notion too, and a user's manual edits to the mirror databases are lost. It never writes personal columns or anything outside the schema, and a single relation or date that's absent is left out rather than cleared. Fields a source has stopped sending must be left out as well, because older pages may hold values that can't be fetched again (see below). Don't apply that to everything: a blanket "never clear" rule would stop real IGDB removals from syncing.

### Upstream data quirks

Checked against live APIs in November 2026:

- **Steam Spy was dropped** because it stopped tracking games. In its export, the library's games from 2024 are all there, 2025 is 13 of 29 and 2026 is 0 of 18. PEAK, with over 300,000 reviews, came back with 0 reviews and `0 .. 20,000` owners, and playtime is 0 on all 82,523 apps. Its old columns (`Owners`, playtime and their `(h)` formulas, `Score Rank`, `User Score`) were removed from Notion in November 2026. Steam has no equivalent for owners or playtime.
- **Steam's APIs** need no key but are mostly undocumented, and they move: `appreviews` now redirects to the homepage and `ISteamApps/GetAppList` returns 404.
  - Review counts follow the store page: `purchase_type` 0 (Steam purchases) for paid games, 1 (all) for free ones. `is_free` is missing on delisted games, so if a total is more than 2% off `review_count`, try the other. Steam Spy's counts were nearer the "all" figure, so counts dropped on many pages when this changed, with ratings nearly unchanged.
  - `GetItems` answers `success: 15` with an empty name when an app isn't sold in that country, and reports some failures as a 200 with no `store_items`. Use the requested appid, because `appid` can be 0 on delisted games.
  - Languages and genres come from `appdetails`, which gives names. `GetItems` gives ids, and additional languages like Croatian come as `elanguage: -1` plus a number no list explains. `appdetails` allows about 200 calls per 5 minutes, hence the 1.5-second pause.
  - Notion allows 100 options per multi-select and Steam doesn't stop there: Öoo lists 103 languages. `SteamNotionPage` keeps the first 100.
  - Steam writes `Free To Play` where Steam Spy wrote `Free to Play`, so both options exist in Notion, and page names now carry Steam's ™ and ®.
- **HowLongToBeat** no longer sends `profile_steam`, `profile_dev` or `comp_lvl_spd`, and `HLTBNotionPage` skips them when absent for the same reason. `search` returns `None` for a failed request and `[]` for no results, and a game's alias counts towards similarity, so `OneShot: World Machine Edition` matches the 2016 `OneShot` at 1.0.
- **IGDB id 0 is real** for tables that used to be enums (`game_types`, `date_formats`, `company_statuses`), so never test an id for truthiness.
- **Some IGDB companies are named after another company's id**, such as `id=11986` called "70" (Nintendo's real id). A title like `70 - 868` is IGDB's data, not a mapping bug.
- **12 databases hold a blank `id=0` page** (titles like `0`, `None`, ` - 0`; empty `Checksum`) left by versions from 2024–2025. Older pages still link to them, and `--update` keeps those links because an absent single relation is left out. The current code shouldn't add more, because unset nested messages come back as `None`.
- With the current Notion sharing, every run logs a `Could not find page` warning. It's `ultimate_notion` looking up a parent page the integration can't see, and it's harmless.

## Code style notes (in addition to what the tooling enforces)

- Python 3.12+; `from __future__ import annotations` at the top of each module is the established pattern.
- Linting is maximal: `ruff lint.select = ["ALL"]` with a curated ignore list, plus the full flake8-plugin stack, plus pylint, plus mypy strict-ish (`disallow_untyped_defs`, `warn_return_any`, etc.), plus `ty`. Run `just format` before committing — most rules autofix.
- `# noqa` for a ruff-only code trips flake8-noqa, so scope those with `per-file-ignores` in `pyproject.toml` instead.
- Line length is 99 (`ruff format`, and flake8's `max-line-length` of 90 plus bugbear's 10% B950 margin).
- `notion_videogames/proto/` is off-limits to formatters/linters; the excludes are already wired in.

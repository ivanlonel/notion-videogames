from __future__ import annotations

import argparse
import dataclasses
import itertools
import logging
import os
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Self

import requests
import ultimate_notion as uno
from dotenv import load_dotenv
from notion_client.errors import HTTPResponseError
from ultimate_notion.config import get_or_create_cfg
from ultimate_notion.errors import UltimateNotionError
from ultimate_notion.schema import MultiSelect, Select

from notion_videogames import custom_notion, hltb_notion, igdb_notion, notion, steamspy_notion

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from notion_videogames.proto import proto

logger: logging.Logger = logging.getLogger(__name__)

IGDB_BATCH_SIZE: Final[int] = 25
"""Games per request, to avoid HTTP error 504 - gateway timeout"""

# The slug ends up inside a quoted string in an IGDB query, so it can't hold " or \.
IGDB_GAME_PATH: Final = re.compile(r'/games/([^/"\\]+)(?:/.*)?')
STEAM_APP_PATH: Final = re.compile(r"(?:/.*)?/app/(\d+)(?:/.*)?")

# In creation order: a database must come after the ones its relations point to.
# The main games database is added after these, under the name set in the environment.
DB_PAGE_TYPES: Final[dict[str, type[notion.NotionPageType[Any]]]] = {
    "Age Rating Organizations": igdb_notion.AgeRatingOrganization,
    "Age Rating Categories": igdb_notion.AgeRatingCategory,
    "Age Rating Content Description Types": igdb_notion.AgeRatingContentDescriptionType,
    "Age Rating Content Descriptions V2": igdb_notion.AgeRatingContentDescriptionV2,
    "Age Ratings": igdb_notion.AgeRating,
    "Alternative Names": igdb_notion.AlternativeName,
    "Artwork Types": igdb_notion.ArtworkType,
    "Artworks": igdb_notion.Artwork,
    "Company Logos": igdb_notion.CompanyLogo,
    "Company Statuses": igdb_notion.CompanyStatus,
    "Website Types": igdb_notion.WebsiteType,
    "Company Websites": igdb_notion.CompanyWebsite,
    "Date Formats": igdb_notion.DateFormat,
    "Companies": igdb_notion.Company,
    "Covers": igdb_notion.Cover,
    "External Game Sources": igdb_notion.ExternalGameSource,
    "Game Release Formats": igdb_notion.GameReleaseFormat,
    "Platform Families": igdb_notion.PlatformFamily,
    "Platform Logos": igdb_notion.PlatformLogo,
    "Platform Types": igdb_notion.PlatformType,
    "Platform Version Companies": igdb_notion.PlatformVersionCompany,
    "Release Date Regions": igdb_notion.ReleaseDateRegion,
    "Platform Version Release Dates": igdb_notion.PlatformVersionReleaseDate,
    "Platform Versions": igdb_notion.PlatformVersion,
    "Platform Websites": igdb_notion.PlatformWebsite,
    "Platforms": igdb_notion.Platform,
    "External Games": igdb_notion.ExternalGame,
    "Franchises": igdb_notion.Franchise,
    "Game Engine Logos": igdb_notion.GameEngineLogo,
    "Game Engines": igdb_notion.GameEngine,
    "Regions": igdb_notion.Region,
    "Game Localizations": igdb_notion.GameLocalization,
    "Game Modes": igdb_notion.GameMode,
    "Game Statuses": igdb_notion.GameStatus,
    "Game Types": igdb_notion.GameType,
    "Game Videos": igdb_notion.GameVideo,
    "Genres": igdb_notion.Genre,
    "Involved Companies": igdb_notion.InvolvedCompany,
    "Keywords": igdb_notion.Keyword,
    "Languages": igdb_notion.Language,
    "Language Support Types": igdb_notion.LanguageSupportType,
    "Language Supports": igdb_notion.LanguageSupport,
    "Multiplayer Modes": igdb_notion.MultiplayerMode,
    "Player Perspectives": igdb_notion.PlayerPerspective,
    "Release Date Statuses": igdb_notion.ReleaseDateStatus,
    "Release Dates": igdb_notion.ReleaseDate,
    "Screenshots": igdb_notion.Screenshot,
    "Themes": igdb_notion.Theme,
    "Websites": igdb_notion.Website,
    "IGDB Games": igdb_notion.Game,
    # "Collection Types": igdb_notion.CollectionType,
    # "Collections": igdb_notion.Collection,
    # "Collection Membership Types": igdb_notion.CollectionMembershipType,
    # "Collection Memberships": igdb_notion.CollectionMembership,
    # "Collection Relation Types": igdb_notion.CollectionRelationType,
    # "Collection Relations": igdb_notion.CollectionRelation,
    # "Game Times To Beat": igdb_notion.GameTimeToBeat,
    # "Game Version Feature Values": igdb_notion.GameVersionFeatureValue,
    # "Game Version Features": igdb_notion.GameVersionFeature,
    # "Game Versions": igdb_notion.GameVersion,
    # "Character Genders": igdb_notion.CharacterGender,
    # "Character Mug Shots": igdb_notion.CharacterMugShot,
    # "Character Species": igdb_notion.CharacterSpecie,
    # "Characters": igdb_notion.Character,
    # "Event Logos": igdb_notion.EventLogo,
    # "Network Types": igdb_notion.NetworkType,
    # "Event Networks": igdb_notion.EventNetwork,
    # "Events": igdb_notion.Event,
    # "Popularity Types": igdb_notion.PopularityType,
    # "Popularity Primitives": igdb_notion.PopularityPrimitive,
    # "Test Dummies": igdb_notion.TestDummy,
    # "Searches": igdb_notion.Search,
    "HowLongToBeat Games": hltb_notion.HLTBNotionPage,
    "Steam Spy Games": steamspy_notion.SteamSpyNotionPage,
}


@dataclass(frozen=True)
class Settings:
    igdb_client_id: str
    igdb_client_secret: str
    source_db_id: str
    main_page_id: str
    main_games_db_name: str

    @classmethod
    def from_env(cls) -> Self:
        values = {f.name: os.getenv(f.name.upper(), "") for f in dataclasses.fields(cls)}
        missing = [name.upper() for name, value in values.items() if not value]
        # Ultimate Notion reads its token by itself, from this variable or from its config file.
        if not get_or_create_cfg().ultimate_notion.token:
            missing.append("NOTION_TOKEN")
        if missing:
            msg = f"Missing environment variables: {', '.join(missing)}. See .env.example."
            raise SystemExit(msg)
        return cls(**values)


@dataclass
class Summary:
    """What a run did, reported at its end."""

    written: int = 0
    already_imported: int = 0
    failed: list[str] = field(default_factory=list)
    incomplete: list[str] = field(default_factory=list)
    not_on_igdb: list[str] = field(default_factory=list)
    unrecognized: list[str] = field(default_factory=list)

    def log(self) -> None:
        logger.info(
            "Done: %d games written, %d URLs already imported, %d failed.",
            self.written,
            self.already_imported,
            len(self.failed),
        )
        for level, message, items in (
            (logging.ERROR, "Failed", self.failed),
            (logging.WARNING, "Lookup failed, use --update to fill the link in", self.incomplete),
            (logging.WARNING, "Not found on IGDB", self.not_on_igdb),
            (logging.WARNING, "Not IGDB game or Steam app URLs", self.unrecognized),
        ):
            if items:
                logger.log(level, "%s: %s", message, ", ".join(items))


@dataclass(frozen=True)
class SourceUrls:
    slugs: list[str]
    steam_app_ids: list[str]
    unrecognized: list[str]


def _is_on(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def parse_source_urls(urls: Iterable[str]) -> SourceUrls:
    """Sort URLs by what they identify, dropping repeats."""
    slugs: list[str] = []
    steam_app_ids: list[str] = []
    unrecognized: list[str] = []

    for url in urls:
        try:
            parts = urllib.parse.urlsplit(url)
            host = parts.hostname or ""
        except ValueError:
            unrecognized.append(url)
            continue

        path = urllib.parse.unquote(parts.path)
        if _is_on(host, "igdb.com") and (match := IGDB_GAME_PATH.fullmatch(path)):
            slugs.append(match[1])
        elif _is_on(host, "steampowered.com") and (match := STEAM_APP_PATH.fullmatch(path)):
            steam_app_ids.append(match[1])
        else:
            unrecognized.append(url)

    return SourceUrls(
        list(dict.fromkeys(slugs)),
        list(dict.fromkeys(steam_app_ids)),
        list(dict.fromkeys(unrecognized)),
    )


def read_source_urls(session: uno.Session, source_db_id: str) -> SourceUrls:
    pages = [
        page
        for data_source in session.get_db(source_db_id).data_sources
        for page in notion.retry_transient(data_source.get_all_pages)()
    ]
    logger.info("Found %d pages in the source database.", len(pages))
    return parse_source_urls(str(url) for page in pages if (url := page.props["URL"]))


def drop_undeclared_columns(reflected: type[uno.Schema], declared: type[uno.Schema]) -> list[str]:
    """
    Remove columns that `declared` doesn't know from a database's reflected schema, and name them.

    These were added by hand in Notion. Binding checks the two schemas for equality, so without
    this it would reject them. Writes only ever touch declared columns, so they're left alone.
    """
    columns = reflected.get_props()
    undeclared = [column.name for column in columns if not declared.has_prop(column.name)]
    columns[:] = [column for column in columns if declared.has_prop(column.name)]
    return undeclared


def rebind_db(data_source: uno.DataSource, schema: type[uno.Schema]) -> None:
    """Add options from (Multi)Select properties of previously-bound DB to schema and bind them."""
    for schema_prop in schema.get_props():
        if not isinstance(schema_prop, (Select, MultiSelect)):
            continue

        db_prop = data_source.schema.get_prop(schema_prop.name, default=None)
        if not isinstance(db_prop, (Select, MultiSelect)):
            # Ignore this, let bind_db do the complaining
            continue

        # Assigning directly to schema_prop.options raises SchemaNotBoundError
        obj_options = (
            schema_prop.obj_ref.select.options
            if isinstance(schema_prop, Select)
            else schema_prop.obj_ref.multi_select.options
        )

        # Add options from db without creating dupes or changing the order
        obj_options_copy = obj_options.copy()
        obj_options.clear()
        obj_options.extend(opt.obj_ref for opt in db_prop.options)
        obj_options.extend(opt for opt in obj_options_copy if opt not in obj_options)

    if undeclared := drop_undeclared_columns(data_source.schema, schema):
        logger.info("Leaving extra columns of %s alone: %s", data_source, ", ".join(undeclared))

    schema.bind_ds(data_source)


def bind_databases(
    session: uno.Session,
    root_page: uno.Page,
    page_types: dict[str, type[notion.NotionPageType[Any]]],
    *,
    create_missing: bool,
) -> list[str]:
    """Connect each page type to its database, returning the titles of those that were missing."""
    existing = {str(ds.title): ds for ds in root_page.sub_dss if str(ds.title) in page_types}
    missing = [title for title in page_types if title not in existing]
    if missing and not create_missing:
        # Binding checks relations against the databases they point to, which need to exist.
        return missing

    for title, page_type in page_types.items():
        if title in existing:
            rebind_db(session.get_ds(existing[title].id), page_type.schema)
        else:
            logger.info("Creating database %r.", title)
            session.create_ds(root_page, schema=page_type.schema, title=title)

    return missing


def _query_in_batches[T](
    query: Callable[[tuple[str, ...]], list[T]], values: Iterable[str], summary: Summary
) -> list[T]:
    results: list[T] = []
    for batch in itertools.batched(values, IGDB_BATCH_SIZE):
        try:
            results += query(batch)
        except (
            requests.ConnectionError,
            requests.Timeout,
            requests.exceptions.RetryError,
        ) as error:
            # The rest may still work. A rejected request (4xx) is left to raise: all would fail.
            logger.warning("IGDB request failed for %s: %s", ", ".join(batch), error)
            summary.failed += batch
    return results


def fetch_games(
    settings: Settings, slugs: list[str], steam_app_ids: list[str], summary: Summary
) -> list[proto.Game]:
    if not slugs and not steam_app_ids:
        return []

    with igdb_notion.IGDBSession(settings.igdb_client_id, settings.igdb_client_secret) as igdb:
        by_slug = _query_in_batches(igdb.find_games, slugs, summary)
        by_steam_id = _query_in_batches(igdb.find_steam_games, steam_app_ids, summary)

    accounted_for = {game.slug for game in by_slug} | {external.uid for external in by_steam_id}
    accounted_for |= set(summary.failed)
    summary.not_on_igdb += [
        value for value in (*slugs, *steam_app_ids) if value not in accounted_for
    ]

    # The same game may be listed under both its IGDB and its Steam URL.
    games = {game.id: game for game in by_slug}
    games |= {external.game.id: external.game for external in by_steam_id if external.game}
    return list(games.values())


def _lookup[T](
    source: str, game: proto.Game, summary: Summary, lookup: Callable[[], T | None]
) -> T | None:
    """Run a lookup whose failure shouldn't cost the game its page: --update can link it later."""
    try:
        return lookup()
    except Exception as error:  # pylint: disable=broad-exception-caught
        # Not just request errors: the HLTB library scrapes a site that changes without notice.
        logger.warning("%s lookup failed for %s: %s", source, game.name, error)
        summary.incomplete.append(f"{game.name} ({source})")
        return None


def sync_game(
    game: proto.Game, steam_spy: steamspy_notion.SteamSpySession, summary: Summary
) -> uno.Page:
    release = game.first_release_date
    steam_id = igdb_notion.get_steam_app_id(game)

    hltb_match = _lookup(
        "HowLongToBeat",
        game,
        summary,
        lambda: hltb_notion.HLTBNotionPage.get_best_match(
            game.name, release.year if release else None
        ),
    )
    steam_spy_match = (
        _lookup("Steam Spy", game, summary, lambda: steam_spy.get_steam_spy_data(steam_id))
        if steam_id
        else None
    )

    return custom_notion.CustomGamePage.retrieve_or_create_from_data(
        custom_notion.CustomGame(game, hltb_match, steam_spy_match)
    )


def sync_games(games: list[proto.Game], summary: Summary) -> None:
    with steamspy_notion.SteamSpySession() as steam_spy:
        for position, game in enumerate(games, start=1):
            progress = f"[{position}/{len(games)}] {game.name}"
            try:
                page = sync_game(game, steam_spy, summary)
            except Exception:  # pylint: disable=broad-exception-caught
                # One bad game shouldn't stop the rest. A later run retries it.
                logger.exception("%s: failed", progress)
                summary.failed.append(game.name)
            else:
                logger.info("%s: %s", progress, page.url)
                summary.written += 1


def run(args: argparse.Namespace, settings: Settings) -> Summary:
    summary = Summary()
    page_types = DB_PAGE_TYPES | {settings.main_games_db_name: custom_notion.CustomGamePage}

    with uno.Session.get_or_create() as session:
        source = read_source_urls(session, settings.source_db_id)
        summary.unrecognized = source.unrecognized

        missing = bind_databases(
            session,
            session.get_page(settings.main_page_id),
            page_types,
            create_missing=not args.dry_run,
        )
        if missing:
            verb = "Would create" if args.dry_run else "Created"
            logger.info("%s %d databases: %s", verb, len(missing), ", ".join(missing))

        # A dry run leaves missing databases unbound, and there's no reading unbound databases.
        imported = (
            custom_notion.Imported()
            if args.update or (args.dry_run and missing)
            else custom_notion.find_imported()
        )
        slugs = [slug for slug in source.slugs if slug not in imported.slugs]
        steam_app_ids = [
            app_id for app_id in source.steam_app_ids if app_id not in imported.steam_app_ids
        ]
        summary.already_imported = (
            len(source.slugs) + len(source.steam_app_ids) - len(slugs) - len(steam_app_ids)
        )

        games = fetch_games(settings, slugs[: args.limit], steam_app_ids[: args.limit], summary)

        # Reachable with Steam URLs whose game Steam Spy doesn't know, so they never look imported.
        pending = [game for game in games if game.id not in imported.igdb_ids]
        summary.already_imported += len(games) - len(pending)
        pending = pending[: args.limit]

        if args.dry_run:
            verb = "update or create" if args.update else "create"
            for game in pending:
                logger.info("Would %s: %s", verb, game.name)
        else:
            sync_games(pending, summary)

    return summary


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        msg = f"{value} is not a positive number"
        raise argparse.ArgumentTypeError(msg)
    return number


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="notion-videogames",
        description="Import videogames into Notion from IGDB, HowLongToBeat and Steam Spy.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="also refresh pages that already exist, instead of only creating missing ones",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        metavar="N",
        help="process at most N games, to try things out on a small batch",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be done, without writing to Notion",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="log more details")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    # Dependencies are chatty at INFO, which would bury the progress lines.
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.getLogger("notion_videogames").setLevel(level)
    logger.setLevel(level)  # Named __main__ when run with python -m

    load_dotenv()
    settings = Settings.from_env()
    notion.NotionPageType.update = args.update

    try:
        summary = run(args, settings)
    except (requests.HTTPError, HTTPResponseError, UltimateNotionError) as error:
        # Bad credentials, a wrong id, a schema mismatch: the message says it all.
        logger.critical("%s", error, exc_info=args.verbose)
        return 1

    summary.log()
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

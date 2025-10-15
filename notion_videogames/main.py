from __future__ import annotations

import atexit
import collections
import itertools
import logging
import os
import urllib.parse
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, Final, TypedDict

import requests
import ultimate_notion as uno
from dotenv import load_dotenv
from igdb.wrapper import IGDBWrapper
from ultimate_notion.schema import MultiSelect, Select

from notion_videogames import (
    custom_notion,
    hltb_notion,
    igdb_notion,
    igdb_proto,
    notion,
    steamspy_notion,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    class TwitchOauth2Token(TypedDict):
        access_token: str
        expires_in: int
        token_type: str


load_dotenv()

IGDB_CLIENT_ID: Final[str | None] = os.getenv("IGDB_CLIENT_ID")
IGDB_CLIENT_SECRET: Final[str | None] = os.getenv("IGDB_CLIENT_SECRET")
SOURCE_DB_ID: Final[str | None] = os.getenv("SOURCE_DB_ID")
MAIN_PAGE_ID: Final[str | None] = os.getenv("MAIN_PAGE_ID")
MAIN_GAMES_DB_NAME: Final[str] = os.environ["MAIN_GAMES_DB_NAME"]

logger: logging.Logger = logging.getLogger(__name__)


notion_db_types: dict[str, type[notion.NotionPageType[Any]]] = {
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
    MAIN_GAMES_DB_NAME: custom_notion.CustomGamePage,
}


def get_twitch_oauth2_token(
    client_id: str,
    client_secret: str,
    timeout: float | tuple[float, float] | tuple[float, None] | None = None,
) -> TwitchOauth2Token:
    dic: TwitchOauth2Token = requests.post(
        "https://id.twitch.tv/oauth2/token",
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
        timeout=timeout,
    ).json()
    return dic


def query_igdb_games(wrapper: IGDBWrapper, query: str) -> list[igdb_proto.Game]:
    return igdb_proto.GameResult.FromString(wrapper.api_request("games.pb", query)).games


def query_igdb_external_games(wrapper: IGDBWrapper, query: str) -> list[igdb_proto.ExternalGame]:
    return igdb_proto.ExternalGameResult.FromString(
        wrapper.api_request("external_games.pb", query)
    ).externalgames


def get_url_path_parts(urls: Iterable[str | bytes]) -> dict[str | None, list[tuple[str, ...]]]:
    d: dict[str | None, list[tuple[str, ...]]] = collections.defaultdict(list)

    for url in urls:
        split_url = urllib.parse.urlsplit(urllib.parse.unquote(url))
        d[split_url.hostname].append(PurePosixPath(split_url.path).parts)

    return d


def rebind_db(database: uno.Database, schema: type[uno.Schema]) -> None:
    """Add options from (Multi)Select properties of previously-bound DB to schema and bind them."""
    for schema_prop in schema.get_props():
        if not isinstance(schema_prop, (Select, MultiSelect)):
            continue

        db_prop = database.schema.get_prop(schema_prop.name)
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

    schema.bind_db(database)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    if not IGDB_CLIENT_ID or not IGDB_CLIENT_SECRET:
        _msg = "IGDB_CLIENT_ID and IGDB_CLIENT_SECRET must be set as environment variables"
        raise ValueError(_msg)
    if not SOURCE_DB_ID or not MAIN_PAGE_ID:
        _msg = "SOURCE_DB_ID and MAIN_PAGE_ID must be set as environment variables"
        raise ValueError(_msg)

    # IGDB API setup
    igdb_token = get_twitch_oauth2_token(IGDB_CLIENT_ID, IGDB_CLIENT_SECRET).get("access_token")
    igdb = IGDBWrapper(IGDB_CLIENT_ID, igdb_token)

    # Initialize Notion client
    with uno.Session.get_or_create() as notion_session:
        pages: list[uno.Page] = list(notion_session.get_db(SOURCE_DB_ID).get_all_pages())

        url_path_parts = get_url_path_parts(str(page.props["URL"]) for page in pages)

        logger.info("Found %d pages in source database.", len(pages))
        logger.info(list(url_path_parts))

        quoted_igdb_slugs = [
            f'"{parts[2]}"'
            for hostname, paths_list in url_path_parts.items()
            if hostname and hostname.rsplit(".", 2)[-2:] == ["igdb", "com"]
            for parts in paths_list
        ]

        games = list(
            itertools.chain.from_iterable(
                query_igdb_games(
                    igdb,
                    f"fields {','.join(igdb_notion.Game.get_query_fields())};"
                    f"where slug=({','.join(batch)});"
                    "limit 500;",
                )
                for batch in itertools.batched(quoted_igdb_slugs, 25)
            )
        )

        quoted_steam_appids = [
            f'"{parts[2]}"'
            for hostname, paths_list in url_path_parts.items()
            if hostname and hostname.rsplit(".", 2)[-2:] == ["steampowered", "com"]
            for parts in paths_list
        ]

        # 25 games per request, to avoid HTTP error 504 - gateway timeout
        external_games = itertools.chain.from_iterable(
            query_igdb_external_games(
                igdb,
                f"fields {','.join(f'game.{fld}' for fld in igdb_notion.Game.get_query_fields())};"
                f"where uid=({','.join(batch)}) & external_game_source=1;"
                "limit 500;",
            )
            for batch in itertools.batched(quoted_steam_appids, 25)
        )

        games += [external.game for external in external_games]

        root_page = notion_session.get_page(MAIN_PAGE_ID)

        databases = {db.title: db for db in root_page.subdbs if db.title in notion_db_types}

        for title, page_type in notion_db_types.items():
            if title in databases:
                databases[title] = notion_session.get_db(databases[title].id)
                rebind_db(databases[title], page_type.schema)
            else:
                databases[title] = notion_session.create_db(root_page, schema=page_type.schema)

        steam_spy = steamspy_notion.SteamSpySession()
        atexit.register(steam_spy.close)

        # UNCOMMENT NEXT LINE TO UPDATE EXISTING PAGES
        # notion.NotionPageType.update = True

        for game in games:
            steam_id = next(
                (int(eg.uid) for eg in game.external_games if eg.external_game_source.id == 1),
                None,
            )

            steamspy_match = steam_spy.get_steam_spy_data(steam_id) if steam_id else None

            game_page = custom_notion.CustomGamePage.retrieve_or_create_from_data(
                custom_notion.CustomGame(
                    game,
                    hltb_notion.HLTBNotionPage.get_best_match(game.name),
                    steamspy_match,
                )
            )
            logger.info("%s (%s)", game.name, game_page.id)

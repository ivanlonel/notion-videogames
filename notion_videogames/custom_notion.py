from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

import ultimate_notion as uno
from ultimate_notion import PropType, props

from notion_videogames import hltb_notion, igdb_notion, notion, steamspy_notion

if TYPE_CHECKING:
    from ultimate_notion.query import Condition

    from notion_videogames.proto import proto


@dataclass(frozen=True)
class CustomGame:
    igdb: proto.Game
    hltb: hltb_notion.HowLongToBeatGame | None = None
    steamspy: steamspy_notion.SteamSpyGame | None = None


class CustomGamePageSchema(uno.Schema):
    name = PropType.Title("Name")
    owned = PropType.MultiSelect(
        "Owned",
        options=[
            uno.Option("Steam", color="blue"),
            uno.Option("Switch", color="red"),
            uno.Option("EA", color="orange"),
        ],
    )
    notes = PropType.Text("Notes")
    vamos_jogar = PropType.Select("VAMOS JOGAR", options=[])
    igdb = PropType.Relation("IGDB", schema=igdb_notion.GameSchema)
    how_long_to_beat = PropType.Relation(
        "How Long to Beat", schema=hltb_notion.HLTBNotionPageSchema
    )
    steam_spy = PropType.Relation("Steam Spy", schema=steamspy_notion.SteamSpyNotionPageSchema)
    game_type = PropType.Rollup(
        "Game Type",
        relation=igdb,
        rollup=igdb_notion.GameSchema.game_type,
    )
    game_modes = PropType.Rollup(
        "Game Modes",
        relation=igdb,
        rollup=igdb_notion.GameSchema.game_modes,
    )
    main_story_h = PropType.Rollup(
        "Main Story (h)",
        relation=how_long_to_beat,
        rollup=hltb_notion.HLTBNotionPageSchema.main_story_hours,
    )
    main_extras_h = PropType.Rollup(
        "Main+Extras (h)",
        relation=how_long_to_beat,
        rollup=hltb_notion.HLTBNotionPageSchema.main_plus_hours,
    )
    completionist_h = PropType.Rollup(
        "Completionist (h)",
        relation=how_long_to_beat,
        rollup=hltb_notion.HLTBNotionPageSchema.completionist_hours,
    )
    steam_rating = PropType.Rollup(
        "Steam Rating",
        relation=steam_spy,
        rollup=steamspy_notion.SteamSpyNotionPageSchema.review_percent,
    )
    steam_rating_count = PropType.Rollup(
        "Steam Rating Count",
        relation=steam_spy,
        rollup=steamspy_notion.SteamSpyNotionPageSchema.review_count,
    )
    hltb_review_score = PropType.Rollup(
        "HLTB Review Score",
        relation=how_long_to_beat,
        rollup=hltb_notion.HLTBNotionPageSchema.review_score,
    )
    hltb_review_count = PropType.Rollup(
        "HLTB Review Count",
        relation=how_long_to_beat,
        rollup=hltb_notion.HLTBNotionPageSchema.review_count,
    )
    users_rating = PropType.Rollup(
        "Users Rating",
        relation=igdb,
        rollup=igdb_notion.GameSchema.rating,
    )
    users_rating_count = PropType.Rollup(
        "Users Rating Count",
        relation=igdb,
        rollup=igdb_notion.GameSchema.rating_count,
    )
    critic_rating = PropType.Rollup(
        "Critic Rating",
        relation=igdb,
        rollup=igdb_notion.GameSchema.aggregated_rating,
    )
    critic_rating_count = PropType.Rollup(
        "Critic Rating Count",
        relation=igdb,
        rollup=igdb_notion.GameSchema.aggregated_rating_count,
    )
    themes = PropType.Rollup(
        "Themes",
        relation=igdb,
        rollup=igdb_notion.GameSchema.themes,
    )
    genres = PropType.Rollup(
        "Genres",
        relation=igdb,
        rollup=igdb_notion.GameSchema.genres,
    )
    player_perspectives = PropType.Rollup(
        "Player Perspectives",
        relation=igdb,
        rollup=igdb_notion.GameSchema.player_perspectives,
    )
    platforms = PropType.Rollup(
        "Platforms",
        relation=igdb,
        rollup=igdb_notion.GameSchema.platforms,
    )
    steam_genres = PropType.Rollup(
        "Steam Genres",
        relation=steam_spy,
        rollup=steamspy_notion.SteamSpyNotionPageSchema.genres,
    )
    steam_tags = PropType.Rollup(
        "Steam Tags",
        relation=steam_spy,
        rollup=steamspy_notion.SteamSpyNotionPageSchema.tags,
    )
    steam_languages = PropType.Rollup(
        "Steam Languages",
        relation=steam_spy,
        rollup=steamspy_notion.SteamSpyNotionPageSchema.languages,
    )
    first_release_date = PropType.Rollup(
        "First Release Date",
        relation=igdb,
        rollup=igdb_notion.GameSchema.first_release_date,
    )
    igdb_url = PropType.Rollup(
        "IGDB URL",
        relation=igdb,
        rollup=igdb_notion.GameSchema.url,
    )
    howlongtobeat_url = PropType.Rollup(
        "HowLongToBeat URL",
        relation=how_long_to_beat,
        rollup=hltb_notion.HLTBNotionPageSchema.url,
    )
    steam_url = PropType.Rollup(
        "Steam URL",
        relation=steam_spy,
        rollup=steamspy_notion.SteamSpyNotionPageSchema.steam_url,
    )


class CustomGamePage(notion.NotionPageType[CustomGame], schema=CustomGamePageSchema):
    @override
    @classmethod
    def get_id(cls, data: CustomGame) -> int:
        return data.igdb.id

    @override
    @classmethod
    def get_populated_properties_dict(cls, data: CustomGame) -> dict[str, props.PropertyValue]:
        properties: dict[str, props.PropertyValue] = {
            "Name": props.Title(data.igdb.name),
            "IGDB": props.Relations(igdb_notion.Game.retrieve_or_create_from_data(data.igdb)),
        }
        # A missing match may be a failed lookup: leave any link an earlier run made untouched.
        if data.hltb is not None:
            properties["How Long to Beat"] = props.Relations(
                hltb_notion.HLTBNotionPage.retrieve_or_create_from_data(data.hltb)
            )
        if data.steamspy is not None:
            properties["Steam Spy"] = props.Relations(
                steamspy_notion.SteamSpyNotionPage.retrieve_or_create_from_data(data.steamspy)
            )
        return properties

    @override
    @classmethod
    def get_lookup_condition(cls, data: CustomGame) -> Condition:
        return uno.prop("IGDB").contains(igdb_notion.Game.retrieve_or_create_from_data(data.igdb))

    @override
    @classmethod
    def get_image_urls(cls, data: CustomGame) -> tuple[str | None, str | None]:
        return igdb_notion.Game.get_image_urls(data.igdb)


@dataclass(frozen=True)
class Imported:
    """What the library already holds, so that a run can skip fetching it again."""

    igdb_ids: frozenset[int] = frozenset()
    slugs: frozenset[str] = frozenset()
    steam_app_ids: frozenset[str] = frozenset()


def _read_all_pages(page_type: type[notion.NotionPageType[Any]]) -> list[uno.Page]:
    return list(notion.retry_transient(page_type.schema.get_ds().get_all_pages)())


def find_imported() -> Imported:
    # Reading these two first fills the session's page cache, which is where following relations
    # gets its pages from. Each relation followed below would be an API call otherwise.
    _read_all_pages(igdb_notion.Game)
    _read_all_pages(steamspy_notion.SteamSpyNotionPage)

    igdb_ids: set[int] = set()
    slugs: set[str] = set()
    steam_app_ids: set[str] = set()
    for page in _read_all_pages(CustomGamePage):
        for igdb_page in page.props["IGDB"]:
            igdb_ids.add(int(igdb_page.props["ID"] or 0))
            slugs.add(str(igdb_page.props["Slug"]))
        for steam_page in page.props["Steam Spy"]:
            steam_app_ids.add(str(int(steam_page.props["ID"] or 0)))

    return Imported(frozenset(igdb_ids), frozenset(slugs), frozenset(steam_app_ids))

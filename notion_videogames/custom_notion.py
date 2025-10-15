from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any, override

import ultimate_notion as uno
from ultimate_notion import PropType

from notion_videogames import hltb_notion, igdb_notion, igdb_proto, notion, steamspy_notion


@dataclass(frozen=True)
class CustomGame:
    igdb: igdb_proto.Game
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


class CustomGamePage(notion.NotionPageType[CustomGame]):
    schema = CustomGamePageSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_notion_properties(data: CustomGame) -> dict[str, dict[str, Any]]:
        return {
            "Name": {"title": [{"text": {"content": data.igdb.name}}]},
            "IGDB": {
                "relation": [
                    {"id": str(igdb_notion.Game.retrieve_or_create_from_data(data.igdb).id)}
                ]
            },
            "How Long to Beat": {
                "relation": (
                    [
                        {
                            "id": str(
                                hltb_notion.HLTBNotionPage.retrieve_or_create_from_data(
                                    data.hltb
                                ).id
                            )
                        }
                    ]
                    if data.hltb
                    else []
                )
            },
            "Steam Spy": {
                "relation": (
                    [
                        {
                            "id": str(
                                steamspy_notion.SteamSpyNotionPage.retrieve_or_create_from_data(
                                    data.steamspy
                                ).id
                            )
                        }
                    ]
                    if data.steamspy
                    else []
                )
            },
        }

    @override
    @classmethod
    def retrieve_from_data(cls, data: CustomGame) -> uno.Page | None:
        igdb_page = igdb_notion.Game.retrieve_or_create_from_data(data.igdb)
        return next(
            iter(cls.schema.get_db().query.filter(uno.prop("IGDB").contains(igdb_page)).execute()),
            None,
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: CustomGame,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.igdb.cover.url:
            icon_url = igdb_notion.add_https_scheme(data.igdb.cover.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)

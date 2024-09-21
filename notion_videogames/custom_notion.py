from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self, cast, override

from notion_videogames import hltb_notion, igdb_notion, igdb_proto, notion, steamspy_notion

if TYPE_CHECKING:
    from uuid import UUID

    from notional.query import QueryBuilder


@dataclass(frozen=True)
class CustomGame:
    igdb: igdb_proto.Game
    hltb: hltb_notion.HowLongToBeatGame | None = None
    steamspy: steamspy_notion.SteamSpyGame | None = None


class CustomGamePage(notion.ConnectablePage[CustomGame]):

    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        # pylint: disable=protected-access
        return cls._get_notion_schema(
            igdb_notion.Game._notional__database,
            hltb_notion.HLTBNotionPage._notional__database,
            steamspy_notion.SteamSpyNotionPage._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        igdb_game_db_id: str | UUID, hltb_game_db_id: str | UUID, steamspy_game_db_id: str | UUID
    ) -> dict[str, dict[str, Any]]:
        return {
            "Name": {"type": "title", "title": {}},
            "Owned": {
                "type": "multi_select",
                "multi_select": {
                    "options": [
                        {"name": "Steam", "color": "blue"},
                        {"name": "Switch", "color": "red"},
                    ]
                },
            },
            "Category": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Category",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "Game Modes": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Game Modes",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "Critic Rating": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Aggregated Rating",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "Critic Rating Count": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Aggregated Rating Count",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "Users Rating": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Rating",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "Users Rating Count": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Rating Count",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "HLTB Review Score": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Review Score",
                    "relation_property_name": "How Long to Beat",
                    "function": "show_original",
                },
            },
            "HLTB Review Count": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Review Count",
                    "relation_property_name": "How Long to Beat",
                    "function": "show_original",
                },
            },
            "Themes": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Themes",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "Genres": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Genres",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "Player Perspectives": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Player Perspectives",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "Platforms": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Platforms",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "Main Story (h)": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Main Story (h)",
                    "relation_property_name": "How Long to Beat",
                    "function": "show_original",
                },
            },
            "Main+Extras (h)": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Main+Extras (h)",
                    "relation_property_name": "How Long to Beat",
                    "function": "show_original",
                },
            },
            "Completionist (h)": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "Completionist (h)",
                    "relation_property_name": "How Long to Beat",
                    "function": "show_original",
                },
            },
            "First Release Date": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "First Release Date",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "IGDB URL": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "URL",
                    "relation_property_name": "IGDB",
                    "function": "show_original",
                },
            },
            "HowLongToBeat URL": {
                "type": "rollup",
                "rollup": {
                    "rollup_property_name": "URL",
                    "relation_property_name": "How Long to Beat",
                    "function": "show_original",
                },
            },
            "IGDB": {
                "type": "relation",
                "relation": {
                    "database_id": str(igdb_game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "How Long to Beat": {
                "type": "relation",
                "relation": {
                    "database_id": str(hltb_game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Steam Spy": {
                "type": "relation",
                "relation": {
                    "database_id": str(steamspy_game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
        }

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
    def retrieve_from_data(cls, data: CustomGame) -> Self | None:
        igdb_page = igdb_notion.Game.retrieve_or_create_from_data(data.igdb)
        if not igdb_page:
            return None

        page: Self | None = (
            cast("QueryBuilder", cls.query())
            .filter(property="IGDB", relation={"contains": igdb_page.id})
            .first()
        )
        return page

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: CustomGame,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.igdb.cover.url:
            icon_url = igdb_notion.add_https_scheme(data.igdb.cover.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast, override

from howlongtobeatpy.HowLongToBeat import HowLongToBeat
from howlongtobeatpy.JSONResultParser import JSONResultParser
from pydantic.dataclasses import dataclass

from notion_videogames import notion

if TYPE_CHECKING:
    from _typeshed import SupportsKeysAndGetItem
    from howlongtobeatpy.HowLongToBeatEntry import HowLongToBeatEntry
    from notional.query import QueryBuilder


@dataclass(frozen=True)
class HowLongToBeatGame:  # pylint: disable=too-many-instance-attributes
    game_id: int
    game_name: str
    game_name_date: int
    game_alias: str
    game_type: str
    game_image: str
    comp_lvl_combine: int
    comp_lvl_sp: int
    comp_lvl_co: int
    comp_lvl_mp: int
    comp_main: int
    comp_plus: int
    comp_100: int
    comp_all: int
    comp_main_count: int
    comp_plus_count: int
    comp_100_count: int
    comp_all_count: int
    invested_co: int
    invested_mp: int
    invested_co_count: int
    invested_mp_count: int
    count_comp: int
    count_speedrun: int
    count_backlog: int
    count_review: int
    review_score: int
    count_playing: int
    count_retired: int
    profile_popular: int
    release_world: int
    game_image_url: str
    game_web_link: str
    similarity: float
    comp_lvl_spd: int | None = None
    profile_steam: int | None = None
    profile_devs: tuple[str, ...] = ()
    profile_platforms: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, mapping: SupportsKeysAndGetItem[str, Any]) -> Self:
        dic = dict(mapping)

        profile_devs = tuple(dev for dev in dic.pop("profile_dev", "").split(", ") if dev)
        profile_platforms = tuple(pf for pf in dic.pop("profile_platform", "").split(", ") if pf)

        return cls(
            **dic,
            profile_devs=profile_devs,
            profile_platforms=profile_platforms,
            game_image_url=f'{JSONResultParser.IMAGE_URL_PREFIX}{dic["game_image"]}',
            game_web_link=f'{JSONResultParser.GAME_URL_PREFIX}{dic["game_id"]}',
        )


class HLTBNotionPage(notion.ConnectablePage[HowLongToBeatGame]):

    hltb_wrapper: ClassVar[HowLongToBeat] = HowLongToBeat(0)

    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Alias": {"type": "rich_text", "rich_text": {}},
            "Type": {"type": "select", "select": {"options": []}},
            "Main Story": {"type": "number", "number": {"format": "number"}},
            "Main+Extras": {"type": "number", "number": {"format": "number"}},
            "Completionist": {"type": "number", "number": {"format": "number"}},
            "All Styles": {"type": "number", "number": {"format": "number"}},
            "Main Story (h)": {
                "type": "formula",
                "formula": {"expression": 'round(prop("Main Story") / 36) / 100'},
            },
            "Main+Extras (h)": {
                "type": "formula",
                "formula": {"expression": 'round(prop("Main+Extras") / 36) / 100'},
            },
            "Completionist (h)": {
                "type": "formula",
                "formula": {"expression": 'round(prop("Completionist") / 36) / 100'},
            },
            "All Styles (h)": {
                "type": "formula",
                "formula": {"expression": 'round(prop("All Styles") / 36) / 100'},
            },
            "Main Story Count": {"type": "number", "number": {"format": "number"}},
            "Main+Extras Count": {"type": "number", "number": {"format": "number"}},
            "Completionist Count": {"type": "number", "number": {"format": "number"}},
            "All Styles Count": {"type": "number", "number": {"format": "number"}},
            "Co-op": {"type": "number", "number": {"format": "number"}},
            "Competitive": {"type": "number", "number": {"format": "number"}},
            "Co-op (h)": {
                "type": "formula",
                "formula": {"expression": 'round(prop("Co-op") / 36) / 100'},
            },
            "Competitive (h)": {
                "type": "formula",
                "formula": {"expression": 'round(prop("Competitive") / 36) / 100'},
            },
            "Co-op Count": {"type": "number", "number": {"format": "number"}},
            "Competitive Count": {"type": "number", "number": {"format": "number"}},
            "Review Score": {"type": "number", "number": {"format": "number"}},
            "Review Count": {"type": "number", "number": {"format": "number"}},
            "Count Completed": {"type": "number", "number": {"format": "number"}},
            "Count Speedruns": {"type": "number", "number": {"format": "number"}},
            "Count Backlogs": {"type": "number", "number": {"format": "number"}},
            "Count Playing": {"type": "number", "number": {"format": "number"}},
            "Count Retired": {"type": "number", "number": {"format": "number"}},
            "Popularity": {"type": "number", "number": {"format": "number"}},
            "Steam ID": {"type": "number", "number": {"format": "number"}},
            "Release Year": {"type": "number", "number": {"format": "number"}},
            "Profile Devs": {"type": "multi_select", "multi_select": {}},
            "Profile Platforms": {"type": "multi_select", "multi_select": {}},
            "Image URL": {"type": "url", "url": {}},
            "URL": {"type": "url", "url": {}},
            "Similarity": {"type": "number", "number": {"format": "number"}},
            "Game Name Date": {"type": "number", "number": {"format": "number"}},
            "comp_lvl_combine": {"type": "number", "number": {"format": "number"}},
            "comp_lvl_sp": {"type": "number", "number": {"format": "number"}},
            "comp_lvl_co": {"type": "number", "number": {"format": "number"}},
            "comp_lvl_mp": {"type": "number", "number": {"format": "number"}},
            "comp_lvl_spd": {"type": "number", "number": {"format": "number"}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: HowLongToBeatGame) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.game_id},
            "Name": {"title": [{"text": {"content": data.game_name}}]},
            "Alias": {"rich_text": [{"text": {"content": data.game_alias}}]},
            "Type": {"select": {"name": data.game_type}},
            "Main Story": {"number": data.comp_main},
            "Main+Extras": {"number": data.comp_plus},
            "Completionist": {"number": data.comp_100},
            "All Styles": {"number": data.comp_all},
            "Main Story Count": {"number": data.comp_main_count},
            "Main+Extras Count": {"number": data.comp_plus_count},
            "Completionist Count": {"number": data.comp_100_count},
            "All Styles Count": {"number": data.comp_all_count},
            "Co-op": {"number": data.invested_co},
            "Competitive": {"number": data.invested_mp},
            "Co-op Count": {"number": data.invested_co_count},
            "Competitive Count": {"number": data.invested_mp_count},
            "Review Score": {"number": data.review_score},
            "Review Count": {"number": data.count_review},
            "Count Completed": {"number": data.count_comp},
            "Count Speedruns": {"number": data.count_speedrun},
            "Count Backlogs": {"number": data.count_backlog},
            "Count Playing": {"number": data.count_playing},
            "Count Retired": {"number": data.count_retired},
            "Popularity": {"number": data.profile_popular},
            "Steam ID": {"number": data.profile_steam},
            "Release Year": {"number": data.release_world},
            "Profile Devs": {"multi_select": [{"name": dev} for dev in data.profile_devs]},
            "Profile Platforms": {"multi_select": [{"name": p} for p in data.profile_platforms]},
            "Image URL": {"url": data.game_image_url},
            "URL": {"url": data.game_web_link},
            "Similarity": {"number": data.similarity},
            "Game Name Date": {"number": data.game_name_date},
            "comp_lvl_combine": {"number": data.comp_lvl_combine},
            "comp_lvl_sp": {"number": data.comp_lvl_sp},
            "comp_lvl_co": {"number": data.comp_lvl_co},
            "comp_lvl_mp": {"number": data.comp_lvl_mp},
            "comp_lvl_spd": {"number": data.comp_lvl_spd},
        }

    @override
    @classmethod
    def retrieve_from_data(cls, data: HowLongToBeatGame) -> Self | None:
        if not hasattr(data, "game_id"):
            raise ValueError(f"{data!r} has no 'game_id' attribute")

        page: Self | None = (
            cast("QueryBuilder", cls.query())
            .filter(property="ID", number={"equals": data.game_id})
            .first()
        )
        return page

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: HowLongToBeatGame,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        return super().retrieve_or_create_from_data(
            data, icon_url or data.game_image_url, cover_url or data.game_image_url
        )

    @classmethod
    def get_best_match(cls, name: str, *, ignore_case: bool = True) -> HowLongToBeatGame | None:
        results: list[HowLongToBeatEntry] | None = cls.hltb_wrapper.search(
            name, similarity_case_sensitive=not ignore_case
        )
        if not results:
            return None

        best = max(results, key=lambda element: element.similarity)
        return HowLongToBeatGame.from_dict(best.json_content | {"similarity": best.similarity})

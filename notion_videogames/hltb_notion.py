from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast, override

import ultimate_notion as uno
from howlongtobeatpy.HowLongToBeat import HowLongToBeat
from howlongtobeatpy.JSONResultParser import JSONResultParser
from pydantic.dataclasses import dataclass
from ultimate_notion import PropType, props

from notion_videogames import notion

if TYPE_CHECKING:
    from _typeshed import SupportsKeysAndGetItem
    from howlongtobeatpy.HowLongToBeatEntry import HowLongToBeatEntry


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
            game_image_url=f"{JSONResultParser.IMAGE_URL_PREFIX}{dic['game_image']}",
            game_web_link=f"{JSONResultParser.GAME_URL_PREFIX}{dic['game_id']}",
        )


class HLTBNotionPageSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    alias = PropType.Text("Alias")
    type = PropType.Select("Type", options=[])
    main_story = PropType.Number("Main Story")
    main_plus = PropType.Number("Main+Extras")
    completionist = PropType.Number("Completionist")
    all_styles = PropType.Number("All Styles")
    main_story_hours = PropType.Formula(
        "Main Story (h)", formula='round(prop("Main Story") / 36) / 100'
    )
    main_plus_hours = PropType.Formula(
        "Main+Extras (h)", formula='round(prop("Main+Extras") / 36) / 100'
    )
    completionist_hours = PropType.Formula(
        "Completionist (h)", formula='round(prop("Completionist") / 36) / 100'
    )
    all_styles_hours = PropType.Formula(
        "All Styles (h)", formula='round(prop("All Styles") / 36) / 100'
    )
    main_story_count = PropType.Number("Main Story Count")
    main_plus_count = PropType.Number("Main+Extras Count")
    completionist_count = PropType.Number("Completionist Count")
    all_styles_count = PropType.Number("All Styles Count")
    coop = PropType.Number("Co-op")
    competitive = PropType.Number("Competitive")
    coop_hours = PropType.Formula("Co-op (h)", formula='round(prop("Co-op") / 36) / 100')
    competitive_hours = PropType.Formula(
        "Competitive (h)", formula='round(prop("Competitive") / 36) / 100'
    )
    coop_count = PropType.Number("Co-op Count")
    competitive_count = PropType.Number("Competitive Count")
    review_score = PropType.Number("Review Score")
    review_count = PropType.Number("Review Count")
    count_completed = PropType.Number("Count Completed")
    count_speedruns = PropType.Number("Count Speedruns")
    count_backlogs = PropType.Number("Count Backlogs")
    count_playing = PropType.Number("Count Playing")
    count_retired = PropType.Number("Count Retired")
    popularity = PropType.Number("Popularity")
    steam_id = PropType.Number("Steam ID")
    release_year = PropType.Number("Release Year")
    profile_devs = PropType.MultiSelect("Profile Devs", options=[])
    profile_platforms = PropType.MultiSelect("Profile Platforms", options=[])
    image_url = PropType.URL("Image URL")
    url = PropType.URL("URL")
    similarity = PropType.Number("Similarity")
    game_name_date = PropType.Number("Game Name Date")
    comp_lvl_combine = PropType.Number("comp_lvl_combine")
    comp_lvl_sp = PropType.Number("comp_lvl_sp")
    comp_lvl_co = PropType.Number("comp_lvl_co")
    comp_lvl_mp = PropType.Number("comp_lvl_mp")
    comp_lvl_spd = PropType.Number("comp_lvl_spd")


class HLTBNotionPage(notion.NotionPageType[HowLongToBeatGame]):
    schema = HLTBNotionPageSchema  # type: ignore[mutable-override]
    hltb_wrapper: ClassVar[HowLongToBeat] = HowLongToBeat(0)

    @override
    @staticmethod
    def get_populated_properties_dict(data: HowLongToBeatGame) -> dict[str, props.PropertyValue]:
        return {
            "ID": props.Number(data.game_id),
            "Name": props.Title(data.game_name),
            "Alias": props.Text(data.game_alias),
            "Type": props.Select(data.game_type),
            "Main Story": props.Number(data.comp_main),
            "Main+Extras": props.Number(data.comp_plus),
            "Completionist": props.Number(data.comp_100),
            "All Styles": props.Number(data.comp_all),
            "Main Story Count": props.Number(data.comp_main_count),
            "Main+Extras Count": props.Number(data.comp_plus_count),
            "Completionist Count": props.Number(data.comp_100_count),
            "All Styles Count": props.Number(data.comp_all_count),
            "Co-op": props.Number(data.invested_co),
            "Competitive": props.Number(data.invested_mp),
            "Co-op Count": props.Number(data.invested_co_count),
            "Competitive Count": props.Number(data.invested_mp_count),
            "Review Score": props.Number(data.review_score),
            "Review Count": props.Number(data.count_review),
            "Count Completed": props.Number(data.count_comp),
            "Count Speedruns": props.Number(data.count_speedrun),
            "Count Backlogs": props.Number(data.count_backlog),
            "Count Playing": props.Number(data.count_playing),
            "Count Retired": props.Number(data.count_retired),
            "Popularity": props.Number(data.profile_popular),
            "Steam ID": props.Number(data.profile_steam),
            "Release Year": props.Number(data.release_world),
            "Profile Devs": props.MultiSelect(data.profile_devs),
            "Profile Platforms": props.MultiSelect(data.profile_platforms),
            "Image URL": props.URL(data.game_image_url),
            "URL": props.URL(data.game_web_link),
            "Similarity": props.Number(data.similarity),
            "Game Name Date": props.Number(data.game_name_date),
            "comp_lvl_combine": props.Number(data.comp_lvl_combine),
            "comp_lvl_sp": props.Number(data.comp_lvl_sp),
            "comp_lvl_co": props.Number(data.comp_lvl_co),
            "comp_lvl_mp": props.Number(data.comp_lvl_mp),
            "comp_lvl_spd": props.Number(data.comp_lvl_spd),
        }

    @override
    @classmethod
    def retrieve_from_data(cls, data: HowLongToBeatGame) -> uno.Page | None:
        if not hasattr(data, "game_id"):
            msg = f"{data!r} has no 'game_id' attribute"
            raise ValueError(msg)

        return next(
            iter(cls.schema.get_db().query.filter(uno.prop("ID") == data.game_id).execute()), None
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: HowLongToBeatGame,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        return super().retrieve_or_create_from_data(
            data,
            icon_url=icon_url or data.game_image_url,
            cover_url=cover_url or data.game_image_url,
        )

    @classmethod
    def get_best_match(cls, name: str, *, ignore_case: bool = True) -> HowLongToBeatGame | None:
        results: list[HowLongToBeatEntry] | None = cls.hltb_wrapper.search(
            name, similarity_case_sensitive=not ignore_case
        )
        if not results:
            return None

        best = max(results, key=lambda element: element.similarity)
        return HowLongToBeatGame.from_dict(
            cast("dict[str, Any]", best.json_content) | {"similarity": best.similarity}
        )

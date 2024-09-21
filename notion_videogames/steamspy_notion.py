from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast, override

import requests
import urllib3
from pydantic.dataclasses import dataclass

from notion_videogames import notion

if TYPE_CHECKING:
    from _typeshed import SupportsKeysAndGetItem
    from notional.query import QueryBuilder

logger: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SteamSpyGame:  # pylint: disable=too-many-instance-attributes
    appid: int
    name: str
    developer: str
    publisher: str
    positive: int
    negative: int
    userscore: int
    owners: str
    average_forever: int
    average_2weeks: int
    median_forever: int
    median_2weeks: int
    ccu: int
    score_rank: int | None = None
    price: int | None = None
    initialprice: int | None = None
    discount: int | None = None
    languages: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, mapping: SupportsKeysAndGetItem[str, Any]) -> Self:
        dic = dict(mapping)

        score_rank = dic.pop("score_rank", "")
        price = dic.pop("price", "")
        initialprice = dic.pop("initialprice", "")
        discount = dic.pop("discount", "")

        if languages_str := dic.pop("languages", ""):
            languages = tuple(lang for lang in languages_str.split(", ") if lang)
        else:
            languages = ()

        if genres_str := dic.pop("genre", ""):
            genres = tuple(lang for lang in genres_str.split(", ") if lang)
        else:
            genres = ()

        if tags_obj := dic.pop("tags", {}):
            tags = tuple(tags_obj.keys()) if isinstance(tags_obj, dict) else tuple(tags_obj)
        else:
            tags = ()

        return cls(
            **dic,
            score_rank=int(score_rank) if score_rank else None,
            price=int(price) if price else None,
            initialprice=int(initialprice) if initialprice else None,
            discount=int(discount) if discount else None,
            languages=languages,
            genres=genres,
            tags=tags,
        )


class SteamSpySession(requests.Session):
    api_url: ClassVar[str] = "https://steamspy.com/api.php"
    retry_policy: ClassVar[urllib3.util.retry.Retry] = urllib3.util.retry.Retry(
        total=7,
        backoff_factor=1.875,
        respect_retry_after_header=False,
        status_forcelist={404, 408, 409, 413, 425, 429, 502, 503, 504, 521, 598, 599},
    )

    def __init__(self) -> None:
        super().__init__()

        self.mount("https://", requests.adapters.HTTPAdapter(max_retries=self.retry_policy))

    def get_steam_spy_data(self, app_id: int) -> SteamSpyGame | None:
        params: dict[str, str | int] = {"request": "appdetails", "appid": app_id}
        response = self.get(self.api_url, params=params)

        logger.info("Steam Spy appdetails response for appid %d: %d", app_id, response.status_code)

        return SteamSpyGame.from_dict(response.json()) if response.ok else None


class SteamSpyNotionPage(notion.ConnectablePage[SteamSpyGame]):
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
            "Developer": {"type": "rich_text", "rich_text": {}},
            "Publisher": {"type": "rich_text", "rich_text": {}},
            "Score Rank": {"type": "number", "number": {"format": "number"}},
            "Positive": {"type": "number", "number": {"format": "number"}},
            "Negative": {"type": "number", "number": {"format": "number"}},
            "User Score": {"type": "number", "number": {"format": "number"}},
            "Owners": {"type": "rich_text", "rich_text": {}},
            "Average Forever": {"type": "number", "number": {"format": "number"}},
            "Average 2 Weeks": {"type": "number", "number": {"format": "number"}},
            "Median Forever": {"type": "number", "number": {"format": "number"}},
            "Median 2 Weeks": {"type": "number", "number": {"format": "number"}},
            "Price": {"type": "number", "number": {"format": "number"}},
            "Initial Price": {"type": "number", "number": {"format": "number"}},
            "Discount": {"type": "number", "number": {"format": "number"}},
            "CCU": {"type": "number", "number": {"format": "number"}},
            "Languages": {"type": "multi_select", "multi_select": {}},
            "Genres": {"type": "multi_select", "multi_select": {}},
            "Tags": {"type": "multi_select", "multi_select": {}},
            "Review Count": {
                "type": "formula",
                "formula": {"expression": 'prop("Positive") + prop("Negative")'},
            },
            "Review Percent": {
                "type": "formula",
                "formula": {
                    "expression": (
                        'round(100 * prop("Positive") / (prop("Positive") + prop("Negative")))'
                    )
                },
            },
            "Average Forever (h)": {
                "type": "formula",
                "formula": {"expression": 'round(100 * prop("Average Forever") / 60) / 100'},
            },
            "Average 2 Weeks (h)": {
                "type": "formula",
                "formula": {"expression": 'round(100 * prop("Average 2 Weeks") / 60) / 100'},
            },
            "Median Forever (h)": {
                "type": "formula",
                "formula": {"expression": 'round(100 * prop("Median Forever") / 60) / 100'},
            },
            "Median 2 Weeks (h)": {
                "type": "formula",
                "formula": {"expression": 'round(100 * prop("Median 2 Weeks") / 60) / 100'},
            },
        }

    @override
    @staticmethod
    def get_notion_properties(data: SteamSpyGame) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.appid},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Developer": {"rich_text": [{"text": {"content": data.developer}}]},
            "Publisher": {"rich_text": [{"text": {"content": data.publisher}}]},
            "Score Rank": {"number": data.score_rank},
            "Positive": {"number": data.positive},
            "Negative": {"number": data.negative},
            "User Score": {"number": data.userscore},
            "Owners": {"rich_text": [{"text": {"content": data.owners}}]},
            "Average Forever": {"number": data.average_forever},
            "Average 2 Weeks": {"number": data.average_2weeks},
            "Median Forever": {"number": data.median_forever},
            "Median 2 Weeks": {"number": data.median_2weeks},
            "Price": {"number": data.price},
            "Initial Price": {"number": data.initialprice},
            "Discount": {"number": data.discount},
            "CCU": {"number": data.ccu},
            "Languages": {"multi_select": [{"name": lang} for lang in data.languages]},
            "Genres": {"multi_select": [{"name": genre} for genre in data.genres]},
            "Tags": {"multi_select": [{"name": tag} for tag in data.tags]},
        }

    @override
    @classmethod
    def retrieve_from_data(cls, data: SteamSpyGame) -> Self | None:
        if not hasattr(data, "appid"):
            raise ValueError(f"{data!r} has no 'appid' attribute")

        page: Self | None = (
            cast("QueryBuilder", cls.query())
            .filter(property="ID", number={"equals": data.appid})
            .first()
        )
        return page

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: SteamSpyGame,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        base_url = "https://shared.cloudflare.steamstatic.com/store_item_assets"
        return super().retrieve_or_create_from_data(
            data,
            icon_url or f"{base_url}/steam/apps/{data.appid}/logo.png",
            cover_url or f"{base_url}/steam/apps/{data.appid}/library_hero.jpg",
        )

from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import requests
import ultimate_notion as uno
import urllib3
from pydantic.dataclasses import dataclass
from ultimate_notion import PropType

from notion_videogames import notion

if TYPE_CHECKING:
    from _typeshed import SupportsKeysAndGetItem

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

        if response.ok:
            try:
                json = response.json()
            except requests.exceptions.JSONDecodeError:
                logger.exception("Failed to decode JSON response for appid %d", app_id)
                return None
        else:
            logger.error("Non-OK response for appid %d: %d", app_id, response.status_code)
            return None

        return SteamSpyGame.from_dict(json)


class SteamSpyNotionPageSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    developer = PropType.Text("Developer")
    publisher = PropType.Text("Publisher")
    score_rank = PropType.Number("Score Rank")
    positive = PropType.Number("Positive")
    negative = PropType.Number("Negative")
    userscore = PropType.Number("User Score")
    owners = PropType.Text("Owners")
    average_forever = PropType.Number("Average Forever")
    average_2weeks = PropType.Number("Average 2 Weeks")
    median_forever = PropType.Number("Median Forever")
    median_2weeks = PropType.Number("Median 2 Weeks")
    price = PropType.Number("Price")
    initialprice = PropType.Number("Initial Price")
    discount = PropType.Number("Discount")
    ccu = PropType.Number("CCU")
    languages = PropType.MultiSelect("Languages", options=[])
    genres = PropType.MultiSelect("Genres", options=[])
    tags = PropType.MultiSelect("Tags", options=[])
    review_count = PropType.Formula("Review Count", formula='prop("Positive") + prop("Negative")')
    review_percent = PropType.Formula(
        "Review Percent",
        formula='round(100 * prop("Positive") / (prop("Positive") + prop("Negative")))',
    )
    average_forever_h = PropType.Formula(
        "Average Forever (h)", formula='round(100 * prop("Average Forever") / 60) / 100'
    )
    average_2weeks_h = PropType.Formula(
        "Average 2 Weeks (h)", formula='round(100 * prop("Average 2 Weeks") / 60) / 100'
    )
    median_forever_h = PropType.Formula(
        "Median Forever (h)", formula='round(100 * prop("Median Forever") / 60) / 100'
    )
    median_2weeks_h = PropType.Formula(
        "Median 2 Weeks (h)", formula='round(100 * prop("Median 2 Weeks") / 60) / 100'
    )
    steam_url = PropType.Formula(
        "Steam URL", formula='concat("https://store.steampowered.com/app/", prop("ID"))'
    )


class SteamSpyNotionPage(notion.NotionPageType[SteamSpyGame]):
    schema = SteamSpyNotionPageSchema  # type: ignore[mutable-override]

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
    def retrieve_from_data(cls, data: SteamSpyGame) -> uno.Page | None:
        if not hasattr(data, "appid"):
            msg = f"{data!r} has no 'appid' attribute"
            raise ValueError(msg)

        return next(
            iter(cls.schema.get_db().query.filter(uno.prop("ID") == data.appid).execute()), None
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: SteamSpyGame,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        base_url = "https://shared.cloudflare.steamstatic.com/store_item_assets"
        return super().retrieve_or_create_from_data(
            data,
            icon_url=icon_url or f"{base_url}/steam/apps/{data.appid}/logo.png",
            cover_url=cover_url or f"{base_url}/steam/apps/{data.appid}/library_hero.jpg",
        )

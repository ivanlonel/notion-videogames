from __future__ import annotations

import functools
import json
import re
import time
from http import HTTPStatus
from typing import Any, ClassVar, override

import requests
import requests.adapters
import ultimate_notion as uno
import urllib3
from pydantic.dataclasses import dataclass
from ultimate_notion import PropType, props

from notion_videogames import notion


@dataclass(frozen=True)
class SteamGame:  # pylint: disable=too-many-instance-attributes
    appid: int
    name: str
    developer: str = ""
    publisher: str = ""
    positive: int = 0
    negative: int = 0
    ccu: int | None = None
    price: int | None = None
    initial_price: int | None = None
    discount: int | None = None
    languages: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


def _parse_languages(text: str) -> tuple[str, ...]:
    """Get the names from 'English<strong>*</strong>, French<br><strong>*</strong>languages...'."""
    names = re.sub(r"<[^>]+>|\*", "", text.split("<br>", maxsplit=1)[0])
    return tuple(name.strip() for name in names.split(",") if name.strip())


def _parse_prices(item: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    """Return the price, the price before any discount, and the discount."""
    if item.get("is_free"):
        return 0, 0, 0
    option = item.get("best_purchase_option")
    if not option:
        return None, None, None
    price = int(option["final_price_in_cents"])  # Steam sends these as strings
    return price, int(option.get("original_price_in_cents", price)), option.get("discount_pct", 0)


class SteamSession(requests.Session):
    """Reads Steam's public APIs. None of them needs a key, and they're mostly undocumented."""

    api_url: ClassVar[str] = "https://api.steampowered.com"
    details_url: ClassVar[str] = "https://store.steampowered.com/api/appdetails"
    timeout: ClassVar[float] = 30
    details_pause: ClassVar[float] = 1.5
    """Seconds to wait after each appdetails call, which allows about 200 per 5 minutes"""
    countries: ClassVar[tuple[str, ...]] = ("US", "BR")
    """Each store has games the other doesn't sell. Prices only come from the first one."""
    retry_policy: ClassVar[urllib3.util.retry.Retry] = urllib3.util.retry.Retry(
        total=5,
        backoff_factor=10,
        status_forcelist={429, 500, 502, 503, 504},
    )

    def __init__(self) -> None:
        super().__init__()

        self.mount("https://", requests.adapters.HTTPAdapter(max_retries=self.retry_policy))

    def _call(self, interface: str, method: str, **input_json: Any) -> dict[str, Any]:
        response = self.get(
            f"{self.api_url}/{interface}/{method}/v1/",
            params={"input_json": json.dumps(input_json)},
            timeout=self.timeout,
        )
        response.raise_for_status()
        answer: dict[str, Any] = response.json().get("response", {})
        return answer

    @functools.cached_property
    def _tag_names(self) -> dict[int, str]:
        tags = self._call("IStoreService", "GetTagList", language="english")["tags"]
        return {tag["tagid"]: tag["name"] for tag in tags}

    def _get_store_item(self, app_id: int) -> dict[str, Any] | None:
        for country in self.countries:
            response = self._call(
                "IStoreBrowseService",
                "GetItems",
                ids=[{"appid": app_id}],
                context={"language": "english", "country_code": country},
                data_request={
                    "include_basic_info": True,
                    "include_reviews": True,
                    "include_tag_count": 20,
                },
            )
            if "store_items" not in response:  # Steam reports failures as a 200 with nothing in it
                msg = f"GetItems returned nothing for {app_id}"
                raise LookupError(msg)

            item: dict[str, Any] = response["store_items"][0]
            if item.get("success") == 1 and item.get("name"):  # 15 means not sold in that country
                if country != self.countries[0]:  # Its prices would be in another currency
                    item.pop("best_purchase_option", None)
                return item
        return None

    def _get_details(self, app_id: int) -> dict[str, Any]:
        """Return what appdetails knows about the app, which is nothing for most delisted ones."""
        params: dict[str, str | int] = {"appids": app_id, "filters": "basic,genres"}
        response = self.get(self.details_url, params=params, timeout=self.timeout)
        response.raise_for_status()
        answer = response.json()
        time.sleep(self.details_pause)
        if not answer:  # Being rate limited can look like this
            msg = f"appdetails returned nothing for {app_id}"
            raise LookupError(msg)
        details: dict[str, Any] = answer.get(str(app_id), {}).get("data", {})
        return details

    def _get_review_totals(self, app_id: int, purchase_type: int) -> tuple[int, int]:
        summary = self._call(
            "IUserReviewsService",
            "GetAppReviews",
            appid=app_id,
            languages=["all"],  # Leaving this empty means English only
            num_per_page=1,  # 0 behaves like 20
            purchase_type=purchase_type,
        ).get("query_summary", {})
        return summary.get("total_positive", 0), summary.get("total_negative", 0)

    def _get_reviews(self, app_id: int, item: dict[str, Any]) -> tuple[int, int]:
        """Return the store page's counts: Steam purchases, or all reviews if it's free."""
        review_count = item.get("reviews", {}).get("summary_filtered", {}).get("review_count", 0)
        purchase_type = 1 if item.get("is_free") else 0
        totals = self._get_review_totals(app_id, purchase_type)
        # is_free is missing on delisted games, so try the other kind if these don't fit.
        if abs(sum(totals) - review_count) > 0.02 * review_count:
            totals = min(
                totals,
                self._get_review_totals(app_id, 1 - purchase_type),
                key=lambda counts: abs(sum(counts) - review_count),
            )
        return totals

    def _get_current_players(self, app_id: int) -> int | None:
        response = self.get(
            f"{self.api_url}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
            params={"appid": app_id},
            timeout=self.timeout,
        )
        if response.status_code == HTTPStatus.NOT_FOUND:
            return None
        response.raise_for_status()
        players: int | None = response.json().get("response", {}).get("player_count")
        return players

    def get_game(self, app_id: int) -> SteamGame | None:
        """Return the app's data, None if Steam doesn't have it. Raise if a request fails."""
        item = self._get_store_item(app_id)
        if item is None:
            return None

        details = self._get_details(app_id)
        positive, negative = self._get_reviews(app_id, item)
        price, initial_price, discount = _parse_prices(item)
        info = item.get("basic_info", {})

        return SteamGame(
            appid=app_id,
            name=item["name"],
            developer=", ".join(company["name"] for company in info.get("developers", [])),
            publisher=", ".join(company["name"] for company in info.get("publishers", [])),
            positive=positive,
            negative=negative,
            ccu=self._get_current_players(app_id),
            price=price,
            initial_price=initial_price,
            discount=discount,
            languages=_parse_languages(details.get("supported_languages") or ""),
            genres=tuple(genre["description"] for genre in details.get("genres", [])),
            tags=tuple(
                self._tag_names[tag["tagid"]]
                for tag in item.get("tags", [])
                if tag["tagid"] in self._tag_names
            ),
        )


class SteamNotionPageSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    developer = PropType.Text("Developer")
    publisher = PropType.Text("Publisher")
    positive = PropType.Number("Positive")
    negative = PropType.Number("Negative")
    price = PropType.Number("Price")
    initial_price = PropType.Number("Initial Price")
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
    steam_url = PropType.Formula(
        "Steam URL", formula='concat("https://store.steampowered.com/app/", prop("ID"))'
    )


class SteamNotionPage(notion.NotionPageType[SteamGame], schema=SteamNotionPageSchema):
    @override
    @classmethod
    def get_id(cls, data: SteamGame) -> int:
        return data.appid

    @override
    @classmethod
    def get_populated_properties_dict(cls, data: SteamGame) -> dict[str, props.PropertyValue]:
        # Delisted apps can come back with next to nothing, so whatever is missing gets left out:
        # a page keeps what it has rather than being blanked.
        numbers = {
            "CCU": data.ccu,
            "Price": data.price,
            "Initial Price": data.initial_price,
            "Discount": data.discount,
        }
        reviews = {"Positive": data.positive, "Negative": data.negative}
        texts = {"Developer": data.developer, "Publisher": data.publisher}
        options = {"Languages": data.languages, "Genres": data.genres, "Tags": data.tags}
        return (
            {"ID": props.Number(data.appid), "Name": props.Title(data.name)}
            | {name: props.Number(value) for name, value in numbers.items() if value is not None}
            | (
                {name: props.Number(n) for name, n in reviews.items()}
                if any(reviews.values())
                else {}
            )
            | {name: props.Text(value) for name, value in texts.items() if value}
            | {name: props.MultiSelect(value) for name, value in options.items() if value}
        )

    @override
    @classmethod
    def get_image_urls(cls, data: SteamGame) -> tuple[str | None, str | None]:
        base_url = "https://shared.cloudflare.steamstatic.com/store_item_assets"
        return (
            f"{base_url}/steam/apps/{data.appid}/logo.png",
            f"{base_url}/steam/apps/{data.appid}/library_hero.jpg",
        )

"""Offline checks: no network, no credentials, no Notion."""

from __future__ import annotations

import dataclasses
import logging
import types
import typing
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Self
from unittest.mock import MagicMock

import httpx
import pytest
import ultimate_notion as uno
from notion_client.errors import APIResponseError, HTTPResponseError, RequestTimeoutError
from ultimate_notion.obj_api.core import Unset
from ultimate_notion.schema import Formula, Rollup

from notion_videogames import custom_notion, hltb_notion, igdb_notion, notion, steamspy_notion
from notion_videogames.proto import proto

if TYPE_CHECKING:
    from ultimate_notion import props

type PageType = type[igdb_notion.IGDBNotionPage[Any]]

IGDB_PAGE_TYPES = igdb_notion.IGDBNotionPage.__subclasses__()

# Real responses, with long lists trimmed.
STEAMSPY_KNOWN_APP: dict[str, Any] = {
    "appid": 620,
    "name": "Portal 2",
    "developer": "Valve",
    "publisher": "Valve",
    "score_rank": "",
    "positive": 427835,
    "negative": 5675,
    "userscore": 0,
    "owners": "5,000,000 .. 10,000,000",
    "average_forever": 0,
    "average_2weeks": 0,
    "median_forever": 0,
    "median_2weeks": 0,
    "price": "999",
    "initialprice": "999",
    "discount": "0",
    "ccu": 1959,
    "languages": "English, French",
    "genre": "Action, Adventure",
    "tags": {"Platformer": 7477, "Puzzle": 7394},
}
STEAMSPY_UNKNOWN_APP: dict[str, Any] = {
    "appid": 1,
    "name": None,
    "developer": "",
    "publisher": "",
    "score_rank": "",
    "positive": 0,
    "negative": 0,
    "userscore": 0,
    "owners": "0 .. 20,000",
    "average_forever": 0,
    "average_2weeks": 0,
    "median_forever": 0,
    "median_2weeks": 0,
    "price": None,
    "initialprice": None,
    "discount": None,
    "ccu": 0,
    "languages": None,
    "genre": None,
    "tags": [],
}
HLTB_ENTRY: dict[str, Any] = {
    "game_id": 7231,
    "game_name": "Portal 2",
    "game_name_date": 0,
    "game_alias": "",
    "game_type": "game",
    "game_image": "Portal2cover.jpg",
    "comp_lvl_combine": 0,
    "comp_lvl_sp": 1,
    "comp_lvl_co": 1,
    "comp_lvl_mp": 1,
    "comp_main": 30894,
    "comp_plus": 49564,
    "comp_100": 82821,
    "comp_all": 38314,
    "comp_main_count": 5574,
    "comp_plus_count": 2465,
    "comp_100_count": 741,
    "comp_all_count": 8780,
    "invested_co": 34510,
    "invested_mp": 24321,
    "invested_co_count": 829,
    "invested_mp_count": 10,
    "count_comp": 40412,
    "count_speedrun": 53,
    "count_backlog": 25538,
    "count_review": 8207,
    "review_score": 90,
    "count_playing": 283,
    "count_retired": 1335,
    "profile_platform": "Linux, Mac, Nintendo Switch, PC, PlayStation 3, Xbox 360",
    "profile_popular": 1242,
    "release_world": 2011,
}


def _name(page_type: type) -> str:
    return page_type.__name__


def _text(value: props.PropertyValue) -> str:
    return str(value.value)


def _relation_ids(value: props.PropertyValue) -> list[str]:
    return [ref["id"] for ref in value.obj_ref.serialize_for_api()["relation"]]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("//images.igdb.com/a.jpg", "https://images.igdb.com/a.jpg"),
        ("https://images.igdb.com/a.jpg", "https://images.igdb.com/a.jpg"),
        ("http://images.igdb.com/a.jpg", "http://images.igdb.com/a.jpg"),
    ],
)
def test_add_https_scheme(url: str, expected: str) -> None:
    assert igdb_notion.add_https_scheme(url) == expected


# Stands in for the per-field type checks the generic mapping gave up: a schema attribute that
# matches neither a message field nor a computed value would raise on the first real page.
@pytest.mark.parametrize("page_type", IGDB_PAGE_TYPES, ids=_name)
def test_every_schema_prop_maps_to_a_message_field(page_type: PageType) -> None:
    message_type: Any = typing.get_args(types.get_original_bases(page_type)[0])[0]
    fields = {field.name for field in dataclasses.fields(message_type)}
    computed = page_type.computed(message_type(id=1))

    assert not [
        prop.attr_name
        for prop in page_type.schema.get_props()
        if not igdb_notion.is_unmapped(prop)
        and prop.attr_name not in fields
        and prop.attr_name not in computed
    ]


@pytest.mark.parametrize("page_type", IGDB_PAGE_TYPES, ids=_name)
def test_query_fields_resolve_every_relation(page_type: PageType) -> None:
    fields = page_type.get_query_fields()

    assert fields[0] == "*"
    assert len(fields) == len(set(fields))


def test_game_query_follows_nested_relations() -> None:
    fields = igdb_notion.Game.get_query_fields()

    assert "platforms.versions.platform_version_release_dates.*" in fields
    assert "involved_companies.company.logo.*" in fields


def test_absent_optionals_are_omitted() -> None:
    properties = igdb_notion.Company.get_populated_properties_dict(
        proto.Company(id=1, name="Acme")
    )

    assert "Logo" not in properties
    assert "Created At" not in properties
    assert properties["ID"].value == 1
    assert _text(properties["Name"]) == "Acme"
    assert properties["URL"].value is None
    assert _relation_ids(properties["Websites"]) == []


def test_long_text_is_not_truncated() -> None:
    text = "x" * 5000

    properties = igdb_notion.Company.get_populated_properties_dict(
        proto.Company(id=1, description=text)
    )

    assert _text(properties["Description"]) == text


def test_relations_are_capped_at_notions_limit(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        igdb_notion.CompanyWebsite, "retrieve_or_create_from_data", lambda _: uuid.uuid4()
    )
    websites = [proto.CompanyWebsite(id=i) for i in range(igdb_notion.MAX_RELATION_PAGES + 1)]

    with caplog.at_level(logging.WARNING):
        properties = igdb_notion.Company.get_populated_properties_dict(
            proto.Company(id=1, websites=websites)
        )

    assert len(_relation_ids(properties["Websites"])) == igdb_notion.MAX_RELATION_PAGES
    assert "Company.websites" in caplog.text


@pytest.mark.parametrize(
    ("page_type", "message", "expected"),
    [
        (igdb_notion.Screenshot, proto.Screenshot(id=7), "7"),
        (igdb_notion.ReleaseDate, proto.ReleaseDate(id=7, y=2020, m=3), "2020/3"),
        (
            igdb_notion.ReleaseDate,
            proto.ReleaseDate(id=7, y=2020, m=3, platform=proto.Platform(id=1, name="PC")),
            "PC - 2020/3",
        ),
        (igdb_notion.Website, proto.Website(id=7), "7"),
        (igdb_notion.Website, proto.Website(id=7, url="https://a.b"), "https://a.b"),
        (
            igdb_notion.Website,
            proto.Website(id=7, url="https://a.b", type=proto.WebsiteType(id=1, type="Steam")),
            "Steam",
        ),
    ],
)
def test_computed_titles(
    page_type: PageType, message: igdb_notion.IGDBMessage, expected: str
) -> None:
    assert page_type.computed(message)["title"] == expected


def test_title_field_is_read_when_the_message_has_one() -> None:
    properties = igdb_notion.GameVersionFeature.get_populated_properties_dict(
        proto.GameVersionFeature(id=1, title="Soundtrack")
    )

    assert _text(properties["Title"]) == "Soundtrack"


THUMB = "//images.igdb.com/igdb/image/upload/t_thumb/abc.jpg"
BASE = "https://images.igdb.com/igdb/image/upload"


@pytest.mark.parametrize(
    ("page_type", "message", "expected"),
    [
        (igdb_notion.Keyword, proto.Keyword(id=1), (None, None)),
        (igdb_notion.Cover, proto.Cover(id=1), (None, None)),
        (
            igdb_notion.Cover,
            proto.Cover(id=1, url=THUMB),
            (f"{BASE}/t_thumb/abc.jpg", f"{BASE}/t_cover_big_2x/abc.jpg"),
        ),
        (
            igdb_notion.Screenshot,
            proto.Screenshot(id=1, url=THUMB),
            (f"{BASE}/t_thumb/abc.jpg", f"{BASE}/t_1080p/abc.jpg"),
        ),
        (
            igdb_notion.Company,
            proto.Company(id=1, logo=proto.CompanyLogo(id=2, url=THUMB)),
            (f"{BASE}/t_logo_med/abc.jpg", f"{BASE}/t_logo_med/abc.jpg"),
        ),
        (igdb_notion.InvolvedCompany, proto.InvolvedCompany(id=1), (None, None)),
        (
            igdb_notion.InvolvedCompany,
            proto.InvolvedCompany(id=1, company=proto.Company(id=2)),
            (None, None),
        ),
        (
            igdb_notion.InvolvedCompany,
            proto.InvolvedCompany(
                id=1, company=proto.Company(id=2, logo=proto.CompanyLogo(id=3, url=THUMB))
            ),
            (f"{BASE}/t_logo_med/abc.jpg", f"{BASE}/t_logo_med/abc.jpg"),
        ),
    ],
)
def test_image_urls(
    page_type: PageType, message: igdb_notion.IGDBMessage, expected: tuple[str | None, str | None]
) -> None:
    assert page_type.get_image_urls(message) == expected


def _api_error(status: int) -> APIResponseError:
    return APIResponseError(
        code="any", status=status, message="", headers=httpx.Headers(), raw_body_text=""
    )


@pytest.mark.parametrize(
    "error",
    [
        _api_error(409),
        _api_error(429),
        _api_error(500),
        _api_error(503),
        RequestTimeoutError(),
        httpx.ConnectError("unreachable"),
    ],
    ids=repr,
)
def test_transient_errors_are_retried(error: Exception) -> None:
    assert notion.is_transient(error)


@pytest.mark.parametrize(
    "error",
    [_api_error(400), _api_error(401), _api_error(403), _api_error(404), ValueError()],
    ids=repr,
)
def test_permanent_errors_are_not_retried(error: Exception) -> None:
    assert not notion.is_transient(error)


class FakePage(uuid.UUID):
    """Passes for a Notion page: relations accept a UUID, and otherwise only `id` gets read."""

    @property
    def id(self) -> Self:
        return self


def _fake_page(*_: object, **__: object) -> FakePage:
    return FakePage(int=uuid.uuid4().int)


class FakeDataSource:
    """Just enough of a data source for page lookups: each query consumes one of `results`."""

    obj_ref = None

    def __init__(self) -> None:
        self.results: list[object] = []
        self.queries = 0

    @property
    def query(self) -> Self:
        return self

    def filter(self, _condition: object) -> Self:
        return self

    def execute(self) -> list[object]:
        self.queries += 1
        return [self.results.pop(0)] if self.results else []


@pytest.fixture(name="fake_notion")
def fixture_fake_notion(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    monkeypatch.setattr("time.sleep", lambda _: None)
    monkeypatch.setattr(notion, "_pages", {})
    data_source = FakeDataSource()
    for page_type in (igdb_notion.Company, igdb_notion.CompanyLogo, igdb_notion.Keyword):
        monkeypatch.setattr(page_type.schema, "_ds", data_source)
    pages = SimpleNamespace(
        create=MagicMock(side_effect=_fake_page),
        update=MagicMock(),
    )
    session = SimpleNamespace(cache={}, api=SimpleNamespace(pages=pages))
    monkeypatch.setattr(uno.Session, "get_active", lambda: session)
    monkeypatch.setattr(uno.Page, "wrap_obj_ref", lambda obj: obj)
    return SimpleNamespace(pages=pages, data_source=data_source)


def test_permanent_error_makes_one_attempt_at_any_depth(fake_notion: SimpleNamespace) -> None:
    fake_notion.pages.create.side_effect = _api_error(400)
    company = proto.Company(id=1, logo=proto.CompanyLogo(id=2))

    with pytest.raises(HTTPResponseError):
        igdb_notion.Company.retrieve_or_create_from_data(company)

    assert fake_notion.pages.create.call_count == 1


def test_transient_error_on_a_nested_page_retries_only_that_page(
    fake_notion: SimpleNamespace,
) -> None:
    created: list[Any] = [_fake_page(), _fake_page()]
    fake_notion.pages.create.side_effect = [_api_error(503), *created]
    company = proto.Company(id=1, logo=proto.CompanyLogo(id=2))

    page = igdb_notion.Company.retrieve_or_create_from_data(company)

    assert page is created[1]
    assert fake_notion.pages.create.call_count == 3


def test_retried_create_finds_a_page_that_landed_despite_the_error(
    fake_notion: SimpleNamespace,
) -> None:
    landed: Any = SimpleNamespace(id=uuid.uuid4())

    def create_times_out(*_: object, **__: object) -> None:
        fake_notion.data_source.results.append(landed)
        raise RequestTimeoutError

    fake_notion.pages.create.side_effect = create_times_out

    page = igdb_notion.Keyword.retrieve_or_create_from_data(proto.Keyword(id=1))

    assert page is landed
    assert fake_notion.pages.create.call_count == 1


def test_each_page_is_handled_once_per_run(fake_notion: SimpleNamespace) -> None:
    first = igdb_notion.Keyword.retrieve_or_create_from_data(proto.Keyword(id=1, name="a"))
    second = igdb_notion.Keyword.retrieve_or_create_from_data(proto.Keyword(id=1, name="b"))

    assert first is second
    assert fake_notion.data_source.queries == 1
    assert fake_notion.pages.create.call_count == 1


def test_existing_page_is_left_alone_by_default(fake_notion: SimpleNamespace) -> None:
    existing: Any = SimpleNamespace(id=uuid.uuid4(), obj_ref=object())
    fake_notion.data_source.results.append(existing)

    page = igdb_notion.Keyword.retrieve_or_create_from_data(proto.Keyword(id=1))

    assert page is existing
    fake_notion.pages.create.assert_not_called()
    fake_notion.pages.update.assert_not_called()


def test_update_does_not_clear_an_icon_or_cover_it_has_no_url_for(
    fake_notion: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(notion.NotionPageType, "update", True)
    existing: Any = SimpleNamespace(id=uuid.uuid4(), obj_ref=object())
    fake_notion.data_source.results.append(existing)

    page = igdb_notion.Keyword.retrieve_or_create_from_data(proto.Keyword(id=1, name="a"))

    assert page is existing
    args, kwargs = fake_notion.pages.update.call_args
    assert args == (existing.obj_ref,)
    assert kwargs["icon"] is Unset
    assert kwargs["cover"] is Unset
    assert "Name" in kwargs["properties"]


def test_custom_game_without_matches_leaves_those_links_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(igdb_notion.Game, "retrieve_or_create_from_data", lambda _: uuid.uuid4())

    properties = custom_notion.CustomGamePage.get_populated_properties_dict(
        custom_notion.CustomGame(proto.Game(id=1, name="Hades"))
    )

    assert set(properties) == {"Name", "IGDB"}


@pytest.mark.parametrize(
    ("page_type", "data"),
    [
        (
            hltb_notion.HLTBNotionPage,
            hltb_notion.HowLongToBeatGame.from_dict(HLTB_ENTRY | {"similarity": 1.0}),
        ),
        (
            steamspy_notion.SteamSpyNotionPage,
            steamspy_notion.SteamSpyGame.from_dict(STEAMSPY_KNOWN_APP),
        ),
    ],
    ids=lambda value: value.__name__ if isinstance(value, type) else "",
)
def test_hand_written_properties_are_writable_schema_props(
    page_type: type[notion.NotionPageType[Any]], data: object
) -> None:
    writable = {
        prop.name
        for prop in page_type.schema.get_props()
        if not isinstance(prop, Formula | Rollup)
    }

    assert set(page_type.get_populated_properties_dict(data)) <= writable

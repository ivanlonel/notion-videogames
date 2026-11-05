# pylint: disable=too-many-lines
"""Offline checks: no network, no credentials, no Notion."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import types
import typing
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Self
from unittest.mock import MagicMock

import httpx
import pytest
import requests
import ultimate_notion as uno
from notion_client.errors import APIResponseError, HTTPResponseError, RequestTimeoutError
from ultimate_notion import PropType
from ultimate_notion.errors import SchemaError
from ultimate_notion.obj_api.core import Unset
from ultimate_notion.schema import Formula, Relation, Rollup

from notion_videogames import (
    custom_notion,
    hltb_notion,
    igdb_notion,
    main,
    notion,
    steam_notion,
)
from notion_videogames.proto import proto

if TYPE_CHECKING:
    from ultimate_notion import props

type PageType = type[igdb_notion.IGDBNotionPage[Any]]

IGDB_PAGE_TYPES = igdb_notion.IGDBNotionPage.__subclasses__()

# Real responses, with long lists trimmed.
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
            steam_notion.SteamNotionPage,
            steam_notion.SteamGame(
                appid=1,
                name="A",
                developer="B",
                publisher="C",
                positive=1,
                negative=1,
                ccu=1,
                price=1,
                initial_price=1,
                discount=1,
                languages=("D",),
                genres=("E",),
                tags=("F",),
            ),
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


def _fake_response(
    *,
    json_data: object = None,
    content: bytes = b"",
    error: Exception | None = None,
    status_code: int = 200,
) -> MagicMock:
    response = MagicMock(spec=requests.Response, content=content, status_code=status_code)
    response.json.return_value = json_data
    response.raise_for_status.side_effect = error
    return response


@pytest.fixture(name="igdb_posts")
def fixture_igdb_posts(monkeypatch: pytest.MonkeyPatch) -> list[SimpleNamespace]:
    """Record the POSTs an IGDBSession makes, answering the token request and then `responses`."""
    posts: list[SimpleNamespace] = []

    def post(_: object, url: str, **kwargs: Any) -> MagicMock:
        posts.append(SimpleNamespace(url=url, **kwargs))
        return _fake_response(json_data={"access_token": "token"}, content=b"")

    monkeypatch.setattr(igdb_notion.IGDBSession, "post", post)
    return posts


def test_igdb_token_request_keeps_the_secret_out_of_the_url(
    igdb_posts: list[SimpleNamespace],
) -> None:
    session = igdb_notion.IGDBSession("client", "secret")

    assert "secret" not in igdb_posts[0].url
    assert igdb_posts[0].data["client_secret"] == "secret"
    assert igdb_posts[0].timeout
    assert session.headers["Authorization"] == "Bearer token"
    assert session.headers["Client-ID"] == "client"


def test_igdb_rejected_credentials_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        igdb_notion.IGDBSession,
        "post",
        lambda *_, **__: _fake_response(error=requests.HTTPError("403")),
    )

    with pytest.raises(requests.HTTPError):
        igdb_notion.IGDBSession("client", "wrong")


def test_igdb_game_query(igdb_posts: list[SimpleNamespace]) -> None:
    session = igdb_notion.IGDBSession("client", "secret")

    assert session.find_games(["hades", "portal-2"]) == []

    assert igdb_posts[-1].url.endswith("/games.pb")
    assert igdb_posts[-1].timeout
    assert 'where slug=("hades","portal-2");' in igdb_posts[-1].data
    assert igdb_posts[-1].data.startswith("fields *,")


def test_igdb_steam_query(igdb_posts: list[SimpleNamespace]) -> None:
    session = igdb_notion.IGDBSession("client", "secret")

    assert session.find_steam_games(["620"]) == []

    assert igdb_posts[-1].url.endswith("/external_games.pb")
    assert 'where uid=("620") & external_game_source=1;' in igdb_posts[-1].data
    assert igdb_posts[-1].data.startswith("fields uid,game.*,")


def test_igdb_answer_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = bytes(proto.GameResult(games=[proto.Game(id=1, name="Hades")]))
    monkeypatch.setattr(
        igdb_notion.IGDBSession,
        "post",
        lambda *_, **__: _fake_response(json_data={"access_token": "token"}, content=answer),
    )

    games = igdb_notion.IGDBSession("client", "secret").find_games(["hades"])

    assert [game.name for game in games] == ["Hades"]


def _external_game(source_id: int, uid: str) -> proto.ExternalGame:
    source = proto.ExternalGameSource(id=source_id)
    return proto.ExternalGame(id=uuid.uuid4().int % 1000, uid=uid, external_game_source=source)


@pytest.mark.parametrize(
    ("external_games", "expected"),
    [
        ([], None),
        ([_external_game(5, "abc")], None),
        ([_external_game(5, "abc"), _external_game(1, "620")], 620),
        ([_external_game(1, "not-a-number")], None),
    ],
)
def test_steam_app_id(external_games: list[proto.ExternalGame], expected: int | None) -> None:
    game = proto.Game(id=1, external_games=external_games)

    assert igdb_notion.get_steam_app_id(game) == expected


def _hltb_entry(game_id: int, similarity: float, year: int) -> SimpleNamespace:
    return SimpleNamespace(
        similarity=similarity,
        release_world=year,
        json_content=HLTB_ENTRY | {"game_id": game_id, "release_world": year},
    )


def _use_hltb_results(monkeypatch: pytest.MonkeyPatch, results: object) -> None:
    wrapper = SimpleNamespace(search=lambda *_, **__: results)
    monkeypatch.setattr(hltb_notion, "_get_wrapper", lambda: wrapper)


def test_hltb_most_similar_game_wins_over_a_closer_year(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_hltb_results(monkeypatch, [_hltb_entry(1, 0.7, 2016), _hltb_entry(2, 0.9, 1993)])

    match = hltb_notion.HLTBNotionPage.get_best_match("Doom", 2016)

    assert match is not None
    assert match.game_id == 2
    assert match.similarity == 0.9


@pytest.mark.parametrize(
    ("release_year", "expected_id"),
    [(1993, 1), (2016, 2), (2017, 2), (None, 1)],
)
def test_hltb_ties_go_to_the_nearest_release_year(
    monkeypatch: pytest.MonkeyPatch, release_year: int | None, expected_id: int
) -> None:
    _use_hltb_results(monkeypatch, [_hltb_entry(1, 1.0, 1993), _hltb_entry(2, 1.0, 2016)])

    match = hltb_notion.HLTBNotionPage.get_best_match("Doom", release_year)

    assert match is not None
    assert match.game_id == expected_id


def test_hltb_no_results_is_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_hltb_results(monkeypatch, [])

    assert hltb_notion.HLTBNotionPage.get_best_match("Unknown Game") is None


def test_hltb_failed_search_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_hltb_results(monkeypatch, None)

    with pytest.raises(LookupError):
        hltb_notion.HLTBNotionPage.get_best_match("Any Game")


def test_every_relation_targets_an_earlier_database() -> None:
    created: set[object] = set()
    page_types: list[type[notion.NotionPageType[Any]]] = [
        *main.DB_PAGE_TYPES.values(),
        custom_notion.CustomGamePage,
    ]
    for page_type in page_types:
        for prop in page_type.schema.get_props():
            if isinstance(prop, Relation) and not igdb_notion.is_unmapped(prop):
                assert prop.schema in created, f"{page_type.__name__}.{prop.attr_name}"
        created.add(page_type.schema)


@pytest.mark.parametrize(
    ("url", "slugs", "steam_app_ids"),
    [
        ("https://www.igdb.com/games/hades", ["hades"], []),
        ("https://igdb.com/games/hades/", ["hades"], []),
        ("https://www.igdb.com/games/hades/presskit?x=1", ["hades"], []),
        ("https://www.igdb.com/games/hades%202", ["hades 2"], []),
        ("https://store.steampowered.com/app/620", [], ["620"]),
        ("https://store.steampowered.com/app/620/Portal_2/", [], ["620"]),
        ("https://store.steampowered.com/agecheck/app/620/", [], ["620"]),
    ],
)
def test_source_urls_recognized(url: str, slugs: list[str], steam_app_ids: list[str]) -> None:
    assert main.parse_source_urls([url]) == main.SourceUrls(slugs, steam_app_ids, [])


@pytest.mark.parametrize(
    "url",
    [
        "https://www.igdb.com/games",
        "https://www.igdb.com/games/",
        "https://www.igdb.com/companies/valve",
        'https://www.igdb.com/games/a"b',
        "https://www.igdb.com/games/a%22b",
        "https://www.igdb.com/games/a%5Cb",
        "https://notigdb.com/games/hades",
        "https://store.steampowered.com/app/",
        "https://store.steampowered.com/app/portal",
        "https://store.steampowered.com/app/620x",
        "https://store.steampowered.com/sub/620",
        "https://steamcommunity.com/app/620",
        "not a url",
        "http://[bad",
    ],
)
def test_source_urls_unrecognized(url: str) -> None:
    assert main.parse_source_urls([url]) == main.SourceUrls([], [], [url])


def test_source_urls_drop_repeats() -> None:
    url = "https://www.igdb.com/games/hades"

    assert main.parse_source_urls([url, url]).slugs == ["hades"]


def _set_env(monkeypatch: pytest.MonkeyPatch, *, token: str | None, **env: str) -> None:
    for field in dataclasses.fields(main.Settings):
        monkeypatch.delenv(field.name.upper(), raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    config = SimpleNamespace(ultimate_notion=SimpleNamespace(token=token))
    monkeypatch.setattr(main, "get_or_create_cfg", lambda: config)


def test_settings_name_everything_missing_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, token=None, SOURCE_DB_ID="source")

    with pytest.raises(SystemExit) as error:
        main.Settings.from_env()

    for name in ("IGDB_CLIENT_ID", "IGDB_CLIENT_SECRET", "MAIN_PAGE_ID", "NOTION_TOKEN"):
        assert name in str(error.value)
    assert "SOURCE_DB_ID" not in str(error.value)


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(
        monkeypatch,
        token="token",
        IGDB_CLIENT_ID="id",
        IGDB_CLIENT_SECRET="secret",
        SOURCE_DB_ID="source",
        MAIN_PAGE_ID="page",
        MAIN_GAMES_DB_NAME="Games",
    )

    assert main.Settings.from_env() == main.Settings("id", "secret", "source", "page", "Games")


@pytest.mark.parametrize("argument", ["0", "-1", "many"])
def test_limit_must_be_a_positive_number(argument: str) -> None:
    with pytest.raises(SystemExit):
        main.parse_args(["--limit", argument])


def _declared_columns() -> type[uno.Schema]:
    class Declared(uno.Schema):
        name = PropType.Title("Name")
        notes = PropType.Text("Notes")

    return Declared


def test_columns_added_in_notion_are_tolerated() -> None:
    declared = _declared_columns()

    class Reflected(uno.Schema):
        name = PropType.Title("Name")
        notes = PropType.Text("Notes")
        mine = PropType.Checkbox("My Column")

    assert main.drop_undeclared_columns(Reflected, declared) == ["My Column"]
    Reflected.assert_consistency_with(declared)
    assert len(declared.get_props()) == 2


def test_columns_missing_from_notion_are_still_an_error() -> None:
    declared = _declared_columns()

    class Reflected(uno.Schema):
        name = PropType.Title("Name")

    assert main.drop_undeclared_columns(Reflected, declared) == []
    with pytest.raises(SchemaError):
        Reflected.assert_consistency_with(declared)


def test_columns_changed_in_notion_are_still_an_error() -> None:
    declared = _declared_columns()

    class Reflected(uno.Schema):
        name = PropType.Title("Name")
        notes = PropType.Checkbox("Notes")

    assert main.drop_undeclared_columns(Reflected, declared) == []
    with pytest.raises(SchemaError):
        Reflected.assert_consistency_with(declared)


class FakeIGDB:
    """An IGDBSession answering from fixed data, and failing for the values in `failing`."""

    def __init__(self, *games: proto.Game, failing: tuple[str, ...] = ()) -> None:
        self.games = games
        self.failing = failing

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def _check(self, values: tuple[str, ...]) -> None:
        if set(values) & set(self.failing):
            raise requests.exceptions.RetryError

    def find_games(self, slugs: tuple[str, ...]) -> list[proto.Game]:
        self._check(slugs)
        return [game for game in self.games if game.slug in slugs]

    def find_steam_games(self, app_ids: tuple[str, ...]) -> list[proto.ExternalGame]:
        self._check(app_ids)
        return [
            proto.ExternalGame(id=game.id, uid=external.uid, game=game)
            for game in self.games
            for external in game.external_games
            if external.uid in app_ids
        ]


SETTINGS = main.Settings("id", "secret", "source", "page", "Games")


def test_fetch_games_merges_urls_of_the_same_game(monkeypatch: pytest.MonkeyPatch) -> None:
    hades = proto.Game(id=1, slug="hades", external_games=[_external_game(1, "1145360")])
    monkeypatch.setattr(igdb_notion, "IGDBSession", lambda *_: FakeIGDB(hades))
    summary = main.Summary()

    games = main.fetch_games(SETTINGS, ["hades"], ["1145360"], summary)

    assert [game.id for game in games] == [1]
    assert not summary.not_on_igdb


def test_fetch_games_reports_what_igdb_does_not_have(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(igdb_notion, "IGDBSession", lambda *_: FakeIGDB())
    summary = main.Summary()

    assert not main.fetch_games(SETTINGS, ["unknown"], ["999"], summary)
    assert summary.not_on_igdb == ["unknown", "999"]
    assert not summary.failed


def test_fetch_games_survives_a_failed_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    hades = proto.Game(id=1, slug="hades")
    monkeypatch.setattr(main, "IGDB_BATCH_SIZE", 1)
    monkeypatch.setattr(igdb_notion, "IGDBSession", lambda *_: FakeIGDB(hades, failing=("bad",)))
    summary = main.Summary()

    games = main.fetch_games(SETTINGS, ["bad", "hades"], [], summary)

    assert [game.id for game in games] == [1]
    assert summary.failed == ["bad"]
    assert not summary.not_on_igdb


def test_fetch_games_stops_when_igdb_rejects_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    igdb = MagicMock(spec=igdb_notion.IGDBSession)
    igdb.__enter__.return_value = igdb
    igdb.find_games.side_effect = requests.HTTPError("401")
    monkeypatch.setattr(igdb_notion, "IGDBSession", lambda *_: igdb)

    with pytest.raises(requests.HTTPError):
        main.fetch_games(SETTINGS, ["hades"], [], main.Summary())


def test_fetch_games_skips_igdb_when_there_is_nothing_to_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()
    monkeypatch.setattr(igdb_notion, "IGDBSession", session)

    assert not main.fetch_games(SETTINGS, [], [], main.Summary())
    session.assert_not_called()


def test_failed_lookups_still_create_the_game(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_: object, **__: object) -> None:
        raise KeyError

    monkeypatch.setattr(hltb_notion.HLTBNotionPage, "get_best_match", fail)
    create = MagicMock()
    monkeypatch.setattr(custom_notion.CustomGamePage, "retrieve_or_create_from_data", create)
    steam = MagicMock(spec=steam_notion.SteamSession)
    steam.get_game.side_effect = requests.ConnectionError
    game = proto.Game(id=1, name="Hades", external_games=[_external_game(1, "1145360")])
    summary = main.Summary()

    main.sync_game(game, steam, summary)

    assert create.call_args.args == (custom_notion.CustomGame(game),)
    assert summary.incomplete == ["Hades (HowLongToBeat)", "Hades (Steam)"]


def test_release_year_reaches_the_hltb_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    match = MagicMock(return_value=None)
    monkeypatch.setattr(hltb_notion.HLTBNotionPage, "get_best_match", match)
    monkeypatch.setattr(custom_notion.CustomGamePage, "retrieve_or_create_from_data", MagicMock())
    released = dt.datetime(2020, 9, 17, tzinfo=dt.UTC)

    main.sync_game(
        proto.Game(id=1, name="Hades", first_release_date=released),
        MagicMock(spec=steam_notion.SteamSession),
        main.Summary(),
    )

    match.assert_called_once_with("Hades", 2020)


def test_a_failing_game_does_not_stop_the_others(monkeypatch: pytest.MonkeyPatch) -> None:
    def sync(game: proto.Game, *_: object) -> SimpleNamespace:
        if game.name == "Bad":
            raise ValueError(game.name)
        return SimpleNamespace(url="https://notion.so/page")

    monkeypatch.setattr(main, "sync_game", sync)
    summary = main.Summary()

    main.sync_games([proto.Game(id=1, name="Bad"), proto.Game(id=2, name="Good")], summary)

    assert summary.failed == ["Bad"]
    assert summary.written == 1


def test_find_imported_follows_the_library_relations(monkeypatch: pytest.MonkeyPatch) -> None:
    igdb_page = SimpleNamespace(props={"ID": 1.0, "Slug": "hades"})
    steam_page = SimpleNamespace(props={"ID": 1145360.0})
    pages = [
        SimpleNamespace(props={"IGDB": [igdb_page], "Steam": [steam_page]}),
        SimpleNamespace(props={"IGDB": [], "Steam": []}),  # A row added by hand
    ]
    data_sources: dict[type[notion.NotionPageType[Any]], list[SimpleNamespace]] = {
        igdb_notion.Game: [igdb_page],
        steam_notion.SteamNotionPage: [steam_page],
        custom_notion.CustomGamePage: pages,
    }
    for page_type, results in data_sources.items():
        data_source = SimpleNamespace(get_all_pages=lambda results=results: results)
        monkeypatch.setattr(page_type.schema, "_ds", data_source)

    assert custom_notion.find_imported() == custom_notion.Imported(
        frozenset({1}), frozenset({"hades"}), frozenset({"1145360"})
    )


def test_hltb_fields_it_no_longer_sends_keep_what_pages_already_hold() -> None:
    properties = hltb_notion.HLTBNotionPage.get_populated_properties_dict(
        hltb_notion.HowLongToBeatGame.from_dict(HLTB_ENTRY | {"similarity": 1.0})
    )

    assert not {"Steam ID", "Profile Devs", "comp_lvl_spd"} & set(properties)
    assert properties["Profile Platforms"].value


def test_hltb_fields_are_written_when_sent() -> None:
    properties = hltb_notion.HLTBNotionPage.get_populated_properties_dict(
        hltb_notion.HowLongToBeatGame.from_dict(
            HLTB_ENTRY
            | {"similarity": 1.0, "profile_steam": 620, "profile_dev": "Valve", "comp_lvl_spd": 1}
        )
    )

    assert properties["Steam ID"].value == 620
    assert properties["comp_lvl_spd"].value == 1
    assert "Profile Devs" in properties


# Real responses from Steam, with long lists trimmed.
HITMAN: dict[str, Any] = {
    "id": 6860,
    "success": 1,
    "name": "Hitman: Blood Money",
    "type": 0,
    "best_purchase_option": {
        "final_price_in_cents": "99",
        "original_price_in_cents": "999",
        "discount_pct": 90,
    },
    "basic_info": {
        "publishers": [{"name": "Io-Interactive A/S"}],
        "developers": [{"name": "Io-Interactive A/S"}],
    },
    "reviews": {"summary_filtered": {"review_count": 13828, "percent_positive": 93}},
    "tags": [
        {"tagid": 1687, "weight": 1865},
        {"tagid": 19, "weight": 1124},
        {"tagid": 7, "weight": 1},
    ],
}
COUNTER_STRIKE: dict[str, Any] = {
    "id": 730,
    "success": 1,
    "name": "Counter-Strike 2",
    "is_free": True,
    "type": 0,
    "basic_info": {"publishers": [{"name": "Valve"}], "developers": [{"name": "Valve"}]},
    "reviews": {"summary_filtered": {"review_count": 9969034, "percent_positive": 85}},
}
NOT_SOLD: dict[str, Any] = {"item_type": 0, "id": 1, "success": 15, "visible": False, "name": ""}
TAG_LIST = [{"tagid": 1687, "name": "Stealth"}, {"tagid": 19, "name": "Action"}]
LANGUAGES_TEXT = (
    "English<strong>*</strong>, French<strong>*</strong>, Spanish - Spain<strong>*</strong>, "
    "Czech, Polish<br><strong>*</strong>languages with full audio support"
)


class FakeSteam:
    """Answers a SteamSession's requests from fixed data, keeping what was asked."""

    def __init__(
        self,
        items: dict[str, dict[str, Any]],
        reviews: dict[int, tuple[int, int]] | None = None,
        details: object = None,
    ) -> None:
        self.items = items
        self.reviews = reviews or {}
        self.details = details
        self.players: tuple[int, dict[str, Any]] = (200, {"response": {"player_count": 98}})
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, *, params: dict[str, Any], timeout: float) -> MagicMock:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        body = json.loads(params.get("input_json", "{}"))
        if "GetItems" in url:
            item = self.items.get(body["context"]["country_code"], NOT_SOLD)
            return _fake_response(json_data={"response": {"store_items": [item]}})
        if "GetAppReviews" in url:
            positive, negative = self.reviews.get(body["purchase_type"], (0, 0))
            summary = {"total_positive": positive, "total_negative": negative}
            return _fake_response(json_data={"response": {"query_summary": summary}})
        if "GetTagList" in url:
            return _fake_response(json_data={"response": {"tags": TAG_LIST}})
        if "GetNumberOfCurrentPlayers" in url:
            return _fake_response(json_data=self.players[1], status_code=self.players[0])
        assert "appdetails" in url
        return _fake_response(json_data=self.details)

    def purchase_types(self) -> list[int]:
        bodies = [
            json.loads(c["params"]["input_json"]) for c in self.calls if "Reviews" in c["url"]
        ]
        return [body["purchase_type"] for body in bodies]


def _steam_session(monkeypatch: pytest.MonkeyPatch, fake: FakeSteam) -> steam_notion.SteamSession:
    monkeypatch.setattr("time.sleep", lambda _: None)
    session = steam_notion.SteamSession()
    monkeypatch.setattr(session, "get", fake.get)
    return session


def _details(app_id: int) -> dict[str, Any]:
    genres = [{"id": "1", "description": "Action"}, {"id": "25", "description": "Adventure"}]
    data = {"supported_languages": LANGUAGES_TEXT, "genres": genres}
    return {str(app_id): {"success": True, "data": data}}


def test_steam_game_on_sale(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSteam({"US": HITMAN}, {0: (13000, 828)}, _details(6860))

    game = _steam_session(monkeypatch, fake).get_game(6860)

    assert game == steam_notion.SteamGame(
        appid=6860,
        name="Hitman: Blood Money",
        developer="Io-Interactive A/S",
        publisher="Io-Interactive A/S",
        positive=13000,
        negative=828,
        ccu=98,
        price=99,
        initial_price=999,
        discount=90,
        languages=("English", "French", "Spanish - Spain", "Czech", "Polish"),
        genres=("Action", "Adventure"),
        tags=("Stealth", "Action"),  # Tag 7 isn't in the list of names
    )
    assert fake.purchase_types() == [0]


def test_steam_free_game_counts_all_reviews_and_costs_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeSteam({"US": COUNTER_STRIKE}, {1: (8544730, 1419062)}, _details(730))

    game = _steam_session(monkeypatch, fake).get_game(730)

    assert game is not None
    assert (game.price, game.initial_price, game.discount) == (0, 0, 0)
    assert (game.positive, game.negative) == (8544730, 1419062)
    assert fake.purchase_types() == [1]


def test_steam_full_price_has_no_discount(monkeypatch: pytest.MonkeyPatch) -> None:
    item = HITMAN | {"best_purchase_option": {"final_price_in_cents": "999"}}
    fake = FakeSteam({"US": item}, {0: (13000, 828)}, _details(6860))

    game = _steam_session(monkeypatch, fake).get_game(6860)

    assert game is not None
    assert (game.price, game.initial_price, game.discount) == (999, 999, 0)


def test_steam_game_not_on_sale_has_no_price(monkeypatch: pytest.MonkeyPatch) -> None:
    item = {key: value for key, value in HITMAN.items() if key != "best_purchase_option"}
    fake = FakeSteam({"US": item}, {0: (13000, 828)}, _details(6860))

    game = _steam_session(monkeypatch, fake).get_game(6860)

    assert game is not None
    assert (game.price, game.initial_price, game.discount) == (None, None, None)


def test_steam_reviews_try_the_other_kind_when_they_do_not_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeSteam({"US": HITMAN}, {0: (100, 28), 1: (13000, 828)}, _details(6860))

    game = _steam_session(monkeypatch, fake).get_game(6860)

    assert game is not None
    assert (game.positive, game.negative) == (13000, 828)
    assert fake.purchase_types() == [0, 1]


def test_steam_falls_back_to_the_next_store_without_its_prices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeSteam({"BR": HITMAN}, {0: (13000, 828)}, _details(6860))

    game = _steam_session(monkeypatch, fake).get_game(6860)

    assert game is not None
    assert game.name == "Hitman: Blood Money"
    assert game.price is None


def test_steam_game_it_does_not_have_is_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSteam({})

    assert _steam_session(monkeypatch, fake).get_game(1) is None
    assert [c["url"].count("GetItems") for c in fake.calls] == [1, 1]


def test_steam_delisted_game_without_details_keeps_what_it_has(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    details = {"6860": {"success": False}}
    fake = FakeSteam({"US": HITMAN}, {0: (13000, 828)}, details)

    game = _steam_session(monkeypatch, fake).get_game(6860)

    assert game is not None
    assert not game.languages
    assert not game.genres


def test_steam_reporting_failure_as_an_empty_answer_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _steam_session(monkeypatch, FakeSteam({}))
    monkeypatch.setattr(
        session, "get", lambda *_, **__: _fake_response(json_data={"response": {}})
    )

    with pytest.raises(LookupError):
        session.get_game(6860)


def test_steam_rate_limiting_details_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSteam({"US": HITMAN}, {0: (13000, 828)}, None)

    with pytest.raises(LookupError):
        _steam_session(monkeypatch, fake).get_game(6860)


def test_steam_failed_request_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _steam_session(monkeypatch, FakeSteam({}))
    monkeypatch.setattr(
        session, "get", lambda *_, **__: _fake_response(error=requests.HTTPError("500"))
    )

    with pytest.raises(requests.HTTPError):
        session.get_game(6860)


def test_steam_app_without_player_counts_has_none(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSteam({"US": HITMAN}, {0: (13000, 828)}, _details(6860))
    fake.players = (404, {"response": {"result": 42}})

    game = _steam_session(monkeypatch, fake).get_game(6860)

    assert game is not None
    assert game.ccu is None


def test_steam_every_request_has_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSteam({"US": HITMAN}, {0: (13000, 828)}, _details(6860))

    _steam_session(monkeypatch, fake).get_game(6860)

    assert len(fake.calls) >= 5
    assert all(call["timeout"] for call in fake.calls)


def test_steam_page_leaves_out_what_steam_did_not_send() -> None:
    properties = steam_notion.SteamNotionPage.get_populated_properties_dict(
        steam_notion.SteamGame(appid=1, name="Delisted")
    )

    assert set(properties) == {"ID", "Name"}


def test_steam_page_writes_a_free_price_and_no_discount() -> None:
    properties = steam_notion.SteamNotionPage.get_populated_properties_dict(
        steam_notion.SteamGame(appid=1, name="Free", price=0, initial_price=0, discount=0)
    )

    assert properties["Price"].value == 0
    assert properties["Discount"].value == 0


def _steam_library(monkeypatch: pytest.MonkeyPatch, *ids: int | None) -> list[SimpleNamespace]:
    pages = [
        SimpleNamespace(title=f"Game {i}", url=f"https://notion.so/{i}", props={"ID": app_id})
        for i, app_id in enumerate(ids)
    ]
    data_source = SimpleNamespace(get_all_pages=lambda: pages)
    monkeypatch.setattr(steam_notion.SteamNotionPage.schema, "_ds", data_source)
    monkeypatch.setattr(steam_notion.SteamNotionPage, "update", False)
    return pages


def _steam_client(monkeypatch: pytest.MonkeyPatch, *games: object) -> MagicMock:
    client = MagicMock(spec=steam_notion.SteamSession)
    client.__enter__.return_value = client
    client.get_game.side_effect = games
    monkeypatch.setattr(steam_notion, "SteamSession", lambda: client)
    return client


def test_refresh_rewrites_each_page_and_survives_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    _steam_library(monkeypatch, 1, 2, 3, 4)
    good = [steam_notion.SteamGame(appid=i, name=str(i)) for i in (1, 4)]
    client = _steam_client(monkeypatch, good[0], requests.ConnectionError(), None, good[1])
    write = MagicMock()
    monkeypatch.setattr(steam_notion.SteamNotionPage, "retrieve_or_create_from_data", write)
    summary = main.Summary()

    main.refresh_steam_pages(summary, limit=None, dry_run=False)

    assert [call.args[0].appid for call in write.call_args_list] == [1, 4]
    assert steam_notion.SteamNotionPage.update
    assert summary.written == 2
    assert summary.failed == ["Game 1"]
    assert summary.not_on_steam == ["Game 2"]
    assert client.get_game.call_count == 4


def test_refresh_honours_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    _steam_library(monkeypatch, 1, 2, 3)
    client = _steam_client(monkeypatch, None, None, None)
    summary = main.Summary()

    main.refresh_steam_pages(summary, limit=2, dry_run=False)

    assert client.get_game.call_count == 2


def test_refresh_dry_run_writes_and_fetches_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _steam_library(monkeypatch, 1, 2)
    client = _steam_client(monkeypatch)
    write = MagicMock()
    monkeypatch.setattr(steam_notion.SteamNotionPage, "retrieve_or_create_from_data", write)

    main.refresh_steam_pages(main.Summary(), limit=None, dry_run=True)

    client.get_game.assert_not_called()
    write.assert_not_called()
    assert not steam_notion.SteamNotionPage.update


def test_refresh_and_update_are_exclusive() -> None:
    with pytest.raises(SystemExit):
        main.parse_args(["--update", "--refresh-steam"])


def test_refresh_touches_neither_the_source_nor_igdb(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    session.__enter__.return_value = session
    monkeypatch.setattr(uno.Session, "get_or_create", lambda: session)
    monkeypatch.setattr(main, "bind_databases", lambda *_, **__: [])
    refresh, import_games = MagicMock(), MagicMock()
    monkeypatch.setattr(main, "refresh_steam_pages", refresh)
    monkeypatch.setattr(main, "import_games", import_games)

    main.run(main.parse_args(["--refresh-steam"]), SETTINGS)

    refresh.assert_called_once()
    import_games.assert_not_called()


def test_steam_page_caps_options_at_notions_limit(caplog: pytest.LogCaptureFixture) -> None:
    languages = tuple(f"Language {i}" for i in range(steam_notion.MAX_OPTIONS + 3))

    with caplog.at_level(logging.WARNING):
        properties = steam_notion.SteamNotionPage.get_populated_properties_dict(
            steam_notion.SteamGame(appid=1, name="Many", languages=languages)
        )

    assert len(properties["Languages"].value) == steam_notion.MAX_OPTIONS
    assert "Many has 103 Languages" in caplog.text

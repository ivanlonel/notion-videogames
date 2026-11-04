"""Offline checks: no network, no credentials, no Notion."""

from __future__ import annotations

import dataclasses
import logging
import types
import typing
import uuid
from typing import TYPE_CHECKING, Any

import pytest

from notion_videogames import igdb_notion
from notion_videogames.proto import proto

if TYPE_CHECKING:
    from ultimate_notion import props

type PageType = type[igdb_notion.IGDBNotionPage[Any]]

IGDB_PAGE_TYPES = igdb_notion.IGDBNotionPage.__subclasses__()


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

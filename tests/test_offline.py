"""Offline checks: no network, no credentials, no Notion."""

from __future__ import annotations

import pytest

from notion_videogames import igdb_notion


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

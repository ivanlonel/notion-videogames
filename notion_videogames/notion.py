from __future__ import annotations

import abc
import functools
import logging
from typing import TYPE_CHECKING, Any, ClassVar

import tenacity
import ultimate_notion as uno
from notion_client.errors import HTTPResponseError, RequestTimeoutError
from ultimate_notion.obj_api import blocks

if TYPE_CHECKING:
    from uuid import UUID

logger: logging.Logger = logging.getLogger(__name__)


class NotionPageType[T](abc.ABC):
    schema: ClassVar[type[uno.Schema]]
    """The database schema class for this page type"""

    update: ClassVar[bool] = False
    """Whether pages that already exist should be updated"""

    @classmethod
    @abc.abstractmethod
    def get_notion_properties(cls, data: T) -> dict[str, dict[str, Any]]: ...

    @classmethod
    @abc.abstractmethod
    def retrieve_from_data(cls, data: T) -> uno.Page | None: ...

    @classmethod
    def create_from_data(
        cls,
        data: T,
        *,
        icon: dict[str, dict[str, str]] | None = None,
        cover: dict[str, dict[str, str]] | None = None,
    ) -> uno.Page:
        return uno.Page.wrap_obj_ref(
            blocks.Page.model_validate(
                uno.Session.get_active().api.pages.raw_api.create(
                    parent={"type": "database_id", "database_id": str(cls.schema.get_db().id)},
                    properties=cls.get_notion_properties(data),
                    icon=icon,
                    cover=cover,
                )
            )
        )

    @classmethod
    def update_from_data(
        cls,
        page: uno.Page | str | UUID,
        data: T,
        *,
        icon: dict[str, dict[str, str]] | None = None,
        cover: dict[str, dict[str, str]] | None = None,
    ) -> uno.Page:
        return uno.Page.wrap_obj_ref(
            blocks.Page.model_validate(
                uno.Session.get_active().api.pages.raw_api.update(
                    page_id=str(page.id if isinstance(page, uno.Page) else page),
                    properties=cls.get_notion_properties(data),
                    icon=icon,
                    cover=cover,
                )
            )
        )

    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    @tenacity.retry(
        retry=tenacity.retry_if_exception_type((HTTPResponseError, RequestTimeoutError)),
        wait=tenacity.wait.wait_random_exponential(multiplier=3.75, max=960),
        stop=tenacity.stop.stop_after_attempt(10),
        reraise=True,
        before_sleep=tenacity.before_sleep.before_sleep_log(logger, logging.INFO, exc_info=True),
    )
    def retrieve_or_create_from_data(
        cls,
        data: T,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        icon = {"external": {"url": icon_url}} if icon_url else None
        cover = {"external": {"url": cover_url}} if cover_url else None

        if page := cls.retrieve_from_data(data):
            return cls.update_from_data(page, data, icon=icon, cover=cover) if cls.update else page

        return cls.create_from_data(data, icon=icon, cover=cover)

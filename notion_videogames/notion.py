from __future__ import annotations

import abc
import itertools
import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar, override

import httpx
import tenacity
import ultimate_notion as uno
from notion_client.errors import HTTPResponseError, RequestTimeoutError
from ultimate_notion.obj_api.core import Unset

if TYPE_CHECKING:
    from ultimate_notion import props
    from ultimate_notion.query import Condition

logger: logging.Logger = logging.getLogger(__name__)

# ponytail: process-wide, which suits a CLI that runs one sync per process.
_pages: dict[tuple[type, int], uno.Page] = {}
"""Pages already handled in this run, so each one is looked up and written at most once"""


def is_transient(error: BaseException) -> bool:
    """Tell whether a Notion error may go away by itself, rather than fail the same way again."""
    if isinstance(error, HTTPResponseError):
        return (
            error.status in {HTTPStatus.CONFLICT, HTTPStatus.TOO_MANY_REQUESTS}
            or error.status >= HTTPStatus.INTERNAL_SERVER_ERROR
        )
    return isinstance(error, RequestTimeoutError | httpx.TransportError)


retry_transient = tenacity.retry(
    retry=tenacity.retry_if_exception(is_transient),
    wait=tenacity.wait.wait_random_exponential(multiplier=3.75, max=960),
    stop=tenacity.stop.stop_after_attempt(10),
    reraise=True,
    before_sleep=tenacity.before_sleep.before_sleep_log(logger, logging.WARNING),
)


class NotionPageType[T](abc.ABC):
    schema: ClassVar[type[uno.Schema]]
    """The database schema class for this page type"""

    update: ClassVar[bool] = False
    """Whether pages that already exist should be updated"""

    @override
    def __init_subclass__(cls, *, schema: type[uno.Schema] | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if schema is not None:
            cls.schema = schema

    @classmethod
    @abc.abstractmethod
    def get_id(cls, data: T) -> int:
        """Return the data's id in its source system."""

    @classmethod
    @abc.abstractmethod
    def get_populated_properties_dict(cls, data: T) -> dict[str, props.PropertyValue]: ...

    @classmethod
    @abc.abstractmethod
    def get_image_urls(cls, data: T) -> tuple[str | None, str | None]:
        """Return the URLs of the page's icon and cover, if it has them."""

    @classmethod
    def get_lookup_condition(cls, data: T) -> Condition:
        """Return the filter that finds the page holding this data."""
        return uno.prop("ID") == cls.get_id(data)

    @classmethod
    def _first_match(cls, condition: Condition) -> uno.Page | None:
        return next(iter(cls.schema.get_ds().query.filter(condition).execute()), None)

    @classmethod
    def retrieve_or_create_from_data(cls, data: T) -> uno.Page:
        key = cls, cls.get_id(data)
        if key not in _pages:
            _pages[key] = cls._retrieve_or_create(data)
        return _pages[key]

    @classmethod
    def _retrieve_or_create(cls, data: T) -> uno.Page:
        # Retries wrap single API calls. Related pages are resolved between those calls, because a
        # retry around that recursion would multiply the attempts at every nesting level.
        condition = cls.get_lookup_condition(data)
        page = retry_transient(cls._first_match)(condition)
        if page is not None and not cls.update:
            return page

        properties = {
            name: value.obj_ref for name, value in cls.get_populated_properties_dict(data).items()
        }
        icon_url, cover_url = cls.get_image_urls(data)
        icon = uno.url(icon_url).obj_ref if icon_url else None
        cover = uno.url(cover_url).obj_ref if cover_url else None
        session = uno.Session.get_active()

        if page is not None:
            # Unset leaves the current icon and cover alone, while None would remove them.
            retry_transient(session.api.pages.update)(
                page.obj_ref, properties=properties, icon=icon or Unset, cover=cover or Unset
            )
            return page

        attempts = itertools.count(1)

        @retry_transient
        def create() -> uno.Page:
            # An earlier attempt may have reached Notion despite failing, e.g. on a timeout.
            if next(attempts) > 1 and (found := cls._first_match(condition)) is not None:
                return found

            created = uno.Page.wrap_obj_ref(
                session.api.pages.create(
                    cls.schema.get_ds().obj_ref, properties=properties, cover=cover, icon=icon
                )
            )
            session.cache[created.id] = created
            return created

        return create()

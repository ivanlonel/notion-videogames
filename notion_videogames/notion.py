from __future__ import annotations

import abc
import functools
import logging
from typing import TYPE_CHECKING, ClassVar

import tenacity
import ultimate_notion as uno
from notion_client.errors import HTTPResponseError, RequestTimeoutError
from pydantic import ValidationError
from ultimate_notion.core import Wrapper
from ultimate_notion.emoji import CustomEmoji, Emoji
from ultimate_notion.errors import ReadOnlyPropertyError, SchemaError
from ultimate_notion.obj_api.core import Unset, UnsetType

if TYPE_CHECKING:
    from ultimate_notion import props
    from ultimate_notion.obj_api import blocks
    from ultimate_notion.schema import SchemaModel

logger: logging.Logger = logging.getLogger(__name__)


class NotionPageType[T](abc.ABC):
    schema: ClassVar[type[uno.Schema]]
    """The database schema class for this page type"""

    update: ClassVar[bool] = False
    """Whether pages that already exist should be updated"""

    @classmethod
    @abc.abstractmethod
    def get_populated_properties_dict(cls, data: T) -> dict[str, props.PropertyValue]: ...

    @classmethod
    @abc.abstractmethod
    def retrieve_from_data(cls, data: T) -> uno.Page | None: ...

    @classmethod
    def validate_and_build_schema_model(cls, data: T) -> SchemaModel:
        # Borrowed code from uno.Database.create_page
        populated_properties = cls.get_populated_properties_dict(data)
        schema_property_names = {prop.name for prop in cls.schema.get_props()}

        if not set(populated_properties).issubset(schema_property_names):
            msg = (
                f"Attributes {', '.join(set(populated_properties) - schema_property_names)}"
                f" not defined for properties in schema {cls.schema.__name__}"
            )
            raise SchemaError(msg)
        if ro_props := set(populated_properties) & {
            prop.name for prop in cls.schema.get_ro_props()
        }:
            msg = f"Read-only properties {', '.join(ro_props)} cannot be set"
            raise ReadOnlyPropertyError(msg)

        validator = cls.schema.to_pydantic_model(with_ro_props=False)
        try:
            schema_model = validator(**populated_properties)
        except ValidationError as e:
            msg = f"Invalid keyword arguments or read-only properties are overwritten:\n{e}"
            raise SchemaError(msg) from e

        return schema_model

    @classmethod
    def create_from_data(
        cls,
        data: T,
        *,
        cover: uno.AnyFile | None = None,
        icon: uno.AnyFile | Emoji | CustomEmoji | str | None = None,
    ) -> uno.Page:
        if isinstance(icon, str) and not isinstance(icon, (Emoji, CustomEmoji)):
            icon = Emoji(icon)

        session = uno.Session.get_active()

        page = uno.Page.wrap_obj_ref(
            session.api.pages.create(
                cls.schema.get_db().obj_ref,
                properties=cls.validate_and_build_schema_model(data).to_dict(),
                cover=None if cover is None else cover.obj_ref,
                icon=None if icon is None else icon.obj_ref,
            )
        )
        session.cache[page.id] = page

        return page

    @classmethod
    def update_from_data(
        cls,
        page: uno.Page | blocks.Page,
        data: T,
        *,
        cover: uno.AnyFile | UnsetType | None = Unset,
        icon: uno.AnyFile | Emoji | CustomEmoji | str | UnsetType | None = Unset,
    ) -> None:
        if isinstance(icon, str) and not isinstance(icon, (Emoji, CustomEmoji)):
            icon = Emoji(icon)

        uno.Session.get_active().api.pages.update(
            page.obj_ref if isinstance(page, uno.Page) else page,
            properties=cls.validate_and_build_schema_model(data).to_dict(),
            cover=cover.obj_ref if isinstance(cover, uno.AnyFile) else cover,
            icon=icon.obj_ref if isinstance(icon, Wrapper) else icon,
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
        cover_url: str | None = None,
        icon_url: str | None = None,
    ) -> uno.Page:
        cover = uno.url(cover_url) if cover_url else None
        icon = uno.url(icon_url) if icon_url else None

        if page := cls.retrieve_from_data(data):
            if cls.update:
                cls.update_from_data(page, data, cover=cover, icon=icon)
            return page

        return cls.create_from_data(data, cover=cover, icon=icon)

from __future__ import annotations

import abc
import functools
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Self, TypeVar, cast

import tenacity
from notion_client.errors import HTTPResponseError, RequestTimeoutError
from notional.orm import ConnectedPage, connected_page
from notional.schema import PropertyObject

if TYPE_CHECKING:
    from uuid import UUID

    from notional import Session
    from notional.blocks import Database, DataRecord


T = TypeVar("T")

logger: logging.Logger = logging.getLogger(__name__)


class ConnectablePage(Generic[T], ConnectedPage, abc.ABC):  # type: ignore[misc]

    update: ClassVar[bool] = False
    """Whether pages that already exist should be updated"""

    @classmethod
    @abc.abstractmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]: ...

    @classmethod
    @abc.abstractmethod
    def get_notion_properties(cls, data: T) -> dict[str, dict[str, Any]]: ...

    @classmethod
    @abc.abstractmethod
    def retrieve_from_data(cls, data: T) -> Self | None: ...

    @classmethod
    def connect(cls, session: Session, database: Database) -> None:
        for key, val in vars(connected_page(session=session, source_db=database, cls=cls)).items():
            setattr(cls, key, val)

    @classmethod
    def create_database(
        cls,
        parent: str | UUID | DataRecord,
        title: str | None = None,
        session: Session | None = None,
    ) -> Database:
        notional_session = session or cls._notional__session

        if notional_session is None:
            _msg = "Cannot create Database; invalid session"
            raise ValueError(_msg)

        return notional_session.databases.create(
            parent=parent,
            schema={k: PropertyObject.parse_obj(v) for k, v in cls.get_notion_schema().items()},
            title=title,
        )

    @classmethod
    def create_from_data(
        cls,
        data: T,
        icon: dict[str, dict[str, str]] | None = None,
        cover: dict[str, dict[str, str]] | None = None,
    ) -> Self:
        if cls._notional__session is None:
            _msg = "Cannot create Page; invalid session"
            raise ValueError(_msg)

        if cls._notional__database is None:
            _msg = "Cannot create Page; invalid database"
            raise ValueError(_msg)

        instance: Self = cls.parse_obj(
            cast("Session", cls._notional__session).client.pages.create(
                parent={"type": "database_id", "database_id": str(cls._notional__database)},
                properties=cls.get_notion_properties(data),
                icon=icon,
                cover=cover,
            )
        )
        return instance

    @classmethod
    def update_from_data(
        cls,
        page_id: str | UUID,
        data: T,
        icon: dict[str, dict[str, str]] | None = None,
        cover: dict[str, dict[str, str]] | None = None,
    ) -> Self:
        if cls._notional__session is None:
            _msg = "Cannot update Page; invalid session"
            raise ValueError(_msg)

        instance: Self = cls.parse_obj(
            cast("Session", cls._notional__session).client.pages.update(
                page_id=str(page_id),
                properties=cls.get_notion_properties(data),
                icon=icon,
                cover=cover,
            )
        )
        return instance

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
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        icon = {"external": {"url": icon_url}} if icon_url else None
        cover = {"external": {"url": cover_url}} if cover_url else None

        if page := cls.retrieve_from_data(data):
            return cls.update_from_data(page.id, data, icon, cover) if cls.update else page

        return cls.create_from_data(data, icon, cover)

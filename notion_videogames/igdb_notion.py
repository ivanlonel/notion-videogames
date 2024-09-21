# pylint: disable=protected-access,too-many-lines
from __future__ import annotations

import functools
import itertools
import urllib.parse
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, AnyStr, Final, Self, TypeVar, cast, override

import betterproto

from notion_videogames import igdb_proto, notion

if TYPE_CHECKING:
    from uuid import UUID

    from notional.query import QueryBuilder
else:

    def _enum_type__call__(cls: betterproto.enum.EnumType, value: int) -> betterproto.Enum:
        try:
            return cls._value_map_[value]
        except KeyError:
            return cls.__new__(cls, name=None, value=value)
        except TypeError:
            raise ValueError(f"{value!r} is not a valid {cls.__name__}") from None

    # Monkeypatch betterproto.enum.EnumType.__call__ to deal with unknown enum values
    betterproto.enum.EnumType.__call__ = _enum_type__call__

T = TypeVar("T", bound=betterproto.Message)

# https://developers.notion.com/reference/request-limits
MAX_RELATION_PAGES: Final[int] = 100
MAX_TEXT_LENGTH: Final[int] = 2000


def _to_datetime(self: betterproto._Timestamp) -> datetime:
    if self.seconds < 1e12:
        offset = timedelta(seconds=self.seconds, microseconds=self.nanos // 1000)
    else:
        offset = timedelta(seconds=self.seconds // 1000, microseconds=self.nanos // 1000000)
    return betterproto.DATETIME_ZERO + offset


# Monkeypatch betterproto._Timestamp.to_datetime to deal with timestamps in milliseconds
betterproto._Timestamp.to_datetime = _to_datetime  # type: ignore[method-assign]


def _hash(self: betterproto.Message) -> int:
    return hash(bytes(self))


# Monkeypatch betterproto.Message adding a __hash__ method so instances can be used in lru_cache
betterproto.Message.__hash__ = _hash  # type: ignore[assignment,method-assign]


def add_https_scheme(url: AnyStr) -> AnyStr:
    parsed_url = urllib.parse.urlparse(url)

    if parsed_url.scheme:
        # If there's already a scheme, return the original URL
        return url

    # If there's no scheme, add 'https'
    new_components = (
        "https" if isinstance(url, str) else b"https",  # type: ignore[redundant-expr]
    ) + parsed_url[1:]
    return urllib.parse.urlunparse(new_components)


class IGDBNotionPage(notion.ConnectablePage[T]):
    @override
    @classmethod
    def retrieve_from_data(cls, data: T) -> Self | None:
        if not hasattr(data, "id"):
            raise ValueError(f"{data!r} has no 'id' attribute")

        page: Self | None = (
            cast("QueryBuilder", cls.query())
            .filter(property="ID", number={"equals": data.id})
            .first()
        )
        return page

    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return ("*",)


class AgeRating(IGDBNotionPage[igdb_proto.AgeRating]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            AgeRatingContentDescription._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        age_rating_content_description_db_id: str | UUID,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.AgeRatingCategoryEnum.__members__
                        if name != "AGERATING_CATEGORY_NULL"
                    ]
                },
            },
            "Content Descriptions": {
                "type": "relation",
                "relation": {
                    "database_id": str(age_rating_content_description_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Rating": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.AgeRatingRatingEnum.__members__
                        if name != "AGERATING_RATING_NULL"
                    ]
                },
            },
            "Rating Cover URL": {"type": "url", "url": {}},
            "Synopsis": {"type": "rich_text", "rich_text": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.AgeRating) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Category": {
                "select": (
                    {"name": data.category.name}
                    if data.category.name != "AGERATING_CATEGORY_NULL"
                    else None
                )
            },
            "Content Descriptions": {
                "relation": [
                    {"id": str(AgeRatingContentDescription.retrieve_or_create_from_data(desc).id)}
                    for desc in data.content_descriptions
                ]
            },
            "Rating": {
                "select": (
                    {"name": data.rating.name}
                    if data.rating.name != "AGERATING_RATING_NULL"
                    else None
                )
            },
            "Rating Cover URL": {"url": data.rating_cover_url or None},
            "Synopsis": {"rich_text": [{"text": {"content": data.synopsis}}]},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {
                "title": [{"text": {"content": f"{data.category.name} - {data.rating.name}"}}]
            },
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (
                    f"content_descriptions.{f}"
                    for f in AgeRatingContentDescription.get_query_fields()
                ),
            )
        )


class AgeRatingContentDescription(IGDBNotionPage[igdb_proto.AgeRatingContentDescription]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.AgeRatingContentDescriptionCategoryEnum.__members__
                        if name != "AGERATINGCONTENTDESCRIPTION_CATEGORY_NULL"
                    ]
                },
            },
            "Description": {"type": "rich_text", "rich_text": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(
        data: igdb_proto.AgeRatingContentDescription,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Category": {
                "select": (
                    {"name": data.category.name}
                    if data.category.name != "AGERATINGCONTENTDESCRIPTION_CATEGORY_NULL"
                    else None
                )
            },
            "Description": {"rich_text": [{"text": {"content": data.description}}]},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": f"{data.category.name} - {data.id}"}}]},
        }


class AlternativeName(IGDBNotionPage[igdb_proto.AlternativeName]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Comment": {"type": "rich_text", "rich_text": {}},
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Name": {"type": "title", "title": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.AlternativeName) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Comment": {"rich_text": [{"text": {"content": data.comment}}]},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class Artwork(IGDBNotionPage[igdb_proto.Artwork]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Alpha Channel": {"type": "checkbox", "checkbox": {}},
            "Animated": {"type": "checkbox", "checkbox": {}},
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Height": {"type": "number", "number": {"format": "number"}},
            "Image ID": {"type": "rich_text", "rich_text": {}},
            "URL": {"type": "url", "url": {}},
            "Width": {"type": "number", "number": {"format": "number"}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Artwork) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Alpha Channel": {"checkbox": data.alpha_channel},
            "Animated": {"checkbox": data.animated},
            "Height": {"number": data.height},
            "Image ID": {"rich_text": [{"text": {"content": data.image_id}}]},
            "URL": {"url": data.url or None},
            "Width": {"number": data.width},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": str(data.id)}}]},
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.Artwork,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_1080p")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class Character(IGDBNotionPage[igdb_proto.Character]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            Game._notional__database,
            CharacterMugShot._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        game_db_id: str | UUID, character_mug_shot_db_id: str | UUID
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "AKAs": {"type": "multi_select", "multi_select": {}},
            "Country Name": {"type": "rich_text", "rich_text": {}},
            "Created At": {"type": "date", "date": {}},
            "Description": {"type": "rich_text", "rich_text": {}},
            "Games": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Gender": {
                "type": "select",
                "select": {
                    "options": [{"name": name} for name in igdb_proto.GenderGenderEnum.__members__]
                },
            },
            "Mug Shot": {
                "type": "relation",
                "relation": {
                    "database_id": str(character_mug_shot_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Name": {"type": "title", "title": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Species": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.CharacterSpeciesEnum.__members__
                        if name != "CHARACTER_SPECIES_NULL"
                    ]
                },
            },
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Character) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "AKAs": {"multi_select": [{"name": aka} for aka in data.akas]},
            "Country Name": {"rich_text": [{"text": {"content": data.country_name}}]},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Description": {"rich_text": [{"text": {"content": data.description}}]},
            "Games": {
                "relation": [
                    {"id": str(Game.retrieve_or_create_from_data(game).id)} for game in data.games
                ]
            },
            "Gender": {"type": "select", "select": {"name": data.gender.name}},
            "Mug Shot": {
                "relation": [
                    {"id": str(CharacterMugShot.retrieve_or_create_from_data(data.mug_shot).id)}
                ]
            },
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Species": {
                "type": "select",
                "select": (
                    {"name": data.species.name}
                    if data.species.name != "CHARACTER_SPECIES_NULL"
                    else None
                ),
            },
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"games.{f}" for f in Game.get_query_fields()),
                (f"mug_shot.{f}" for f in CharacterMugShot.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.Character,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.mug_shot.url:
            icon_url = add_https_scheme(data.mug_shot.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class CharacterMugShot(IGDBNotionPage[igdb_proto.CharacterMugShot]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Alpha Channel": {"type": "checkbox", "checkbox": {}},
            "Animated": {"type": "checkbox", "checkbox": {}},
            "Height": {"type": "number", "number": {"format": "number"}},
            "Image ID": {"type": "rich_text", "rich_text": {}},
            "URL": {"type": "url", "url": {}},
            "Width": {"type": "number", "number": {"format": "number"}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.CharacterMugShot) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Alpha Channel": {"checkbox": data.alpha_channel},
            "Animated": {"checkbox": data.animated},
            "Height": {"number": data.height},
            "Image ID": {"rich_text": [{"text": {"content": data.image_id}}]},
            "URL": {"url": data.url or None},
            "Width": {"number": data.width},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": str(data.id)}}]},
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.CharacterMugShot,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class Collection(IGDBNotionPage[igdb_proto.Collection]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            Game._notional__database,
            CollectionType._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        game_db_id: str | UUID, collection_type_db_id: str | UUID
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Created At": {"type": "date", "date": {}},
            "Games": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Name": {"type": "title", "title": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Type": {
                "type": "relation",
                "relation": {
                    "database_id": str(collection_type_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            # "As Parent Relations": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(collection_relation_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            # "As Child Relations": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(collection_relation_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Collection) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Games": {
                "relation": [
                    {"id": str(Game.retrieve_or_create_from_data(game).id)} for game in data.games
                ]
            },
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Type": {
                "relation": [
                    {"id": str(CollectionType.retrieve_or_create_from_data(data.type).id)}
                ]
            },
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"games.{f}" for f in Game.get_query_fields()),
                (f"type.{f}" for f in CollectionType.get_query_fields()),
                # (
                #     f"as_parent_relations.{f}"
                #     for f in CollectionRelation.get_query_fields()
                # ),
                # (
                #     f"as_child_relations.{f}"
                #     for f in CollectionRelation.get_query_fields()
                # ),
            )
        )


class CollectionMembership(IGDBNotionPage[igdb_proto.CollectionMembership]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            Game._notional__database,
            Collection._notional__database,
            CollectionMembershipType._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        game_db_id: str | UUID,
        collection_db_id: str | UUID,
        collection_membership_type_db_id: str | UUID,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Game": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Collection": {
                "type": "relation",
                "relation": {
                    "database_id": str(collection_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Type": {
                "type": "relation",
                "relation": {
                    "database_id": str(collection_membership_type_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Updated At": {"type": "date", "date": {}},
            "Created At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @classmethod
    def get_notion_properties(
        cls, data: igdb_proto.CollectionMembership
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Game": {"relation": [{"id": str(Game.retrieve_or_create_from_data(data.game).id)}]},
            "Collection": {
                "relation": [
                    {"id": str(Collection.retrieve_or_create_from_data(data.collection).id)}
                ]
            },
            "Type": {
                "relation": [
                    {
                        "id": str(
                            CollectionMembershipType.retrieve_or_create_from_data(data.type).id
                        )
                    }
                ]
            },
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": f"{data.game.name} - {data.collection.name}"
                            f" - {data.type.name}"
                        }
                    }
                ]
            },
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"game.{f}" for f in Game.get_query_fields()),
                (f"collection.{f}" for f in Collection.get_query_fields()),
                (f"type.{f}" for f in CollectionMembershipType.get_query_fields()),
            )
        )


class CollectionMembershipType(IGDBNotionPage[igdb_proto.CollectionMembershipType]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            CollectionType._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        collection_type_db_id: str | UUID,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Description": {"type": "rich_text", "rich_text": {}},
            "Allowed Collection Type": {
                "type": "relation",
                "relation": {
                    "database_id": str(collection_type_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Updated At": {"type": "date", "date": {}},
            "Created At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(
        data: igdb_proto.CollectionMembershipType,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Description": {"rich_text": [{"text": {"content": data.description}}]},
            "Allowed Collection Type": {
                "relation": [
                    {
                        "id": str(
                            CollectionType.retrieve_or_create_from_data(
                                data.allowed_collection_type
                            ).id
                        )
                    }
                ]
            },
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"allowed_collection_type.{f}" for f in CollectionType.get_query_fields()),
            )
        )


class CollectionRelation(IGDBNotionPage[igdb_proto.CollectionRelation]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            Collection._notional__database,
            CollectionRelationType._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        collection_db_id: str | UUID, collection_relation_type_db_id: str | UUID
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Child Collection": {
                "type": "relation",
                "relation": {
                    "database_id": str(collection_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Parent Collection": {
                "type": "relation",
                "relation": {
                    "database_id": str(collection_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Type": {
                "type": "relation",
                "relation": {
                    "database_id": str(collection_relation_type_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Updated At": {"type": "date", "date": {}},
            "Created At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @classmethod
    def get_notion_properties(
        cls, data: igdb_proto.CollectionRelation
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Child Collection": {
                "relation": [
                    {"id": str(Collection.retrieve_or_create_from_data(data.child_collection).id)}
                ]
            },
            "Parent Collection": {
                "relation": [
                    {"id": str(Collection.retrieve_or_create_from_data(data.parent_collection).id)}
                ]
            },
            "Type": {
                "relation": [
                    {"id": str(CollectionRelationType.retrieve_or_create_from_data(data.type).id)}
                ]
            },
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": f"{data.parent_collection.name}"
                            f" - {data.child_collection.name} - {data.type.name}"
                        }
                    }
                ]
            },
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"child_collection.{f}" for f in Collection.get_query_fields()),
                (f"parent_collection.{f}" for f in Collection.get_query_fields()),
                (f"type.{f}" for f in CollectionRelationType.get_query_fields()),
            )
        )


class CollectionRelationType(IGDBNotionPage[igdb_proto.CollectionRelationType]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            CollectionType._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        collection_type_db_id: str | UUID,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Description": {"type": "rich_text", "rich_text": {}},
            "Allowed Child Type": {
                "type": "relation",
                "relation": {
                    "database_id": str(collection_type_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Allowed Parent Type": {
                "type": "relation",
                "relation": {
                    "database_id": str(collection_type_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Updated At": {"type": "date", "date": {}},
            "Created At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(
        data: igdb_proto.CollectionRelationType,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Description": {"rich_text": [{"text": {"content": data.description}}]},
            "Allowed Child Type": {
                "relation": [
                    {
                        "id": str(
                            CollectionType.retrieve_or_create_from_data(data.allowed_child_type).id
                        )
                    }
                ]
            },
            "Allowed Parent Type": {
                "relation": [
                    {
                        "id": str(
                            CollectionType.retrieve_or_create_from_data(
                                data.allowed_parent_type
                            ).id
                        )
                    }
                ]
            },
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"allowed_child_type.{f}" for f in CollectionType.get_query_fields()),
                (f"allowed_parent_type.{f}" for f in CollectionType.get_query_fields()),
            )
        )


class CollectionType(IGDBNotionPage[igdb_proto.CollectionType]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Description": {"type": "rich_text", "rich_text": {}},
            "Updated At": {"type": "date", "date": {}},
            "Created At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.CollectionType) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Description": {"rich_text": [{"text": {"content": data.description}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class Company(IGDBNotionPage[igdb_proto.Company]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            CompanyLogo._notional__database,
            CompanyWebsite._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        company_logo_db_id: str | UUID, company_website_db_id: str | UUID
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Change Date": {"type": "date", "date": {}},
            "Change Date Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.DateFormatChangeDateCategoryEnum.__members__
                    ]
                },
            },
            # "Changed Company ID": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(company_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Country": {"type": "number", "number": {"format": "number"}},
            "Created At": {"type": "date", "date": {}},
            "Description": {"type": "rich_text", "rich_text": {}},
            # "Developed": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Logo": {
                "type": "relation",
                "relation": {
                    "database_id": str(company_logo_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Name": {"type": "title", "title": {}},
            # "Parent": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(company_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Start Date": {"type": "date", "date": {}},
            "Start Date Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.DateFormatChangeDateCategoryEnum.__members__
                    ]
                },
            },
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Websites": {
                "type": "relation",
                "relation": {
                    "database_id": str(company_website_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Company) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Change Date": {"type": "date", "date": {"start": data.change_date.isoformat()}},
            "Change Date Category": {
                "type": "select",
                "select": {"name": data.change_date_category.name},
            },
            "Country": {"number": data.country},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Description": {
                "rich_text": [{"text": {"content": data.description[:MAX_TEXT_LENGTH]}}]
            },
            "Logo": {
                "relation": [{"id": str(CompanyLogo.retrieve_or_create_from_data(data.logo).id)}]
            },
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Start Date": {"type": "date", "date": {"start": data.start_date.isoformat()}},
            "Start Date Category": {
                "type": "select",
                "select": {"name": data.start_date_category.name},
            },
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Websites": {
                "relation": [
                    {"id": str(CompanyWebsite.retrieve_or_create_from_data(site).id)}
                    for site in data.websites
                ]
            },
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                # (f"changed_company_id.{f}" for f in Company.get_query_fields()),
                # (f"developed.{f}" for f in Game.get_query_fields()),
                (f"logo.{f}" for f in CompanyLogo.get_query_fields()),
                # (f"parent.{f}" for f in Company.get_query_fields()),
                (f"websites.{f}" for f in CompanyWebsite.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.Company,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.logo.url:
            icon_url = add_https_scheme(data.logo.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class CompanyLogo(IGDBNotionPage[igdb_proto.CompanyLogo]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Alpha Channel": {"type": "checkbox", "checkbox": {}},
            "Animated": {"type": "checkbox", "checkbox": {}},
            "Height": {"type": "number", "number": {"format": "number"}},
            "Image ID": {"type": "rich_text", "rich_text": {}},
            "URL": {"type": "url", "url": {}},
            "Width": {"type": "number", "number": {"format": "number"}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.CompanyLogo) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Alpha Channel": {"checkbox": data.alpha_channel},
            "Animated": {"checkbox": data.animated},
            "Height": {"number": data.height},
            "Image ID": {"rich_text": [{"text": {"content": data.image_id}}]},
            "URL": {"url": data.url or None},
            "Width": {"number": data.width},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": str(data.id)}}]},
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.CompanyLogo,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class CompanyWebsite(IGDBNotionPage[igdb_proto.CompanyWebsite]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name.removeprefix("WEBSITE_")}
                        for name in igdb_proto.WebsiteCategoryEnum.__members__
                        if name != "WEBSITE_CATEGORY_NULL"
                    ]
                },
            },
            "Trusted": {"type": "checkbox", "checkbox": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.CompanyWebsite) -> dict[str, dict[str, Any]]:
        category = (
            data.category.name.removeprefix("WEBSITE_")
            if data.category.name and data.category.name != "WEBSITE_CATEGORY_NULL"
            else None
        )

        return {
            "ID": {"number": data.id},
            "Category": {
                "type": "select",
                "select": ({"name": category} if category else None),
            },
            "Trusted": {"checkbox": data.trusted},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": category or data.url or str(data.id)}}]},
        }


class Cover(IGDBNotionPage[igdb_proto.Cover]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Alpha Channel": {"type": "checkbox", "checkbox": {}},
            "Animated": {"type": "checkbox", "checkbox": {}},
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Height": {"type": "number", "number": {"format": "number"}},
            "Image ID": {"type": "rich_text", "rich_text": {}},
            "URL": {"type": "url", "url": {}},
            "Width": {"type": "number", "number": {"format": "number"}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Cover) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Alpha Channel": {"checkbox": data.alpha_channel},
            "Animated": {"checkbox": data.animated},
            "Height": {"number": data.height},
            "Image ID": {"rich_text": [{"text": {"content": data.image_id}}]},
            "URL": {"url": data.url or None},
            "Width": {"number": data.width},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": str(data.id)}}]},
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.Cover,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class Event(IGDBNotionPage[igdb_proto.Event]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            EventLogo._notional__database,
            Game._notional__database,
            GameVideo._notional__database,
            EventNetwork._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        event_logo_db_id: str | UUID,
        game_db_id: str | UUID,
        game_video_db_id: str | UUID,
        event_network_db_id: str | UUID,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Description": {"type": "rich_text", "rich_text": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Event Logo": {
                "type": "relation",
                "relation": {
                    "database_id": str(event_logo_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Start Time": {"type": "date", "date": {}},
            "Time Zone": {"type": "rich_text", "rich_text": {}},
            "End Time": {"type": "date", "date": {}},
            "Live Stream URL": {"type": "url", "url": {}},
            "Games": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Videos": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_video_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Event Networks": {
                "type": "relation",
                "relation": {
                    "database_id": str(event_network_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Event) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Description": {"rich_text": [{"text": {"content": data.description}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Event Logo": {
                "relation": [
                    {"id": str(EventLogo.retrieve_or_create_from_data(data.event_logo).id)}
                ]
            },
            "Start Time": {"type": "date", "date": {"start": data.start_time.isoformat()}},
            "Time Zone": {"rich_text": [{"text": {"content": data.time_zone}}]},
            "End Time": {"type": "date", "date": {"start": data.end_time.isoformat()}},
            "Live Stream URL": {"url": data.live_stream_url},
            "Games": {
                "relation": [
                    {"id": str(Game.retrieve_or_create_from_data(game).id)} for game in data.games
                ]
            },
            "Videos": {
                "relation": [
                    {"id": str(GameVideo.retrieve_or_create_from_data(vid).id)}
                    for vid in data.videos
                ]
            },
            "Event Networks": {
                "relation": [
                    {"id": str(EventNetwork.retrieve_or_create_from_data(n).id)}
                    for n in data.event_networks
                ]
            },
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"event_logo.{f}" for f in EventLogo.get_query_fields()),
                (f"games.{f}" for f in Game.get_query_fields()),
                (f"videos.{f}" for f in GameVideo.get_query_fields()),
                (f"event_networks.{f}" for f in EventNetwork.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.Event,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.event_logo.url:
            icon_url = add_https_scheme(data.event_logo.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_original/")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class EventLogo(IGDBNotionPage[igdb_proto.EventLogo]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            # "Event": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(event_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Alpha Channel": {"type": "checkbox", "checkbox": {}},
            "Animated": {"type": "checkbox", "checkbox": {}},
            "Height": {"type": "number", "number": {"format": "number"}},
            "Image ID": {"type": "rich_text", "rich_text": {}},
            "URL": {"type": "url", "url": {}},
            "Width": {"type": "number", "number": {"format": "number"}},
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.EventLogo) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Alpha Channel": {"checkbox": data.alpha_channel},
            "Animated": {"checkbox": data.animated},
            "Height": {"number": data.height},
            "Image ID": {"rich_text": [{"text": {"content": data.image_id}}]},
            "URL": {"url": data.url or None},
            "Width": {"number": data.width},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": str(data.id)}}]},
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.EventLogo,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_original/")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class EventNetwork(IGDBNotionPage[igdb_proto.EventNetwork]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(NetworkType._notional__database)

    @staticmethod
    @functools.cache
    def _get_notion_schema(network_type_db_id: str | UUID) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            # "Event": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(event_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "URL": {"type": "url", "url": {}},
            "Network Type": {
                "type": "relation",
                "relation": {
                    "database_id": str(network_type_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.EventNetwork) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "URL": {"url": data.url or None},
            "Network Type": {
                "relation": [
                    {"id": str(NetworkType.retrieve_or_create_from_data(data.network_type).id)}
                ]
            },
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": f"{data.network_type.name} - {data.id}"}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                # (f"event.{f}" for f in Event.get_query_fields()),
                (f"network_type.{f}" for f in NetworkType.get_query_fields()),
            )
        )


class ExternalGame(IGDBNotionPage[igdb_proto.ExternalGame]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(Platform._notional__database)

    @staticmethod
    @functools.cache
    def _get_notion_schema(platform_db_id: str | UUID) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name.removeprefix("EXTERNALGAME_")}
                        for name in igdb_proto.ExternalGameCategoryEnum.__members__
                        if name != "EXTERNALGAME_CATEGORY_NULL"
                    ]
                },
            },
            "Created At": {"type": "date", "date": {}},
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Name": {"type": "title", "title": {}},
            "UID": {"type": "rich_text", "rich_text": {}},
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Year": {"type": "number", "number": {"format": "number"}},
            "Media": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name.removeprefix("EXTERNALGAME_")}
                        for name in igdb_proto.ExternalGameMediaEnum.__members__
                        if name != "EXTERNALGAME_MEDIA_NULL"
                    ]
                },
            },
            "Platform": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            # "Countries": {"type": "multi_select", "multi_select": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.ExternalGame) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Category": {
                "type": "select",
                "select": (
                    {"name": data.category.name.removeprefix("EXTERNALGAME_")}
                    if data.category.name and data.category.name != "EXTERNALGAME_CATEGORY_NULL"
                    else None
                ),
            },
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "UID": {"rich_text": [{"text": {"content": data.uid}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Year": {"number": data.year},
            "Media": {
                "type": "select",
                "select": (
                    {"name": data.media.name.removeprefix("EXTERNALGAME_")}
                    if data.media.name and data.media.name != "EXTERNALGAME_MEDIA_NULL"
                    else None
                ),
            },
            "Platform": {
                "relation": [{"id": str(Platform.retrieve_or_create_from_data(data.platform).id)}]
            },
            # "Countries": {"multi_select": [{"name":str(country)} for country in data.countries]},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                # (f"game.{f}" for f in Game.get_query_fields()),
                (f"platform.{f}" for f in Platform.get_query_fields()),
            )
        )


class Franchise(IGDBNotionPage[igdb_proto.Franchise]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Created At": {"type": "date", "date": {}},
            # "Games": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Name": {"type": "title", "title": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Franchise) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class Game(IGDBNotionPage[igdb_proto.Game]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            AgeRating._notional__database,
            AlternativeName._notional__database,
            Artwork._notional__database,
            Cover._notional__database,
            ExternalGame._notional__database,
            Franchise._notional__database,
            GameEngine._notional__database,
            GameMode._notional__database,
            Genre._notional__database,
            InvolvedCompany._notional__database,
            Keyword._notional__database,
            MultiplayerMode._notional__database,
            Platform._notional__database,
            PlayerPerspective._notional__database,
            ReleaseDate._notional__database,
            Screenshot._notional__database,
            Theme._notional__database,
            GameVideo._notional__database,
            Website._notional__database,
            LanguageSupport._notional__database,
            GameLocalization._notional__database,
        )

    @staticmethod
    @functools.cache
    # pylint: disable-next=too-many-arguments,too-many-positional-arguments,too-many-locals
    def _get_notion_schema(
        age_rating_db_id: str | UUID,
        alternative_name_db_id: str | UUID,
        artwork_db_id: str | UUID,
        cover_db_id: str | UUID,
        external_game_db_id: str | UUID,
        franchise_db_id: str | UUID,
        game_engine_db_id: str | UUID,
        game_mode_db_id: str | UUID,
        genre_db_id: str | UUID,
        involved_company_db_id: str | UUID,
        keyword_db_id: str | UUID,
        multiplayer_mode_db_id: str | UUID,
        platform_db_id: str | UUID,
        player_perspective_db_id: str | UUID,
        release_date_db_id: str | UUID,
        screenshot_db_id: str | UUID,
        theme_db_id: str | UUID,
        game_video_db_id: str | UUID,
        website_db_id: str | UUID,
        language_support_db_id: str | UUID,
        game_localization_db_id: str | UUID,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Age Ratings": {
                "type": "relation",
                "relation": {
                    "database_id": str(age_rating_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Aggregated Rating": {"type": "number", "number": {"format": "number"}},
            "Aggregated Rating Count": {"type": "number", "number": {"format": "number"}},
            "Alternative Names": {
                "type": "relation",
                "relation": {
                    "database_id": str(alternative_name_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Artworks": {
                "type": "relation",
                "relation": {
                    "database_id": str(artwork_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            # "Bundles": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            "Category": {
                "type": "select",
                "select": {
                    "options": [{"name": name} for name in igdb_proto.GameCategoryEnum.__members__]
                },
            },
            # "Collection": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(collection_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Cover": {
                "type": "relation",
                "relation": {
                    "database_id": str(cover_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Created At": {"type": "date", "date": {}},
            # "DLCs": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            # "Expansions": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            "External Games": {
                "type": "relation",
                "relation": {
                    "database_id": str(external_game_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "First Release Date": {"type": "date", "date": {}},
            # "Follows": {"type": "number", "number": {"format": "number"}},
            # "Franchise": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(franchise_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            "Franchises": {
                "type": "relation",
                "relation": {
                    "database_id": str(franchise_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Game Engines": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_engine_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Game Modes": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_mode_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Genres": {
                "type": "relation",
                "relation": {
                    "database_id": str(genre_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Hypes": {"type": "number", "number": {"format": "number"}},
            "Involved Companies": {
                "type": "relation",
                "relation": {
                    "database_id": str(involved_company_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Keywords": {
                "type": "relation",
                "relation": {
                    "database_id": str(keyword_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Multiplayer Modes": {
                "type": "relation",
                "relation": {
                    "database_id": str(multiplayer_mode_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Name": {"type": "title", "title": {}},
            # "Parent Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            "Platforms": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Player Perspectives": {
                "type": "relation",
                "relation": {
                    "database_id": str(player_perspective_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Rating": {"type": "number", "number": {"format": "number"}},
            "Rating Count": {"type": "number", "number": {"format": "number"}},
            "Release Dates": {
                "type": "relation",
                "relation": {
                    "database_id": str(release_date_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Screenshots": {
                "type": "relation",
                "relation": {
                    "database_id": str(screenshot_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            # "Similar Games": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Slug": {"type": "rich_text", "rich_text": {}},
            # "Standalone Expansions": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            "Status": {
                "type": "select",
                "select": {
                    "options": [{"name": name} for name in igdb_proto.GameStatusEnum.__members__]
                },
            },
            "Storyline": {"type": "rich_text", "rich_text": {}},
            "Summary": {"type": "rich_text", "rich_text": {}},
            # "Tags": {"type": "multi_select", "multi_select": {}},
            "Themes": {
                "type": "relation",
                "relation": {
                    "database_id": str(theme_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Total Rating": {"type": "number", "number": {"format": "number"}},
            "Total Rating Count": {"type": "number", "number": {"format": "number"}},
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            # "Version Parent": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            # "Version Title": {"type": "rich_text", "rich_text": {}},
            "Videos": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_video_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Websites": {
                "type": "relation",
                "relation": {
                    "database_id": str(website_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Checksum": {"type": "rich_text", "rich_text": {}},
            # "Remakes": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            # "Remasters": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            # "Expanded Games": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            # "Ports": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            # "Forks": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "dual_property",
            #         "dual_property": {},
            #     },
            # },
            "Language Supports": {
                "type": "relation",
                "relation": {
                    "database_id": str(language_support_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Game Localizations": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_localization_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            # "Collections": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(collection_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Game) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Age Ratings": {
                "relation": [
                    {"id": str(AgeRating.retrieve_or_create_from_data(ar).id)}
                    for ar in data.age_ratings
                ]
            },
            "Aggregated Rating": {"number": data.aggregated_rating},
            "Aggregated Rating Count": {"number": data.aggregated_rating_count},
            "Alternative Names": {
                "relation": [
                    {"id": str(AlternativeName.retrieve_or_create_from_data(name).id)}
                    for name in data.alternative_names
                ]
            },
            "Artworks": {
                "relation": [
                    {"id": str(Artwork.retrieve_or_create_from_data(artwork).id)}
                    for artwork in data.artworks
                ]
            },
            "Category": {
                "type": "select",
                # "select": {"name": igdb_proto.GameCategoryEnum(data.category).name},
                "select": {"name": data.category.name},
            },
            # "Collection": {
            #     "relation": [
            #         {"id": str(Collection.retrieve_or_create_from_data(data.collection).id)}
            #     ]
            # },
            "Cover": {
                "relation": [{"id": str(Cover.retrieve_or_create_from_data(data.cover).id)}]
            },
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "External Games": {
                "relation": [
                    {"id": str(ExternalGame.retrieve_or_create_from_data(game).id)}
                    for game in data.external_games
                ]
            },
            "First Release Date": {
                "type": "date",
                "date": {"start": data.first_release_date.isoformat()},
            },
            # "Follows": {"number": data.follows},
            # "Franchise": {
            #     "relation": [
            #         {"id": str(Franchise.retrieve_or_create_from_data(data.franchise).id)}
            #     ]
            # },
            "Franchises": {
                "relation": [
                    {"id": str(Franchise.retrieve_or_create_from_data(franc).id)}
                    for franc in data.franchises
                ]
            },
            "Game Engines": {
                "relation": [
                    {"id": str(GameEngine.retrieve_or_create_from_data(eng).id)}
                    for eng in data.game_engines
                ]
            },
            "Game Modes": {
                "relation": [
                    {"id": str(GameMode.retrieve_or_create_from_data(mode).id)}
                    for mode in data.game_modes
                ]
            },
            "Genres": {
                "relation": [
                    {"id": str(Genre.retrieve_or_create_from_data(genre).id)}
                    for genre in data.genres
                ]
            },
            "Hypes": {"number": data.hypes},
            "Involved Companies": {
                "relation": [
                    {"id": str(InvolvedCompany.retrieve_or_create_from_data(company).id)}
                    for company in data.involved_companies
                ]
            },
            "Keywords": {
                "relation": [
                    {"id": str(Keyword.retrieve_or_create_from_data(keyword).id)}
                    for keyword in data.keywords[:MAX_RELATION_PAGES]
                ]
            },
            "Multiplayer Modes": {
                "relation": [
                    {"id": str(MultiplayerMode.retrieve_or_create_from_data(mode).id)}
                    for mode in data.multiplayer_modes
                ]
            },
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Platforms": {
                "relation": [
                    {"id": str(Platform.retrieve_or_create_from_data(platf).id)}
                    for platf in data.platforms
                ]
            },
            "Player Perspectives": {
                "relation": [
                    {"id": str(PlayerPerspective.retrieve_or_create_from_data(perspective).id)}
                    for perspective in data.player_perspectives
                ]
            },
            "Rating": {"number": data.rating},
            "Rating Count": {"number": data.rating_count},
            "Release Dates": {
                "relation": [
                    {"id": str(ReleaseDate.retrieve_or_create_from_data(reldate).id)}
                    for reldate in data.release_dates
                ]
            },
            "Screenshots": {
                "relation": [
                    {"id": str(Screenshot.retrieve_or_create_from_data(shot).id)}
                    for shot in data.screenshots
                ]
            },
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Status": {
                "type": "select",
                # "select": {"name": igdb_proto.GameStatusEnum(data.status).name},
                "select": {"name": data.status.name},
            },
            "Storyline": {"rich_text": [{"text": {"content": data.storyline[:MAX_TEXT_LENGTH]}}]},
            "Summary": {"rich_text": [{"text": {"content": data.summary}}]},
            # "Tags": {"multi_select": [{"name": str(tag)} for tag in data.tags]},
            "Themes": {
                "relation": [
                    {"id": str(Theme.retrieve_or_create_from_data(theme).id)}
                    for theme in data.themes
                ]
            },
            "Total Rating": {"number": data.total_rating},
            "Total Rating Count": {"number": data.total_rating_count},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            # "Version Title": {"rich_text": [{"text": {"content": data.version_title}}]},
            "Videos": {
                "relation": [
                    {"id": str(GameVideo.retrieve_or_create_from_data(vid).id)}
                    for vid in data.videos
                ]
            },
            "Websites": {
                "relation": [
                    {"id": str(Website.retrieve_or_create_from_data(site).id)}
                    for site in data.websites
                ]
            },
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Language Supports": {
                "relation": [
                    {"id": str(LanguageSupport.retrieve_or_create_from_data(lang_support).id)}
                    for lang_support in data.language_supports
                ]
            },
            "Game Localizations": {
                "relation": [
                    {"id": str(GameLocalization.retrieve_or_create_from_data(localization).id)}
                    for localization in data.game_localizations
                ]
            },
            # "Collections": {
            #     "relation": [
            #         {"id": str(Collection.retrieve_or_create_from_data(data.collections).id)}
            #     ]
            # },
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"age_ratings.{f}" for f in AgeRating.get_query_fields()),
                (f"alternative_names.{f}" for f in AlternativeName.get_query_fields()),
                (f"artworks.{f}" for f in Artwork.get_query_fields()),
                # (f"bundles.{f}" for f in Game.get_query_fields()),
                # (f"collection.{f}" for f in Collection.get_query_fields()),
                (f"cover.{f}" for f in Cover.get_query_fields()),
                # (f"dlcs.{f}" for f in Game.get_query_fields()),
                # (f"expansions.{f}" for f in Game.get_query_fields()),
                (f"external_games.{f}" for f in ExternalGame.get_query_fields()),
                (f"franchise.{f}" for f in Franchise.get_query_fields()),
                (f"franchises.{f}" for f in Franchise.get_query_fields()),
                (f"game_engines.{f}" for f in GameEngine.get_query_fields()),
                (f"game_modes.{f}" for f in GameMode.get_query_fields()),
                (f"genres.{f}" for f in Genre.get_query_fields()),
                (f"involved_companies.{f}" for f in InvolvedCompany.get_query_fields()),
                (f"keywords.{f}" for f in Keyword.get_query_fields()),
                (f"multiplayer_modes.{f}" for f in MultiplayerMode.get_query_fields()),
                # (f"parent_game.{f}" for f in Game.get_query_fields()),
                (f"platforms.{f}" for f in Platform.get_query_fields()),
                (f"player_perspectives.{f}" for f in PlayerPerspective.get_query_fields()),
                (f"release_dates.{f}" for f in ReleaseDate.get_query_fields()),
                (f"screenshots.{f}" for f in Screenshot.get_query_fields()),
                # (f"similar_games.{f}" for f in Game.get_query_fields()),
                # (f"standalone_expansions.{f}" for f in Game.get_query_fields()),
                (f"themes.{f}" for f in Theme.get_query_fields()),
                # (f"version_parent.{f}" for f in Game.get_query_fields()),
                (f"videos.{f}" for f in GameVideo.get_query_fields()),
                (f"websites.{f}" for f in Website.get_query_fields()),
                # (f"remakes.{f}" for f in Game.get_query_fields()),
                # (f"remasters.{f}" for f in Game.get_query_fields()),
                # (f"expanded_games.{f}" for f in Game.get_query_fields()),
                # (f"ports.{f}" for f in Game.get_query_fields()),
                # (f"forks.{f}" for f in Game.get_query_fields()),
                (f"language_supports.{f}" for f in LanguageSupport.get_query_fields()),
                (f"game_localizations.{f}" for f in GameLocalization.get_query_fields()),
                # (f"collections.{f}" for f in Collection.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.Game,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.cover.url:
            icon_url = add_https_scheme(data.cover.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class GameEngine(IGDBNotionPage[igdb_proto.GameEngine]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            Company._notional__database,
            GameEngineLogo._notional__database,
            Platform._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        company_db_id: str | UUID, game_engine_logo_db_id: str | UUID, platform_db_id: str | UUID
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Companies": {
                "type": "relation",
                "relation": {
                    "database_id": str(company_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Created At": {"type": "date", "date": {}},
            "Description": {"type": "rich_text", "rich_text": {}},
            "Logo": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_engine_logo_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Name": {"type": "title", "title": {}},
            "Platforms": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.GameEngine) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Companies": {
                "relation": [
                    {"id": str(Company.retrieve_or_create_from_data(comp).id)}
                    for comp in data.companies
                ]
            },
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Description": {"rich_text": [{"text": {"content": data.description}}]},
            "Logo": {
                "relation": [
                    {"id": str(GameEngineLogo.retrieve_or_create_from_data(data.logo).id)}
                ]
            },
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Platforms": {
                "relation": [
                    {"id": str(Platform.retrieve_or_create_from_data(platf).id)}
                    for platf in data.platforms
                ]
            },
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"companies.{f}" for f in Company.get_query_fields()),
                (f"logo.{f}" for f in GameEngineLogo.get_query_fields()),
                (f"platforms.{f}" for f in Platform.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.GameEngine,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.logo.url:
            icon_url = add_https_scheme(data.logo.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class GameEngineLogo(IGDBNotionPage[igdb_proto.GameEngineLogo]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Alpha Channel": {"type": "checkbox", "checkbox": {}},
            "Animated": {"type": "checkbox", "checkbox": {}},
            "Height": {"type": "number", "number": {"format": "number"}},
            "Image ID": {"type": "rich_text", "rich_text": {}},
            "URL": {"type": "url", "url": {}},
            "Width": {"type": "number", "number": {"format": "number"}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.GameEngineLogo) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Alpha Channel": {"checkbox": data.alpha_channel},
            "Animated": {"checkbox": data.animated},
            "Height": {"number": data.height},
            "Image ID": {"rich_text": [{"text": {"content": data.image_id}}]},
            "URL": {"url": data.url or None},
            "Width": {"number": data.width},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": str(data.id)}}]},
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.GameEngineLogo,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class GameLocalization(IGDBNotionPage[igdb_proto.GameLocalization]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            Cover._notional__database,
            Region._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        cover_db_id: str | UUID, region_db_id: str | UUID
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Cover": {
                "type": "relation",
                "relation": {
                    "database_id": str(cover_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Region": {
                "type": "relation",
                "relation": {
                    "database_id": str(region_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.GameLocalization) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Cover": {
                "relation": [{"id": str(Cover.retrieve_or_create_from_data(data.cover).id)}]
            },
            "Region": {
                "relation": [{"id": str(Region.retrieve_or_create_from_data(data.region).id)}]
            },
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                # (f"game.{f}" for f in Game.get_query_fields()),
                (f"cover.{f}" for f in Cover.get_query_fields()),
                (f"region.{f}" for f in Region.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.GameLocalization,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.cover.url:
            icon_url = add_https_scheme(data.cover.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class GameMode(IGDBNotionPage[igdb_proto.GameMode]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Created At": {"type": "date", "date": {}},
            "Name": {"type": "title", "title": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.GameMode) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class GameVersion(IGDBNotionPage[igdb_proto.GameVersion]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            GameVersionFeature._notional__database,
            Game._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        game_version_feature_db_id: str | UUID, game_db_id: str | UUID
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Created At": {"type": "date", "date": {}},
            "Features": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_version_feature_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Game": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Games": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.GameVersion) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Features": {
                "relation": [
                    {"id": str(GameVersionFeature.retrieve_or_create_from_data(feat).id)}
                    for feat in data.features
                ]
            },
            "Game": {"relation": [{"id": str(Game.retrieve_or_create_from_data(data.game).id)}]},
            "Games": {
                "relation": [
                    {"id": str(Game.retrieve_or_create_from_data(game).id)} for game in data.games
                ]
            },
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": str(data.id)}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"features.{f}" for f in GameVersionFeature.get_query_fields()),
                (f"game.{f}" for f in Game.get_query_fields()),
                (f"games.{f}" for f in Game.get_query_fields()),
            )
        )


class GameVersionFeature(IGDBNotionPage[igdb_proto.GameVersionFeature]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            GameVersionFeatureValue._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        game_version_feature_value_db_id: str | UUID,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.GameVersionFeatureCategoryEnum.__members__
                    ]
                },
            },
            "Description": {"type": "rich_text", "rich_text": {}},
            "Position": {"type": "number", "number": {"format": "number"}},
            "Title": {"type": "title", "title": {}},
            "Values": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_version_feature_value_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @classmethod
    def get_notion_properties(
        cls, data: igdb_proto.GameVersionFeature
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Category": {"type": "select", "select": {"name": data.category.name}},
            "Description": {"rich_text": [{"text": {"content": data.description}}]},
            "Position": {"number": data.position},
            "Title": {"title": [{"text": {"content": data.title}}]},
            "Values": {
                "relation": [
                    {"id": str(GameVersionFeatureValue.retrieve_or_create_from_data(value).id)}
                    for value in data.values
                ]
            },
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"values.{f}" for f in GameVersionFeatureValue.get_query_fields()),
            )
        )


class GameVersionFeatureValue(IGDBNotionPage[igdb_proto.GameVersionFeatureValue]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(Game._notional__database)

    @staticmethod
    @functools.cache
    def _get_notion_schema(game_db_id: str | UUID) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Game": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            # "Game Feature": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_version_feature_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Included Feature": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": nm}
                        for nm in igdb_proto.GameVersionFeatureValueIncludedFeatureEnum.__members__
                    ]
                },
            },
            "Note": {"type": "rich_text", "rich_text": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(
        data: igdb_proto.GameVersionFeatureValue,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Game": {"relation": [{"id": str(Game.retrieve_or_create_from_data(data.game).id)}]},
            "Included Feature": {
                "type": "select",
                "select": {"name": data.included_feature.name},
            },
            "Note": {"rich_text": [{"text": {"content": data.note}}]},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {
                "title": [
                    {"text": {"content": f"{data.game.name} - {data.included_feature.name}"}}
                ]
            },
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"game.{f}" for f in Game.get_query_fields()),
            )
        )


class GameVideo(IGDBNotionPage[igdb_proto.GameVideo]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Name": {"type": "title", "title": {}},
            "Video ID": {"type": "rich_text", "rich_text": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.GameVideo) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Video ID": {"rich_text": [{"text": {"content": data.video_id}}]},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class Genre(IGDBNotionPage[igdb_proto.Genre]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Created At": {"type": "date", "date": {}},
            "Name": {"type": "title", "title": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Genre) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class InvolvedCompany(IGDBNotionPage[igdb_proto.InvolvedCompany]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(Company._notional__database)

    @staticmethod
    @functools.cache
    def _get_notion_schema(company_db_id: str | UUID) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Company": {
                "type": "relation",
                "relation": {
                    "database_id": str(company_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Created At": {"type": "date", "date": {}},
            "Developer": {"type": "checkbox", "checkbox": {}},
            "Porting": {"type": "checkbox", "checkbox": {}},
            "Publisher": {"type": "checkbox", "checkbox": {}},
            "Supporting": {"type": "checkbox", "checkbox": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.InvolvedCompany) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Company": {
                "relation": [{"id": str(Company.retrieve_or_create_from_data(data.company).id)}]
            },
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Developer": {"checkbox": data.developer},
            "Porting": {"checkbox": data.porting},
            "Publisher": {"checkbox": data.publisher},
            "Supporting": {"checkbox": data.supporting},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": data.company.name}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"company.{f}" for f in Company.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.InvolvedCompany,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.company.logo.url:
            icon_url = add_https_scheme(data.company.logo.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class Keyword(IGDBNotionPage[igdb_proto.Keyword]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Created At": {"type": "date", "date": {}},
            "Name": {"type": "title", "title": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Keyword) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class Language(IGDBNotionPage[igdb_proto.Language]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Native Name": {"type": "rich_text", "rich_text": {}},
            "Locale": {"type": "rich_text", "rich_text": {}},
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Language) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Native Name": {"rich_text": [{"text": {"content": data.native_name}}]},
            "Locale": {"rich_text": [{"text": {"content": data.locale}}]},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class LanguageSupport(IGDBNotionPage[igdb_proto.LanguageSupport]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            Language._notional__database,
            LanguageSupportType._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        language_db_id: str | UUID, language_support_type_db_id: str | UUID
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Language": {
                "type": "relation",
                "relation": {
                    "database_id": str(language_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Language Support Type": {
                "type": "relation",
                "relation": {
                    "database_id": str(language_support_type_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.LanguageSupport) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Language": {
                "relation": [{"id": str(Language.retrieve_or_create_from_data(data.language).id)}]
            },
            "Language Support Type": {
                "relation": [
                    {
                        "id": str(
                            LanguageSupportType.retrieve_or_create_from_data(
                                data.language_support_type
                            ).id
                        )
                    }
                ]
            },
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": f"{data.language.name} - {data.language_support_type.name}"
                        }
                    }
                ]
            },
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                # (f"game.{f}" for f in Game.get_query_fields()),
                (f"language.{f}" for f in Language.get_query_fields()),
                (f"language_support_type.{f}" for f in LanguageSupportType.get_query_fields()),
            )
        )


class LanguageSupportType(IGDBNotionPage[igdb_proto.LanguageSupportType]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @classmethod
    def get_notion_properties(
        cls, data: igdb_proto.LanguageSupportType
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class MultiplayerMode(IGDBNotionPage[igdb_proto.MultiplayerMode]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(Platform._notional__database)

    @staticmethod
    @functools.cache
    def _get_notion_schema(platform_db_id: str | UUID) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Campaign Coop": {"type": "checkbox", "checkbox": {}},
            "Drop In": {"type": "checkbox", "checkbox": {}},
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "LAN Coop": {"type": "checkbox", "checkbox": {}},
            "Offline Coop": {"type": "checkbox", "checkbox": {}},
            "Offline Coop Max": {"type": "number", "number": {"format": "number"}},
            "Offline Max": {"type": "number", "number": {"format": "number"}},
            "Online Coop": {"type": "checkbox", "checkbox": {}},
            "Online Coop Max": {"type": "number", "number": {"format": "number"}},
            "Online Max": {"type": "number", "number": {"format": "number"}},
            "Platform": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Split Screen": {"type": "checkbox", "checkbox": {}},
            "Split Screen Online": {"type": "checkbox", "checkbox": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.MultiplayerMode) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Campaign Coop": {"checkbox": data.campaigncoop},
            "Drop In": {"checkbox": data.dropin},
            "LAN Coop": {"checkbox": data.lancoop},
            "Offline Coop": {"checkbox": data.offlinecoop},
            "Offline Coop Max": {"number": data.offlinecoopmax},
            "Offline Max": {"number": data.offlinemax},
            "Online Coop": {"checkbox": data.onlinecoop},
            "Online Coop Max": {"number": data.onlinecoopmax},
            "Online Max": {"number": data.onlinemax},
            "Platform": {
                "relation": [{"id": str(Platform.retrieve_or_create_from_data(data.platform).id)}]
            },
            "Split Screen": {"checkbox": data.splitscreen},
            "Split Screen Online": {"checkbox": data.splitscreenonline},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": f"{data.platform.name} - {data.id}"}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                # (f"game.{f}" for f in Game.get_query_fields()),
                (f"platform.{f}" for f in Platform.get_query_fields()),
            )
        )


class NetworkType(IGDBNotionPage[igdb_proto.NetworkType]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            # "Event Networks": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(event_network_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.NetworkType) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class Platform(IGDBNotionPage[igdb_proto.Platform]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            PlatformLogo._notional__database,
            PlatformFamily._notional__database,
            PlatformVersion._notional__database,
            PlatformWebsite._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        platform_logo_db_id: str | UUID,
        platform_family_db_id: str | UUID,
        platform_version_db_id: str | UUID,
        platform_website_db_id: str | UUID,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Abbreviation": {"type": "rich_text", "rich_text": {}},
            "Alternative Name": {"type": "rich_text", "rich_text": {}},
            "Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.PlatformCategoryEnum.__members__
                        if name != "PLATFORM_CATEGORY_NULL"
                    ]
                },
            },
            "Created At": {"type": "date", "date": {}},
            "Generation": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Platform Logo": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_logo_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Platform Family": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_family_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Summary": {"type": "rich_text", "rich_text": {}},
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Versions": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_version_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Websites": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_website_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Platform) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Abbreviation": {"rich_text": [{"text": {"content": data.abbreviation}}]},
            "Alternative Name": {"rich_text": [{"text": {"content": data.alternative_name}}]},
            "Category": {
                "type": "select",
                "select": (
                    {"name": data.category.name}
                    if data.category.name != "PLATFORM_CATEGORY_NULL"
                    else None
                ),
            },
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Generation": {"number": data.generation},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Platform Logo": {
                "relation": [
                    {"id": str(PlatformLogo.retrieve_or_create_from_data(data.platform_logo).id)}
                ]
            },
            "Platform Family": {
                "relation": [
                    {
                        "id": str(
                            PlatformFamily.retrieve_or_create_from_data(data.platform_family).id
                        )
                    }
                ]
            },
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Summary": {"rich_text": [{"text": {"content": data.summary}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Versions": {
                "relation": [
                    {"id": str(PlatformVersion.retrieve_or_create_from_data(ver).id)}
                    for ver in data.versions
                ]
            },
            "Websites": {
                "relation": [
                    {"id": str(PlatformWebsite.retrieve_or_create_from_data(ws).id)}
                    for ws in data.websites
                ]
            },
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"platform_logo.{f}" for f in PlatformLogo.get_query_fields()),
                (f"platform_family.{f}" for f in PlatformFamily.get_query_fields()),
                (f"versions.{f}" for f in PlatformVersion.get_query_fields()),
                (f"websites.{f}" for f in PlatformWebsite.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.Platform,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.platform_logo.url:
            icon_url = add_https_scheme(data.platform_logo.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class PlatformFamily(IGDBNotionPage[igdb_proto.PlatformFamily]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.PlatformFamily) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class PlatformLogo(IGDBNotionPage[igdb_proto.PlatformLogo]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Alpha Channel": {"type": "checkbox", "checkbox": {}},
            "Animated": {"type": "checkbox", "checkbox": {}},
            "Height": {"type": "number", "number": {"format": "number"}},
            "Image ID": {"type": "rich_text", "rich_text": {}},
            "URL": {"type": "url", "url": {}},
            "Width": {"type": "number", "number": {"format": "number"}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.PlatformLogo) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Alpha Channel": {"checkbox": data.alpha_channel},
            "Animated": {"checkbox": data.animated},
            "Height": {"number": data.height},
            "Image ID": {"rich_text": [{"text": {"content": data.image_id}}]},
            "URL": {"url": data.url or None},
            "Width": {"number": data.width},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": str(data.id)}}]},
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.PlatformLogo,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class PlatformVersion(IGDBNotionPage[igdb_proto.PlatformVersion]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            PlatformVersionCompany._notional__database,
            PlatformLogo._notional__database,
            PlatformVersionReleaseDate._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        platform_version_company_db_id: str | UUID,
        platform_logo_db_id: str | UUID,
        platform_version_release_date_db_id: str | UUID,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Companies": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_version_company_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Connectivity": {"type": "rich_text", "rich_text": {}},
            "CPU": {"type": "rich_text", "rich_text": {}},
            "Graphics": {"type": "rich_text", "rich_text": {}},
            "Main Manufacturer": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_version_company_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Media": {"type": "rich_text", "rich_text": {}},
            "Memory": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},
            "Online": {"type": "rich_text", "rich_text": {}},
            "OS": {"type": "rich_text", "rich_text": {}},
            "Output": {"type": "rich_text", "rich_text": {}},
            "Platform Logo": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_logo_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Release Dates": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_version_release_date_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Resolutions": {"type": "rich_text", "rich_text": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Sound": {"type": "rich_text", "rich_text": {}},
            "Storage": {"type": "rich_text", "rich_text": {}},
            "Summary": {"type": "rich_text", "rich_text": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.PlatformVersion) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Companies": {
                "relation": [
                    {"id": str(PlatformVersionCompany.retrieve_or_create_from_data(company).id)}
                    for company in data.companies
                ]
            },
            "Connectivity": {"rich_text": [{"text": {"content": data.connectivity}}]},
            "CPU": {"rich_text": [{"text": {"content": data.cpu}}]},
            "Graphics": {"rich_text": [{"text": {"content": data.graphics}}]},
            "Main Manufacturer": {
                "relation": [
                    {
                        "id": str(
                            PlatformVersionCompany.retrieve_or_create_from_data(
                                data.main_manufacturer
                            ).id
                        )
                    }
                ]
            },
            "Media": {"rich_text": [{"text": {"content": data.media}}]},
            "Memory": {"rich_text": [{"text": {"content": data.memory}}]},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Online": {"rich_text": [{"text": {"content": data.online}}]},
            "OS": {"rich_text": [{"text": {"content": data.os}}]},
            "Output": {"rich_text": [{"text": {"content": data.output}}]},
            "Platform Logo": {
                "relation": [
                    {"id": str(PlatformLogo.retrieve_or_create_from_data(data.platform_logo).id)}
                ]
            },
            "Release Dates": {
                "relation": [
                    {
                        "id": str(
                            PlatformVersionReleaseDate.retrieve_or_create_from_data(
                                release_date
                            ).id
                        )
                    }
                    for release_date in data.platform_version_release_dates
                ]
            },
            "Resolutions": {"rich_text": [{"text": {"content": data.resolutions}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Sound": {"rich_text": [{"text": {"content": data.sound}}]},
            "Storage": {"rich_text": [{"text": {"content": data.storage}}]},
            "Summary": {"rich_text": [{"text": {"content": data.summary[:MAX_TEXT_LENGTH]}}]},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"companies.{f}" for f in PlatformVersionCompany.get_query_fields()),
                (f"main_manufacturer.{f}" for f in PlatformVersionCompany.get_query_fields()),
                (f"platform_logo.{f}" for f in PlatformLogo.get_query_fields()),
                (
                    f"platform_version_release_dates.{f}"
                    for f in PlatformVersionReleaseDate.get_query_fields()
                ),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.PlatformVersion,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.platform_logo.url:
            icon_url = add_https_scheme(data.platform_logo.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class PlatformVersionCompany(IGDBNotionPage[igdb_proto.PlatformVersionCompany]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(Company._notional__database)

    @staticmethod
    @functools.cache
    def _get_notion_schema(company_db_id: str | UUID) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Comment": {"type": "rich_text", "rich_text": {}},
            "Company": {
                "type": "relation",
                "relation": {
                    "database_id": str(company_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Developer": {"type": "checkbox", "checkbox": {}},
            "Manufacturer": {"type": "checkbox", "checkbox": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(
        data: igdb_proto.PlatformVersionCompany,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Comment": {"rich_text": [{"text": {"content": data.comment}}]},
            "Company": {
                "relation": [{"id": str(Company.retrieve_or_create_from_data(data.company).id)}]
            },
            "Developer": {"checkbox": data.developer},
            "Manufacturer": {"checkbox": data.manufacturer},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": f"{data.company.name} - {data.id}"}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"company.{f}" for f in Company.get_query_fields()),
            )
        )


class PlatformVersionReleaseDate(IGDBNotionPage[igdb_proto.PlatformVersionReleaseDate]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.DateFormatChangeDateCategoryEnum.__members__
                    ]
                },
            },
            "Created At": {"type": "date", "date": {}},
            "Date": {"type": "date", "date": {}},
            "Human": {"type": "rich_text", "rich_text": {}},
            "M": {"type": "number", "number": {"format": "number"}},
            # "Platform Version": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(platform_version_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Region": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.RegionRegionEnum.__members__
                        if name != "REGION_REGION_NULL"
                    ]
                },
            },
            "Updated At": {"type": "date", "date": {}},
            "Y": {"type": "number", "number": {"format": "number"}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(
        data: igdb_proto.PlatformVersionReleaseDate,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Category": {"type": "select", "select": {"name": data.category.name}},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Date": {"type": "date", "date": {"start": data.date.isoformat()}},
            "Human": {"rich_text": [{"text": {"content": data.human}}]},
            "M": {"number": data.m},
            "Region": {
                "type": "select",
                "select": (
                    {"name": data.region.name}
                    if data.region.name != "REGION_REGION_NULL"
                    else None
                ),
            },
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Y": {"number": data.y},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": f"{data.y}/{data.m}"}}]},
        }


class PlatformWebsite(IGDBNotionPage[igdb_proto.PlatformWebsite]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name.removeprefix("WEBSITE_")}
                        for name in igdb_proto.WebsiteCategoryEnum.__members__
                        if name != "WEBSITE_CATEGORY_NULL"
                    ]
                },
            },
            "Trusted": {"type": "checkbox", "checkbox": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.PlatformWebsite) -> dict[str, dict[str, Any]]:
        category = (
            data.category.name.removeprefix("WEBSITE_")
            if data.category.name and data.category.name != "WEBSITE_CATEGORY_NULL"
            else None
        )

        return {
            "ID": {"number": data.id},
            "Category": {
                "type": "select",
                "select": ({"name": category} if category else None),
            },
            "Trusted": {"checkbox": data.trusted},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": category or data.url or str(data.id)}}]},
        }


class PlayerPerspective(IGDBNotionPage[igdb_proto.PlayerPerspective]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Created At": {"type": "date", "date": {}},
            "Name": {"type": "title", "title": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @classmethod
    def get_notion_properties(
        cls, data: igdb_proto.PlayerPerspective
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class PopularityPrimitive(IGDBNotionPage[igdb_proto.PopularityPrimitive]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(PopularityType._notional__database)

    @staticmethod
    @functools.cache
    def _get_notion_schema(popularity_type_db_id: str | UUID) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Game ID": {"type": "number", "number": {"format": "number"}},
            "Popularity Type": {
                "type": "relation",
                "relation": {
                    "database_id": str(popularity_type_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Popularity Source": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.PopularitySourcePopularitySourceEnum.__members__
                        if name != "POPULARITYSOURCE_POPULARITY_SOURCE_NULL"
                    ]
                },
            },
            "Value": {"type": "number", "number": {"format": "number"}},
            "Calculated At": {"type": "date", "date": {}},
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @classmethod
    def get_notion_properties(
        cls, data: igdb_proto.PopularityPrimitive
    ) -> dict[str, dict[str, Any]]:
        pop_src = (
            data.popularity_source.name
            if data.popularity_source.name != "POPULARITYSOURCE_POPULARITY_SOURCE_NULL"
            else None
        )

        return {
            "ID": {"number": data.id},
            "Game ID": {"number": data.game_id},
            "Popularity Type": {
                "relation": [
                    {
                        "id": str(
                            PopularityType.retrieve_or_create_from_data(data.popularity_type).id
                        )
                    }
                ]
            },
            "Popularity Source": {
                "type": "select",
                "select": ({"name": pop_src} if pop_src else None),
            },
            "Value": {"number": data.value},
            "Calculated At": {"type": "date", "date": {"start": data.calculated_at.isoformat()}},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": " - ".join(
                                part for part in (data.popularity_type.name, pop_src) if part
                            )
                        }
                    }
                ]
            },
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"popularity_type.{f}" for f in PopularityType.get_query_fields()),
            )
        )


class PopularityType(IGDBNotionPage[igdb_proto.PopularityType]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Popularity Source": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.PopularitySourcePopularitySourceEnum.__members__
                        if name != "POPULARITYSOURCE_POPULARITY_SOURCE_NULL"
                    ]
                },
            },
            "Name": {"type": "title", "title": {}},
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @classmethod
    def get_notion_properties(cls, data: igdb_proto.PopularityType) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Popularity Source": {
                "type": "select",
                "select": (
                    {"name": data.popularity_source.name}
                    if data.popularity_source.name != "POPULARITYSOURCE_POPULARITY_SOURCE_NULL"
                    else None
                ),
            },
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class Region(IGDBNotionPage[igdb_proto.Region]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Category": {"type": "rich_text", "rich_text": {}},
            "Identifier": {"type": "rich_text", "rich_text": {}},
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Region) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Category": {"rich_text": [{"text": {"content": data.category}}]},
            "Identifier": {"rich_text": [{"text": {"content": data.identifier}}]},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class ReleaseDate(IGDBNotionPage[igdb_proto.ReleaseDate]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            Platform._notional__database,
            ReleaseDateStatus._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        platform_db_id: str | UUID, release_date_status_db_id: str | UUID
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.DateFormatChangeDateCategoryEnum.__members__
                    ]
                },
            },
            "Created At": {"type": "date", "date": {}},
            "Date": {"type": "date", "date": {}},
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Human": {"type": "rich_text", "rich_text": {}},
            "M": {"type": "number", "number": {"format": "number"}},
            "Platform": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Region": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.RegionRegionEnum.__members__
                        if name != "REGION_REGION_NULL"
                    ]
                },
            },
            "Updated At": {"type": "date", "date": {}},
            "Y": {"type": "number", "number": {"format": "number"}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Status": {
                "type": "relation",
                "relation": {
                    "database_id": str(release_date_status_db_id),
                    "type": "dual_property",
                    "dual_property": {},
                },
            },
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.ReleaseDate) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Category": {"type": "select", "select": {"name": data.category.name}},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Date": {"type": "date", "date": {"start": data.date.isoformat()}},
            "Human": {"rich_text": [{"text": {"content": data.human}}]},
            "M": {"number": data.m},
            "Platform": {
                "relation": [{"id": str(Platform.retrieve_or_create_from_data(data.platform).id)}]
            },
            "Region": {
                "type": "select",
                "select": (
                    {"name": data.region.name}
                    if data.region.name != "REGION_REGION_NULL"
                    else None
                ),
            },
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Y": {"number": data.y},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Status": {
                "relation": [
                    {"id": str(ReleaseDateStatus.retrieve_or_create_from_data(data.status).id)}
                ]
            },
            "Name": {
                "title": [{"text": {"content": f"{data.platform.name} - {data.y}/{data.m}"}}]
            },
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                # (f"game.{f}" for f in Game.get_query_fields()),
                (f"platform.{f}" for f in Platform.get_query_fields()),
                (f"status.{f}" for f in ReleaseDateStatus.get_query_fields()),
            )
        )


class ReleaseDateStatus(IGDBNotionPage[igdb_proto.ReleaseDateStatus]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "Description": {"type": "rich_text", "rich_text": {}},
            "Created At": {"type": "date", "date": {}},
            "Updated At": {"type": "date", "date": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @classmethod
    def get_notion_properties(
        cls, data: igdb_proto.ReleaseDateStatus
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Description": {"rich_text": [{"text": {"content": data.description}}]},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class Screenshot(IGDBNotionPage[igdb_proto.Screenshot]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Alpha Channel": {"type": "checkbox", "checkbox": {}},
            "Animated": {"type": "checkbox", "checkbox": {}},
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Height": {"type": "number", "number": {"format": "number"}},
            "Image ID": {"type": "rich_text", "rich_text": {}},
            "URL": {"type": "url", "url": {}},
            "Width": {"type": "number", "number": {"format": "number"}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Screenshot) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Alpha Channel": {"checkbox": data.alpha_channel},
            "Animated": {"checkbox": data.animated},
            "Height": {"number": data.height},
            "Image ID": {"rich_text": [{"text": {"content": data.image_id}}]},
            "URL": {"url": data.url or None},
            "Width": {"number": data.width},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": str(data.id)}}]},
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: igdb_proto.Screenshot,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> Self:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_1080p")

        return super().retrieve_or_create_from_data(data, icon_url, cover_url)


class Search(IGDBNotionPage[igdb_proto.Search]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(
            Character._notional__database,
            Collection._notional__database,
            Company._notional__database,
            Game._notional__database,
            Platform._notional__database,
            TestDummy._notional__database,
            Theme._notional__database,
        )

    @staticmethod
    @functools.cache
    def _get_notion_schema(
        character_db_id: str | UUID,
        collection_db_id: str | UUID,
        company_db_id: str | UUID,
        game_db_id: str | UUID,
        platform_db_id: str | UUID,
        test_dummy_db_id: str | UUID,
        theme_db_id: str | UUID,
    ) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Alternative Name": {"type": "rich_text", "rich_text": {}},
            "Character": {
                "type": "relation",
                "relation": {
                    "database_id": str(character_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Collection": {
                "type": "relation",
                "relation": {
                    "database_id": str(collection_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Company": {
                "type": "relation",
                "relation": {
                    "database_id": str(company_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Description": {"type": "rich_text", "rich_text": {}},
            "Game": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Name": {"type": "title", "title": {}},
            "Platform": {
                "type": "relation",
                "relation": {
                    "database_id": str(platform_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Published At": {"type": "date", "date": {}},
            "Test Dummy": {
                "type": "relation",
                "relation": {
                    "database_id": str(test_dummy_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Theme": {
                "type": "relation",
                "relation": {
                    "database_id": str(theme_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Search) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Alternative Name": {"rich_text": [{"text": {"content": data.alternative_name}}]},
            "Character": {
                "relation": [
                    {"id": str(Character.retrieve_or_create_from_data(data.character).id)}
                ]
            },
            "Collection": {
                "relation": [
                    {"id": str(Collection.retrieve_or_create_from_data(data.collection).id)}
                ]
            },
            "Company": {
                "relation": [{"id": str(Company.retrieve_or_create_from_data(data.company).id)}]
            },
            "Description": {"rich_text": [{"text": {"content": data.description}}]},
            "Game": {"relation": [{"id": str(Game.retrieve_or_create_from_data(data.game).id)}]},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Platform": {
                "relation": [{"id": str(Platform.retrieve_or_create_from_data(data.platform).id)}]
            },
            "Published At": {
                "type": "date",
                "date": {"start": data.published_at.isoformat()},
            },
            "Test Dummy": {
                "relation": [
                    {"id": str(TestDummy.retrieve_or_create_from_data(data.test_dummy).id)}
                ]
            },
            "Theme": {
                "relation": [{"id": str(Theme.retrieve_or_create_from_data(data.theme).id)}]
            },
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"character.{f}" for f in Character.get_query_fields()),
                (f"collection.{f}" for f in Collection.get_query_fields()),
                (f"company.{f}" for f in Company.get_query_fields()),
                (f"game.{f}" for f in Game.get_query_fields()),
                (f"platform.{f}" for f in Platform.get_query_fields()),
                (f"test_dummy.{f}" for f in TestDummy.get_query_fields()),
                (f"theme.{f}" for f in Theme.get_query_fields()),
            )
        )


class TestDummy(IGDBNotionPage[igdb_proto.TestDummy]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema(Game._notional__database)

    @staticmethod
    @functools.cache
    def _get_notion_schema(game_db_id: str | UUID) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Bool Value": {"type": "checkbox", "checkbox": {}},
            "Created At": {"type": "date", "date": {}},
            "Enum Test": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name}
                        for name in igdb_proto.TestDummyEnumTestEnum.__members__
                        if name != "TESTDUMMY_ENUM_TEST_NULL"
                    ]
                },
            },
            "Float Value": {"type": "number", "number": {"format": "number"}},
            "Game": {
                "type": "relation",
                "relation": {
                    "database_id": str(game_db_id),
                    "type": "single_property",
                    "single_property": {},
                },
            },
            "Integer Array": {
                "type": "rich_text",
                "rich_text": {},
            },  # Stored as a string, will need parsing
            "Integer Value": {"type": "number", "number": {"format": "number"}},
            "Name": {"type": "title", "title": {}},
            "New Integer Value": {"type": "number", "number": {"format": "number"}},
            "Private": {"type": "checkbox", "checkbox": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "String Array": {
                "type": "rich_text",
                "rich_text": {},
            },  # Stored as a string, will need parsing
            # "Test Dummies": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(test_dummy_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            # "Test Dummy": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(test_dummy_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.TestDummy) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Bool Value": {"checkbox": data.bool_value},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Enum Test": {
                "type": "select",
                "select": (
                    {"name": data.enum_test.name}
                    if data.enum_test.name != "TESTDUMMY_ENUM_TEST_NULL"
                    else None
                ),
            },
            "Float Value": {"number": data.float_value},
            "Game": {"relation": [{"id": str(Game.retrieve_or_create_from_data(data.game).id)}]},
            "Integer Array": {"rich_text": [{"text": {"content": str(data.integer_array)}}]},
            "Integer Value": {"number": data.integer_value},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "New Integer Value": {"number": data.new_integer_value},
            "Private": {"checkbox": data.private},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "String Array": {"rich_text": [{"text": {"content": str(data.string_array)}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"game.{f}" for f in Game.get_query_fields()),
            )
        )


class Theme(IGDBNotionPage[igdb_proto.Theme]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Created At": {"type": "date", "date": {}},
            "Name": {"type": "title", "title": {}},
            "Slug": {"type": "rich_text", "rich_text": {}},
            "Updated At": {"type": "date", "date": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Theme) -> dict[str, dict[str, Any]]:
        return {
            "ID": {"number": data.id},
            "Created At": {"type": "date", "date": {"start": data.created_at.isoformat()}},
            "Name": {"title": [{"text": {"content": data.name}}]},
            "Slug": {"rich_text": [{"text": {"content": data.slug}}]},
            "Updated At": {"type": "date", "date": {"start": data.updated_at.isoformat()}},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
        }


class Website(IGDBNotionPage[igdb_proto.Website]):
    @override
    @classmethod
    def get_notion_schema(cls) -> dict[str, dict[str, Any]]:
        return cls._get_notion_schema()

    @staticmethod
    @functools.cache
    def _get_notion_schema() -> dict[str, dict[str, Any]]:
        return {
            "ID": {"type": "number", "number": {"format": "number"}},
            "Category": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": name.removeprefix("WEBSITE_")}
                        for name in igdb_proto.WebsiteCategoryEnum.__members__
                        if name != "WEBSITE_CATEGORY_NULL"
                    ]
                },
            },
            # "Game": {
            #     "type": "relation",
            #     "relation": {
            #         "database_id": str(game_db_id),
            #         "type": "single_property",
            #         "single_property": {},
            #     },
            # },
            "Trusted": {"type": "checkbox", "checkbox": {}},
            "URL": {"type": "url", "url": {}},
            "Checksum": {"type": "rich_text", "rich_text": {}},
            "Name": {"type": "title", "title": {}},  # This is a required property
        }

    @override
    @staticmethod
    def get_notion_properties(data: igdb_proto.Website) -> dict[str, dict[str, Any]]:
        category = (
            data.category.name.removeprefix("WEBSITE_")
            if data.category.name and data.category.name != "WEBSITE_CATEGORY_NULL"
            else None
        )

        return {
            "ID": {"number": data.id},
            "Category": {
                "type": "select",
                "select": {"name": category} if category else None,
            },
            "Trusted": {"checkbox": data.trusted},
            "URL": {"url": data.url or None},
            "Checksum": {"rich_text": [{"text": {"content": data.checksum}}]},
            "Name": {"title": [{"text": {"content": category or data.url or str(data.id)}}]},
        }

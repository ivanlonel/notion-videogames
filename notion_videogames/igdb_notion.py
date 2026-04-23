# pylint: disable=too-many-lines
from __future__ import annotations

import functools
import itertools
import urllib.parse
from typing import Final, TypeVar, override

import betterproto2
import ultimate_notion as uno
from ultimate_notion import PropType, props

from notion_videogames import notion
from notion_videogames.proto import proto

T = TypeVar("T", bound=betterproto2.Message)

# https://developers.notion.com/reference/request-limits
MAX_RELATION_PAGES: Final[int] = 100
MAX_TEXT_LENGTH: Final[int] = 2000


def _hash(self: betterproto2.Message) -> int:
    return hash(bytes(self))


# Monkeypatch betterproto2.Message adding a __hash__ method so instances can be used in lru_cache
betterproto2.Message.__hash__ = _hash  # type: ignore[assignment,method-assign]


def add_https_scheme[AnyStr: (bytes, str)](url: AnyStr) -> AnyStr:
    parsed_url = urllib.parse.urlparse(url)

    if parsed_url.scheme:
        # If there's already a scheme, return the original URL
        return url

    # If there's no scheme, add 'https'
    new_components = (
        "https" if isinstance(url, str) else b"https",  # type: ignore[redundant-expr]
        *parsed_url[1:],  # type: ignore[has-type]
    )
    return urllib.parse.urlunparse(new_components)  # type: ignore[no-any-return]


class IGDBNotionPage(notion.NotionPageType[T]):
    @override
    @classmethod
    def retrieve_from_data(cls, data: T) -> uno.Page | None:
        if not hasattr(data, "id"):
            msg = f"{data!r} has no 'id' attribute"
            raise ValueError(msg)
        return next(
            iter(cls.schema.get_db().query.filter(uno.prop("ID") == data.id).execute()), None
        )

    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return ("*",)


class AgeRatingOrganizationSchema(uno.Schema, db_title="Age Rating Organizations"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_age_rating_categories = PropType.Relation(
        "Related to Age Rating Categories (Organization)"
    )
    related_to_age_rating_content_descriptions_v2 = PropType.Relation(
        "Related to Age Rating Content Descriptions V2 (Organization)"
    )
    related_to_age_ratings = PropType.Relation("Related to Age Ratings (Organization)")


class AgeRatingOrganization(IGDBNotionPage[proto.AgeRatingOrganization]):
    schema = AgeRatingOrganizationSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.AgeRatingOrganization,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals


class AgeRatingCategorySchema(uno.Schema, db_title="Age Rating Categories"):
    id = PropType.Number("ID")
    rating = PropType.Title("Rating")
    organization = PropType.Relation(
        "Organization",
        schema=AgeRatingOrganizationSchema,
        two_way_prop=AgeRatingOrganizationSchema.related_to_age_rating_categories,
    )
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_age_ratings = PropType.Relation("Related to Age Ratings (Rating Category)")


class AgeRatingCategory(IGDBNotionPage[proto.AgeRatingCategory]):
    schema = AgeRatingCategorySchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.AgeRatingCategory,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.organization is not None:
            optionals["Organization"] = props.Relations(
                AgeRatingOrganization.retrieve_or_create_from_data(data.organization)
            )
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Rating": props.Title(data.rating),
            "Checksum": props.Text(data.checksum),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"organization.{f}" for f in AgeRatingOrganization.get_query_fields()),
            )
        )


class AgeRatingContentDescriptionTypeSchema(
    uno.Schema, db_title="Age Rating Content Description Types"
):
    id = PropType.Number("ID")
    slug = PropType.Text("Slug")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_age_rating_content_descriptions_v2 = PropType.Relation(
        "Related to Age Rating Content Descriptions V2 (Description Type)"
    )


class AgeRatingContentDescriptionType(IGDBNotionPage[proto.AgeRatingContentDescriptionType]):
    schema = AgeRatingContentDescriptionTypeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.AgeRatingContentDescriptionType,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Slug": props.Text(data.slug),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals


class AgeRatingContentDescriptionV2Schema(
    uno.Schema, db_title="Age Rating Content Descriptions V2"
):
    id = PropType.Number("ID")
    description = PropType.Title("Description")
    organization = PropType.Relation(
        "Organization",
        schema=AgeRatingOrganizationSchema,
        two_way_prop=AgeRatingOrganizationSchema.related_to_age_rating_content_descriptions_v2,
    )
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    description_type = PropType.Relation(
        "Description Type",
        schema=AgeRatingContentDescriptionTypeSchema,
        two_way_prop=AgeRatingContentDescriptionTypeSchema.related_to_age_rating_content_descriptions_v2,
    )
    related_to_age_ratings = PropType.Relation(
        "Related to Age Ratings (Rating Content Descriptions)"
    )


class AgeRatingContentDescriptionV2(IGDBNotionPage[proto.AgeRatingContentDescriptionV2]):
    schema = AgeRatingContentDescriptionV2Schema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.AgeRatingContentDescriptionV2,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.organization is not None:
            optionals["Organization"] = props.Relations(
                AgeRatingOrganization.retrieve_or_create_from_data(data.organization)
            )
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        if data.description_type is not None:
            optionals["Description Type"] = props.Relations(
                AgeRatingContentDescriptionType.retrieve_or_create_from_data(data.description_type)
            )
        return {
            "ID": props.Number(data.id),
            "Description": props.Title(data.description),
            "Checksum": props.Text(data.checksum),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"organization.{f}" for f in AgeRatingOrganization.get_query_fields()),
                (
                    f"description_type.{f}"
                    for f in AgeRatingContentDescriptionType.get_query_fields()
                ),
            )
        )


class AgeRatingSchema(uno.Schema, db_title="Age Ratings"):
    id = PropType.Number("ID")
    rating_cover_url = PropType.URL("Rating Cover URL")
    synopsis = PropType.Text("Synopsis")
    checksum = PropType.Text("Checksum")
    organization = PropType.Relation(
        "Organization",
        schema=AgeRatingOrganizationSchema,
        two_way_prop=AgeRatingOrganizationSchema.related_to_age_ratings,
    )
    rating_category = PropType.Relation(
        "Rating Category",
        schema=AgeRatingCategorySchema,
        two_way_prop=AgeRatingCategorySchema.related_to_age_ratings,
    )
    rating_content_descriptions = PropType.Relation(
        "Rating Content Descriptions",
        schema=AgeRatingContentDescriptionV2Schema,
        two_way_prop=AgeRatingContentDescriptionV2Schema.related_to_age_ratings,
    )
    title = PropType.Title("Title")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Age Ratings)")


class AgeRating(IGDBNotionPage[proto.AgeRating]):
    schema = AgeRatingSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.AgeRating) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.organization is not None:
            optionals["Organization"] = props.Relations(
                AgeRatingOrganization.retrieve_or_create_from_data(data.organization)
            )
        if data.rating_category is not None:
            optionals["Rating Category"] = props.Relations(
                AgeRatingCategory.retrieve_or_create_from_data(data.rating_category)
            )
        return {
            "ID": props.Number(data.id),
            "Rating Cover URL": props.URL(data.rating_cover_url or None),
            "Synopsis": props.Text(data.synopsis[:MAX_TEXT_LENGTH]),
            "Checksum": props.Text(data.checksum),
            "Rating Content Descriptions": props.Relations(
                [
                    AgeRatingContentDescriptionV2.retrieve_or_create_from_data(descr)
                    for descr in data.rating_content_descriptions
                ]
            ),
            "Title": props.Title(
                " - ".join(
                    part
                    for part in (
                        data.organization.name if data.organization else None,
                        data.rating_category.rating if data.rating_category else None,
                    )
                    if part
                )
            ),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"organization.{f}" for f in AgeRatingOrganization.get_query_fields()),
                (f"rating_category.{f}" for f in AgeRatingCategory.get_query_fields()),
                (
                    f"rating_content_descriptions.{f}"
                    for f in AgeRatingContentDescriptionV2.get_query_fields()
                ),
            )
        )


class AlternativeNameSchema(uno.Schema, db_title="Alternative Names"):
    id = PropType.Number("ID")
    comment = PropType.Text("Comment")
    # game = PropType.Relation("Game", schema=GameSchema)
    name = PropType.Title("Name")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Alternative Names)")


class AlternativeName(IGDBNotionPage[proto.AlternativeName]):
    schema = AlternativeNameSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.AlternativeName,
    ) -> dict[str, props.PropertyValue]:
        return {
            "ID": props.Number(data.id),
            "Comment": props.Text(data.comment[:MAX_TEXT_LENGTH]),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        }


class ArtworkTypeSchema(uno.Schema, db_title="Artwork Types"):
    id = PropType.Number("ID")
    slug = PropType.Text("Slug")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_artworks = PropType.Relation("Related to Artworks (Artwork Type)")


class ArtworkType(IGDBNotionPage[proto.ArtworkType]):
    schema = ArtworkTypeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.ArtworkType) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Slug": props.Text(data.slug),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals


class ArtworkSchema(uno.Schema, db_title="Artworks"):
    id = PropType.Number("ID")
    alpha_channel = PropType.Checkbox("Alpha Channel")
    animated = PropType.Checkbox("Animated")
    # game = PropType.Relation("Game", schema=GameSchema)
    height = PropType.Number("Height")
    image_id = PropType.Text("Image ID")
    url = PropType.URL("URL")
    width = PropType.Number("Width")
    checksum = PropType.Text("Checksum")
    artwork_type = PropType.Relation(
        "Artwork Type",
        schema=ArtworkTypeSchema,
        two_way_prop=ArtworkTypeSchema.related_to_artworks,
    )
    title = PropType.Title("Title")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Artworks)")


class Artwork(IGDBNotionPage[proto.Artwork]):
    schema = ArtworkSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Artwork) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.artwork_type is not None:
            optionals["Artwork Type"] = props.Relations(
                ArtworkType.retrieve_or_create_from_data(data.artwork_type)
            )
        return {
            "ID": props.Number(data.id),
            "Alpha Channel": props.Checkbox(data.alpha_channel),
            "Animated": props.Checkbox(data.animated),
            "Height": props.Number(data.height),
            "Image ID": props.Text(data.image_id),
            "URL": props.URL(data.url or None),
            "Width": props.Number(data.width),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(str(data.id)),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"artwork_type.{f}" for f in ArtworkType.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.Artwork,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_1080p")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class CompanyLogoSchema(uno.Schema, db_title="Company Logos"):
    id = PropType.Number("ID")
    alpha_channel = PropType.Checkbox("Alpha Channel")
    animated = PropType.Checkbox("Animated")
    height = PropType.Number("Height")
    image_id = PropType.Text("Image ID")
    url = PropType.URL("URL")
    width = PropType.Number("Width")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_companies = PropType.Relation("Related to Companies (Logo)")


class CompanyLogo(IGDBNotionPage[proto.CompanyLogo]):
    schema = CompanyLogoSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.CompanyLogo) -> dict[str, props.PropertyValue]:
        return {
            "ID": props.Number(data.id),
            "Alpha Channel": props.Checkbox(data.alpha_channel),
            "Animated": props.Checkbox(data.animated),
            "Height": props.Number(data.height),
            "Image ID": props.Text(data.image_id),
            "URL": props.URL(data.url or None),
            "Width": props.Number(data.width),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(str(data.id)),
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.CompanyLogo,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class CompanyStatusSchema(uno.Schema, db_title="Company Statuses"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_companies = PropType.Relation("Related to Companies (Status)")


class CompanyStatus(IGDBNotionPage[proto.CompanyStatus]):
    schema = CompanyStatusSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.CompanyStatus) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals


class WebsiteTypeSchema(uno.Schema, db_title="Website Types"):
    id = PropType.Number("ID")
    type = PropType.Title("Type")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_company_websites = PropType.Relation("Related to Company Websites (Type)")
    related_to_platform_websites = PropType.Relation("Related to Platform Websites (Type)")
    related_to_websites = PropType.Relation("Related to Websites (Type)")


class WebsiteType(IGDBNotionPage[proto.WebsiteType]):
    schema = WebsiteTypeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.WebsiteType) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Type": props.Title(data.type),
            "Checksum": props.Text(data.checksum),
        } | optionals


class CompanyWebsiteSchema(uno.Schema, db_title="Company Websites"):
    id = PropType.Number("ID")
    trusted = PropType.Checkbox("Trusted")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    type = PropType.Relation(
        "Type",
        schema=WebsiteTypeSchema,
        two_way_prop=WebsiteTypeSchema.related_to_company_websites,
    )
    title = PropType.Title("Title")
    related_to_companies = PropType.Relation("Related to Companies (Websites)")


class CompanyWebsite(IGDBNotionPage[proto.CompanyWebsite]):
    schema = CompanyWebsiteSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.CompanyWebsite,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.type is not None:
            optionals["Type"] = props.Relations(
                WebsiteType.retrieve_or_create_from_data(data.type)
            )
        return {
            "ID": props.Number(data.id),
            "Trusted": props.Checkbox(data.trusted),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(
                (data.type.type if data.type else None) or data.url or str(data.id)
            ),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"type.{f}" for f in WebsiteType.get_query_fields()),
            )
        )


class DateFormatSchema(uno.Schema, db_title="Date Formats"):
    id = PropType.Number("ID")
    format = PropType.Title("Format")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_companies_start_date_format = PropType.Relation(
        "Related to Companies (Start Date Format)"
    )
    related_to_companies_change_date_format = PropType.Relation(
        "Related to Companies (Change Date Format)"
    )
    related_to_platform_version_release_dates = PropType.Relation(
        "Related to Platform Version Release Dates (Date Format)"
    )
    related_to_release_dates = PropType.Relation("Related to Release Dates (Date Format)")


class DateFormat(IGDBNotionPage[proto.DateFormat]):
    schema = DateFormatSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.DateFormat) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Format": props.Title(data.format),
            "Checksum": props.Text(data.checksum),
        } | optionals


class CompanySchema(uno.Schema, db_title="Companies"):
    id = PropType.Number("ID")
    change_date = PropType.Date("Change Date")
    # changed_company = PropType.Relation("Changed Company", schema=uno.SelfRef)
    country = PropType.Number("Country")
    created_at = PropType.Date("Created At")
    description = PropType.Text("Description")
    # developed = PropType.Relation("Developed", schema=GameSchema)
    logo = PropType.Relation(
        "Logo",
        schema=CompanyLogoSchema,
        two_way_prop=CompanyLogoSchema.related_to_companies,
    )
    name = PropType.Title("Name")
    # parent = PropType.Relation("Parent", schema=uno.SelfRef)
    slug = PropType.Text("Slug")
    start_date = PropType.Date("Start Date")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    websites = PropType.Relation(
        "Websites",
        schema=CompanyWebsiteSchema,
        two_way_prop=CompanyWebsiteSchema.related_to_companies,
    )
    checksum = PropType.Text("Checksum")
    status = PropType.Relation(
        "Status",
        schema=CompanyStatusSchema,
        two_way_prop=CompanyStatusSchema.related_to_companies,
    )
    start_date_format = PropType.Relation(
        "Start Date Format",
        schema=DateFormatSchema,
        two_way_prop=DateFormatSchema.related_to_companies_start_date_format,
    )
    change_date_format = PropType.Relation(
        "Change Date Format",
        schema=DateFormatSchema,
        two_way_prop=DateFormatSchema.related_to_companies_change_date_format,
    )
    related_to_platform_version_companies = PropType.Relation(
        "Related to Platform Version Companies (Company)"
    )
    related_to_game_engines = PropType.Relation("Related to Game Engines (Companies)")
    related_to_involved_companies = PropType.Relation("Related to Involved Companies (Company)")


class Company(IGDBNotionPage[proto.Company]):
    schema = CompanySchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Company) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.change_date is not None:
            optionals["Change Date"] = props.Date(data.change_date.isoformat())
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.logo is not None:
            optionals["Logo"] = props.Relations(
                CompanyLogo.retrieve_or_create_from_data(data.logo)
            )
        if data.start_date is not None:
            optionals["Start Date"] = props.Date(data.start_date.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        if data.status is not None:
            optionals["Status"] = props.Relations(
                CompanyStatus.retrieve_or_create_from_data(data.status)
            )
        if data.start_date_format is not None:
            optionals["Start Date Format"] = props.Relations(
                DateFormat.retrieve_or_create_from_data(data.start_date_format)
            )
        if data.change_date_format is not None:
            optionals["Change Date Format"] = props.Relations(
                DateFormat.retrieve_or_create_from_data(data.change_date_format)
            )
        return {
            "ID": props.Number(data.id),
            "Country": props.Number(data.country),
            "Description": props.Text(data.description[:MAX_TEXT_LENGTH]),
            "Name": props.Title(data.name),
            "Slug": props.Text(data.slug),
            "URL": props.URL(data.url or None),
            "Websites": props.Relations(
                [CompanyWebsite.retrieve_or_create_from_data(site) for site in data.websites]
            ),
            "Checksum": props.Text(data.checksum),
        } | optionals

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
                (f"status.{f}" for f in CompanyStatus.get_query_fields()),
                (f"start_date_format.{f}" for f in DateFormat.get_query_fields()),
                (f"change_date_format.{f}" for f in DateFormat.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.Company,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.logo and data.logo.url:
            icon_url = add_https_scheme(data.logo.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class CoverSchema(uno.Schema, db_title="Covers"):
    id = PropType.Number("ID")
    alpha_channel = PropType.Checkbox("Alpha Channel")
    animated = PropType.Checkbox("Animated")
    # game = PropType.Relation("Game", schema=GameSchema)
    height = PropType.Number("Height")
    image_id = PropType.Text("Image ID")
    url = PropType.URL("URL")
    width = PropType.Number("Width")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_game_localizations = PropType.Relation("Related to Game Localizations (Cover)")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Cover)")


class Cover(IGDBNotionPage[proto.Cover]):
    schema = CoverSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Cover) -> dict[str, props.PropertyValue]:
        return {
            "ID": props.Number(data.id),
            "Alpha Channel": props.Checkbox(data.alpha_channel),
            "Animated": props.Checkbox(data.animated),
            "Height": props.Number(data.height),
            "Image ID": props.Text(data.image_id),
            "URL": props.URL(data.url or None),
            "Width": props.Number(data.width),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(str(data.id)),
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.Cover,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class ExternalGameSourceSchema(uno.Schema, db_title="External Game Sources"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_external_games = PropType.Relation(
        "Related to External Games (External Game Source)"
    )


class ExternalGameSource(IGDBNotionPage[proto.ExternalGameSource]):
    schema = ExternalGameSourceSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.ExternalGameSource,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals


class GameReleaseFormatSchema(uno.Schema, db_title="Game Release Formats"):
    id = PropType.Number("ID")
    format = PropType.Title("Format")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_external_games = PropType.Relation(
        "Related to External Games (Game Release Format)"
    )


class GameReleaseFormat(IGDBNotionPage[proto.GameReleaseFormat]):
    schema = GameReleaseFormatSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.GameReleaseFormat,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Format": props.Title(data.format),
            "Checksum": props.Text(data.checksum),
        } | optionals


class PlatformFamilySchema(uno.Schema, db_title="Platform Families"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    checksum = PropType.Text("Checksum")
    related_to_platforms = PropType.Relation("Related to Platforms (Platform Family)")


class PlatformFamily(IGDBNotionPage[proto.PlatformFamily]):
    schema = PlatformFamilySchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.PlatformFamily,
    ) -> dict[str, props.PropertyValue]:
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Slug": props.Text(data.slug),
            "Checksum": props.Text(data.checksum),
        }


class PlatformLogoSchema(uno.Schema, db_title="Platform Logos"):
    id = PropType.Number("ID")
    alpha_channel = PropType.Checkbox("Alpha Channel")
    animated = PropType.Checkbox("Animated")
    height = PropType.Number("Height")
    image_id = PropType.Text("Image ID")
    url = PropType.URL("URL")
    width = PropType.Number("Width")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_platform_versions = PropType.Relation(
        "Related to Platform Versions (Platform Logo)"
    )
    related_to_platforms = PropType.Relation("Related to Platforms (Platform Logo)")


class PlatformLogo(IGDBNotionPage[proto.PlatformLogo]):
    schema = PlatformLogoSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.PlatformLogo) -> dict[str, props.PropertyValue]:
        return {
            "ID": props.Number(data.id),
            "Alpha Channel": props.Checkbox(data.alpha_channel),
            "Animated": props.Checkbox(data.animated),
            "Height": props.Number(data.height),
            "Image ID": props.Text(data.image_id),
            "URL": props.URL(data.url or None),
            "Width": props.Number(data.width),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(str(data.id)),
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.PlatformLogo,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class PlatformTypeSchema(uno.Schema, db_title="Platform Types"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_platforms = PropType.Relation("Related to Platforms (Platform Type)")


class PlatformType(IGDBNotionPage[proto.PlatformType]):
    schema = PlatformTypeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.PlatformType) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals


class PlatformVersionCompanySchema(uno.Schema, db_title="Platform Version Companies"):
    id = PropType.Number("ID")
    comment = PropType.Text("Comment")
    company = PropType.Relation(
        "Company",
        schema=CompanySchema,
        two_way_prop=CompanySchema.related_to_platform_version_companies,
    )
    developer = PropType.Checkbox("Developer")
    manufacturer = PropType.Checkbox("Manufacturer")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_platform_versions_c = PropType.Relation("Related to Platform Versions (Companies)")
    related_to_platform_versions_m = PropType.Relation(
        "Related to Platform Versions (Main Manufacturer)"
    )


class PlatformVersionCompany(IGDBNotionPage[proto.PlatformVersionCompany]):
    schema = PlatformVersionCompanySchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.PlatformVersionCompany,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.company is not None:
            optionals["Company"] = props.Relations(
                Company.retrieve_or_create_from_data(data.company)
            )
        return {
            "ID": props.Number(data.id),
            "Comment": props.Text(data.comment[:MAX_TEXT_LENGTH]),
            "Developer": props.Checkbox(data.developer),
            "Manufacturer": props.Checkbox(data.manufacturer),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(
                " - ".join(
                    part
                    for part in (data.company.name if data.company else None, str(data.id))
                    if part
                )
            ),
        } | optionals

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


class ReleaseDateRegionSchema(uno.Schema, db_title="Release Date Regions"):
    id = PropType.Number("ID")
    region = PropType.Title("Region")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_platform_version_release_dates = PropType.Relation(
        "Related to Platform Version Release Dates (Release Region)"
    )
    related_to_release_dates = PropType.Relation("Related to Release Dates (Release Region)")


class ReleaseDateRegion(IGDBNotionPage[proto.ReleaseDateRegion]):
    schema = ReleaseDateRegionSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.ReleaseDateRegion,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Region": props.Title(data.region),
            "Checksum": props.Text(data.checksum),
        } | optionals


class PlatformVersionReleaseDateSchema(uno.Schema, db_title="Platform Version Release Dates"):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    date = PropType.Date("Date")
    human = PropType.Text("Human")
    m = PropType.Number("M")
    # platform_version = PropType.Relation("Platform Version", schema=PlatformVersionSchema)
    updated_at = PropType.Date("Updated At")
    y = PropType.Number("Y")
    checksum = PropType.Text("Checksum")
    date_format = PropType.Relation(
        "Date Format",
        schema=DateFormatSchema,
        two_way_prop=DateFormatSchema.related_to_platform_version_release_dates,
    )
    release_region = PropType.Relation(
        "Release Region",
        schema=ReleaseDateRegionSchema,
        two_way_prop=ReleaseDateRegionSchema.related_to_platform_version_release_dates,
    )
    title = PropType.Title("Title")
    related_to_platform_versions = PropType.Relation(
        "Related to Platform Versions (Release Dates)"
    )


class PlatformVersionReleaseDate(IGDBNotionPage[proto.PlatformVersionReleaseDate]):
    schema = PlatformVersionReleaseDateSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.PlatformVersionReleaseDate,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.date is not None:
            optionals["Date"] = props.Date(data.date.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        if data.date_format is not None:
            optionals["Date Format"] = props.Relations(
                DateFormat.retrieve_or_create_from_data(data.date_format)
            )
        if data.release_region is not None:
            optionals["Release Region"] = props.Relations(
                ReleaseDateRegion.retrieve_or_create_from_data(data.release_region)
            )
        return {
            "ID": props.Number(data.id),
            "Human": props.Text(data.human),
            "M": props.Number(data.m),
            "Y": props.Number(data.y),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(f"{data.y}/{data.m}"),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"date_format.{f}" for f in DateFormat.get_query_fields()),
                (f"release_region.{f}" for f in ReleaseDateRegion.get_query_fields()),
            )
        )


class PlatformVersionSchema(uno.Schema, db_title="Platform Versions"):
    id = PropType.Number("ID")
    companies = PropType.Relation(
        "Companies",
        schema=PlatformVersionCompanySchema,
        two_way_prop=PlatformVersionCompanySchema.related_to_platform_versions_c,
    )
    connectivity = PropType.Text("Connectivity")
    cpu = PropType.Text("CPU")
    graphics = PropType.Text("Graphics")
    main_manufacturer = PropType.Relation(
        "Main Manufacturer",
        schema=PlatformVersionCompanySchema,
        two_way_prop=PlatformVersionCompanySchema.related_to_platform_versions_m,
    )
    media = PropType.Text("Media")
    memory = PropType.Text("Memory")
    name = PropType.Title("Name")
    os = PropType.Text("OS")
    output = PropType.Text("Output")
    platform_logo = PropType.Relation(
        "Platform Logo",
        schema=PlatformLogoSchema,
        two_way_prop=PlatformLogoSchema.related_to_platform_versions,
    )
    release_dates = PropType.Relation(
        "Release Dates",
        schema=PlatformVersionReleaseDateSchema,
        two_way_prop=PlatformVersionReleaseDateSchema.related_to_platform_versions,
    )
    resolutions = PropType.Text("Resolutions")
    slug = PropType.Text("Slug")
    sound = PropType.Text("Sound")
    storage = PropType.Text("Storage")
    summary = PropType.Text("Summary")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_platforms = PropType.Relation("Related to Platforms (Versions)")


class PlatformVersion(IGDBNotionPage[proto.PlatformVersion]):
    schema = PlatformVersionSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.PlatformVersion,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.main_manufacturer is not None:
            optionals["Main Manufacturer"] = props.Relations(
                PlatformVersionCompany.retrieve_or_create_from_data(data.main_manufacturer)
            )
        if data.platform_logo is not None:
            optionals["Platform Logo"] = props.Relations(
                PlatformLogo.retrieve_or_create_from_data(data.platform_logo)
            )
        return {
            "ID": props.Number(data.id),
            "Companies": props.Relations(
                [
                    PlatformVersionCompany.retrieve_or_create_from_data(company)
                    for company in data.companies
                ]
            ),
            "Connectivity": props.Text(data.connectivity),
            "CPU": props.Text(data.cpu),
            "Graphics": props.Text(data.graphics),
            "Media": props.Text(data.media),
            "Memory": props.Text(data.memory),
            "Name": props.Title(data.name),
            "OS": props.Text(data.os),
            "Output": props.Text(data.output),
            "Release Dates": props.Relations(
                [
                    PlatformVersionReleaseDate.retrieve_or_create_from_data(release_date)
                    for release_date in data.platform_version_release_dates
                ]
            ),
            "Resolutions": props.Text(data.resolutions),
            "Slug": props.Text(data.slug),
            "Sound": props.Text(data.sound),
            "Storage": props.Text(data.storage),
            "Summary": props.Text(data.summary[:MAX_TEXT_LENGTH]),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
        } | optionals

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
        data: proto.PlatformVersion,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.platform_logo and data.platform_logo.url:
            icon_url = add_https_scheme(data.platform_logo.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class PlatformWebsiteSchema(uno.Schema, db_title="Platform Websites"):
    id = PropType.Number("ID")
    trusted = PropType.Checkbox("Trusted")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    type = PropType.Relation(
        "Type",
        schema=WebsiteTypeSchema,
        two_way_prop=WebsiteTypeSchema.related_to_platform_websites,
    )
    title = PropType.Title("Title")
    related_to_platforms = PropType.Relation("Related to Platforms (Websites)")


class PlatformWebsite(IGDBNotionPage[proto.PlatformWebsite]):
    schema = PlatformWebsiteSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.PlatformWebsite,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.type is not None:
            optionals["Type"] = props.Relations(
                WebsiteType.retrieve_or_create_from_data(data.type)
            )
        return {
            "ID": props.Number(data.id),
            "Trusted": props.Checkbox(data.trusted),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(
                (data.type.type if data.type else None) or data.url or str(data.id)
            ),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"type.{f}" for f in WebsiteType.get_query_fields()),
            )
        )


class PlatformSchema(uno.Schema, db_title="Platforms"):
    id = PropType.Number("ID")
    abbreviation = PropType.Text("Abbreviation")
    alternative_name = PropType.Text("Alternative Name")
    created_at = PropType.Date("Created At")
    generation = PropType.Number("Generation")
    name = PropType.Title("Name")
    platform_logo = PropType.Relation(
        "Platform Logo",
        schema=PlatformLogoSchema,
        two_way_prop=PlatformLogoSchema.related_to_platforms,
    )
    platform_family = PropType.Relation(
        "Platform Family",
        schema=PlatformFamilySchema,
        two_way_prop=PlatformFamilySchema.related_to_platforms,
    )
    slug = PropType.Text("Slug")
    summary = PropType.Text("Summary")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    versions = PropType.Relation(
        "Versions",
        schema=PlatformVersionSchema,
        two_way_prop=PlatformVersionSchema.related_to_platforms,
    )
    websites = PropType.Relation(
        "Websites",
        schema=PlatformWebsiteSchema,
        two_way_prop=PlatformWebsiteSchema.related_to_platforms,
    )
    checksum = PropType.Text("Checksum")
    platform_type = PropType.Relation(
        "Platform Type",
        schema=PlatformTypeSchema,
        two_way_prop=PlatformTypeSchema.related_to_platforms,
    )
    related_to_external_games = PropType.Relation("Related to External Games (Platform)")
    related_to_game_engines = PropType.Relation("Related to Game Engines (Platforms)")
    related_to_multiplayer_modes = PropType.Relation("Related to Multiplayer Modes (Platform)")
    related_to_release_dates = PropType.Relation("Related to Release Dates (Platform)")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Platforms)")


class Platform(IGDBNotionPage[proto.Platform]):
    schema = PlatformSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Platform) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.platform_logo is not None:
            optionals["Platform Logo"] = props.Relations(
                PlatformLogo.retrieve_or_create_from_data(data.platform_logo)
            )
        if data.platform_family is not None:
            optionals["Platform Family"] = props.Relations(
                PlatformFamily.retrieve_or_create_from_data(data.platform_family)
            )
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        if data.platform_type is not None:
            optionals["Platform Type"] = props.Relations(
                PlatformType.retrieve_or_create_from_data(data.platform_type)
            )
        return {
            "ID": props.Number(data.id),
            "Abbreviation": props.Text(data.abbreviation),
            "Alternative Name": props.Text(data.alternative_name),
            "Generation": props.Number(data.generation),
            "Name": props.Title(data.name),
            "Slug": props.Text(data.slug),
            "Summary": props.Text(data.summary[:MAX_TEXT_LENGTH]),
            "URL": props.URL(data.url or None),
            "Versions": props.Relations(
                [PlatformVersion.retrieve_or_create_from_data(ver) for ver in data.versions]
            ),
            "Websites": props.Relations(
                [PlatformWebsite.retrieve_or_create_from_data(ws) for ws in data.websites]
            ),
            "Checksum": props.Text(data.checksum),
        } | optionals

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
                (f"platform_type.{f}" for f in PlatformType.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.Platform,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.platform_logo and data.platform_logo.url:
            icon_url = add_https_scheme(data.platform_logo.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class ExternalGameSchema(uno.Schema, db_title="External Games"):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    # game = PropType.Relation("Game", schema=GameSchema)
    name = PropType.Title("Name")
    uid = PropType.Text("UID")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    year = PropType.Number("Year")
    platform = PropType.Relation(
        "Platform",
        schema=PlatformSchema,
        two_way_prop=PlatformSchema.related_to_external_games,
    )
    # countries = PropType.MultiSelect("Countries")
    checksum = PropType.Text("Checksum")
    external_game_source = PropType.Relation(
        "External Game Source",
        schema=ExternalGameSourceSchema,
        two_way_prop=ExternalGameSourceSchema.related_to_external_games,
    )
    game_release_format = PropType.Relation(
        "Game Release Format",
        schema=GameReleaseFormatSchema,
        two_way_prop=GameReleaseFormatSchema.related_to_external_games,
    )
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (External Games)")


class ExternalGame(IGDBNotionPage[proto.ExternalGame]):
    schema = ExternalGameSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.ExternalGame) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        if data.platform is not None:
            optionals["Platform"] = props.Relations(
                Platform.retrieve_or_create_from_data(data.platform)
            )
        if data.external_game_source is not None:
            optionals["External Game Source"] = props.Relations(
                ExternalGameSource.retrieve_or_create_from_data(data.external_game_source)
            )
        if data.game_release_format is not None:
            optionals["Game Release Format"] = props.Relations(
                GameReleaseFormat.retrieve_or_create_from_data(data.game_release_format)
            )
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "UID": props.Text(data.uid),
            "URL": props.URL(data.url or None),
            "Year": props.Number(data.year),
            # "Countries": props.MultiSelect([str(country) for country in data.countries]),
            "Checksum": props.Text(data.checksum),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                # (f"game.{f}" for f in Game.get_query_fields()),
                (f"platform.{f}" for f in Platform.get_query_fields()),
                (f"external_game_source.{f}" for f in ExternalGameSource.get_query_fields()),
                (f"game_release_format.{f}" for f in GameReleaseFormat.get_query_fields()),
            )
        )


class FranchiseSchema(uno.Schema, db_title="Franchises"):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    # games = PropType.Relation("Games", schema=GameSchema)
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Franchises)")


class Franchise(IGDBNotionPage[proto.Franchise]):
    schema = FranchiseSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Franchise) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Slug": props.Text(data.slug),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
        } | optionals


class GameEngineLogoSchema(uno.Schema, db_title="Game Engine Logos"):
    id = PropType.Number("ID")
    alpha_channel = PropType.Checkbox("Alpha Channel")
    animated = PropType.Checkbox("Animated")
    height = PropType.Number("Height")
    image_id = PropType.Text("Image ID")
    url = PropType.URL("URL")
    width = PropType.Number("Width")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_game_engines = PropType.Relation("Related to Game Engines (Logo)")


class GameEngineLogo(IGDBNotionPage[proto.GameEngineLogo]):
    schema = GameEngineLogoSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.GameEngineLogo,
    ) -> dict[str, props.PropertyValue]:
        return {
            "ID": props.Number(data.id),
            "Alpha Channel": props.Checkbox(data.alpha_channel),
            "Animated": props.Checkbox(data.animated),
            "Height": props.Number(data.height),
            "Image ID": props.Text(data.image_id),
            "URL": props.URL(data.url or None),
            "Width": props.Number(data.width),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(str(data.id)),
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.GameEngineLogo,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class GameEngineSchema(uno.Schema, db_title="Game Engines"):
    id = PropType.Number("ID")
    companies = PropType.Relation(
        "Companies",
        schema=CompanySchema,
        two_way_prop=CompanySchema.related_to_game_engines,
    )
    created_at = PropType.Date("Created At")
    description = PropType.Text("Description")
    logo = PropType.Relation(
        "Logo",
        schema=GameEngineLogoSchema,
        two_way_prop=GameEngineLogoSchema.related_to_game_engines,
    )
    name = PropType.Title("Name")
    platforms = PropType.Relation(
        "Platforms",
        schema=PlatformSchema,
        two_way_prop=PlatformSchema.related_to_game_engines,
    )
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Game Engines)")


class GameEngine(IGDBNotionPage[proto.GameEngine]):
    schema = GameEngineSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.GameEngine) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.logo is not None:
            optionals["Logo"] = props.Relations(
                GameEngineLogo.retrieve_or_create_from_data(data.logo)
            )
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Companies": props.Relations(
                [Company.retrieve_or_create_from_data(comp) for comp in data.companies]
            ),
            "Description": props.Text(data.description[:MAX_TEXT_LENGTH]),
            "Name": props.Title(data.name),
            "Platforms": props.Relations(
                [Platform.retrieve_or_create_from_data(platf) for platf in data.platforms]
            ),
            "Slug": props.Text(data.slug),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
        } | optionals

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
        data: proto.GameEngine,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.logo and data.logo.url:
            icon_url = add_https_scheme(data.logo.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class RegionSchema(uno.Schema, db_title="Regions"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    category = PropType.Text("Category")
    identifier = PropType.Text("Identifier")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_game_localizations = PropType.Relation("Related to Game Localizations (Region)")


class Region(IGDBNotionPage[proto.Region]):
    schema = RegionSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Region) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Category": props.Text(data.category),
            "Identifier": props.Text(data.identifier),
            "Checksum": props.Text(data.checksum),
        } | optionals


class GameLocalizationSchema(uno.Schema, db_title="Game Localizations"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    cover = PropType.Relation(
        "Cover",
        schema=CoverSchema,
        two_way_prop=CoverSchema.related_to_game_localizations,
    )
    region = PropType.Relation(
        "Region",
        schema=RegionSchema,
        two_way_prop=RegionSchema.related_to_game_localizations,
    )
    # game = PropType.Relation("Game", schema=GameSchema)
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Game Localizations)")


class GameLocalization(IGDBNotionPage[proto.GameLocalization]):
    schema = GameLocalizationSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.GameLocalization,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.cover is not None:
            optionals["Cover"] = props.Relations(Cover.retrieve_or_create_from_data(data.cover))
        if data.region is not None:
            optionals["Region"] = props.Relations(Region.retrieve_or_create_from_data(data.region))
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals

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
        data: proto.GameLocalization,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.cover and data.cover.url:
            icon_url = add_https_scheme(data.cover.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class GameModeSchema(uno.Schema, db_title="Game Modes"):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Game Modes)")


class GameMode(IGDBNotionPage[proto.GameMode]):
    schema = GameModeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.GameMode) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Slug": props.Text(data.slug),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
        } | optionals


class GameStatusSchema(uno.Schema, db_title="Game Statuses"):
    id = PropType.Number("ID")
    status = PropType.Title("Status")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Game Status)")


class GameStatus(IGDBNotionPage[proto.GameStatus]):
    schema = GameStatusSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.GameStatus) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Status": props.Title(data.status),
            "Checksum": props.Text(data.checksum),
        } | optionals


class GameTypeSchema(uno.Schema, db_title="Game Types"):
    id = PropType.Number("ID")
    type = PropType.Title("Type")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Game Type)")


class GameType(IGDBNotionPage[proto.GameType]):
    schema = GameTypeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.GameType) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Type": props.Title(data.type),
            "Checksum": props.Text(data.checksum),
        } | optionals


class GameVideoSchema(uno.Schema, db_title="Game Videos"):
    id = PropType.Number("ID")
    # game = PropType.Relation("Game", schema=GameSchema)
    name = PropType.Title("Name")
    video_id = PropType.Text("Video ID")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Videos)")


class GameVideo(IGDBNotionPage[proto.GameVideo]):
    schema = GameVideoSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.GameVideo) -> dict[str, props.PropertyValue]:
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Video ID": props.Text(data.video_id),
            "Checksum": props.Text(data.checksum),
        }


class GenreSchema(uno.Schema, db_title="Genres"):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Genres)")


class Genre(IGDBNotionPage[proto.Genre]):
    schema = GenreSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Genre) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Slug": props.Text(data.slug),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
        } | optionals


class InvolvedCompanySchema(uno.Schema, db_title="Involved Companies"):
    id = PropType.Number("ID")
    company = PropType.Relation(
        "Company",
        schema=CompanySchema,
        two_way_prop=CompanySchema.related_to_involved_companies,
    )
    created_at = PropType.Date("Created At")
    developer = PropType.Checkbox("Developer")
    porting = PropType.Checkbox("Porting")
    publisher = PropType.Checkbox("Publisher")
    supporting = PropType.Checkbox("Supporting")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    # game = PropType.Relation("Game", schema=GameSchema)
    title = PropType.Title("Title")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Involved Companies)")


class InvolvedCompany(IGDBNotionPage[proto.InvolvedCompany]):
    schema = InvolvedCompanySchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.InvolvedCompany,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.company is not None:
            optionals["Company"] = props.Relations(
                Company.retrieve_or_create_from_data(data.company)
            )
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Developer": props.Checkbox(data.developer),
            "Porting": props.Checkbox(data.porting),
            "Publisher": props.Checkbox(data.publisher),
            "Supporting": props.Checkbox(data.supporting),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title((data.company.name if data.company else None) or str(data.id)),
        } | optionals

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
        data: proto.InvolvedCompany,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.company and data.company.logo and data.company.logo.url:
            icon_url = add_https_scheme(data.company.logo.url).replace("t_thumb", "t_logo_med")
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_logo_med")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class KeywordSchema(uno.Schema, db_title="Keywords"):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Keywords)")


class Keyword(IGDBNotionPage[proto.Keyword]):
    schema = KeywordSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Keyword) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Slug": props.Text(data.slug),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
        } | optionals


class LanguageSchema(uno.Schema, db_title="Languages"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    native_name = PropType.Text("Native Name")
    locale = PropType.Text("Locale")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_language_supports = PropType.Relation("Related to Language Supports (Language)")


class Language(IGDBNotionPage[proto.Language]):
    schema = LanguageSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Language) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Native Name": props.Text(data.native_name),
            "Locale": props.Text(data.locale),
            "Checksum": props.Text(data.checksum),
        } | optionals


class LanguageSupportTypeSchema(uno.Schema, db_title="Language Support Types"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_language_supports = PropType.Relation(
        "Related to Language Supports (Language Support Type)"
    )


class LanguageSupportType(IGDBNotionPage[proto.LanguageSupportType]):
    schema = LanguageSupportTypeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.LanguageSupportType,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals


class LanguageSupportSchema(uno.Schema, db_title="Language Supports"):
    id = PropType.Number("ID")
    # game = PropType.Relation("Game", schema=GameSchema)
    language = PropType.Relation(
        "Language",
        schema=LanguageSchema,
        two_way_prop=LanguageSchema.related_to_language_supports,
    )
    language_support_type = PropType.Relation(
        "Language Support Type",
        schema=LanguageSupportTypeSchema,
        two_way_prop=LanguageSupportTypeSchema.related_to_language_supports,
    )
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Language Supports)")


class LanguageSupport(IGDBNotionPage[proto.LanguageSupport]):
    schema = LanguageSupportSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.LanguageSupport,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.language is not None:
            optionals["Language"] = props.Relations(
                Language.retrieve_or_create_from_data(data.language)
            )
        if data.language_support_type is not None:
            optionals["Language Support Type"] = props.Relations(
                LanguageSupportType.retrieve_or_create_from_data(data.language_support_type)
            )
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(
                " - ".join(
                    part
                    for part in (
                        data.language.name if data.language else None,
                        data.language_support_type.name if data.language_support_type else None,
                    )
                    if part
                )
            ),
        } | optionals

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


class MultiplayerModeSchema(uno.Schema, db_title="Multiplayer Modes"):
    id = PropType.Number("ID")
    campaigncoop = PropType.Checkbox("Campaign Coop")
    dropin = PropType.Checkbox("Drop In")
    # game = PropType.Relation("Game", schema=GameSchema)
    lancoop = PropType.Checkbox("LAN Coop")
    offlinecoop = PropType.Checkbox("Offline Coop")
    offlinecoopmax = PropType.Number("Offline Coop Max")
    offlinemax = PropType.Number("Offline Max")
    onlinecoop = PropType.Checkbox("Online Coop")
    onlinecoopmax = PropType.Number("Online Coop Max")
    onlinemax = PropType.Number("Online Max")
    platform = PropType.Relation(
        "Platform",
        schema=PlatformSchema,
        two_way_prop=PlatformSchema.related_to_multiplayer_modes,
    )
    splitscreen = PropType.Checkbox("Split Screen")
    splitscreenonline = PropType.Checkbox("Split Screen Online")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Multiplayer Modes)")


class MultiplayerMode(IGDBNotionPage[proto.MultiplayerMode]):
    schema = MultiplayerModeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.MultiplayerMode,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.platform is not None:
            optionals["Platform"] = props.Relations(
                Platform.retrieve_or_create_from_data(data.platform)
            )
        return {
            "ID": props.Number(data.id),
            "Campaign Coop": props.Checkbox(data.campaigncoop),
            "Drop In": props.Checkbox(data.dropin),
            "LAN Coop": props.Checkbox(data.lancoop),
            "Offline Coop": props.Checkbox(data.offlinecoop),
            "Offline Coop Max": props.Number(data.offlinecoopmax),
            "Offline Max": props.Number(data.offlinemax),
            "Online Coop": props.Checkbox(data.onlinecoop),
            "Online Coop Max": props.Number(data.onlinecoopmax),
            "Online Max": props.Number(data.onlinemax),
            "Split Screen": props.Checkbox(data.splitscreen),
            "Split Screen Online": props.Checkbox(data.splitscreenonline),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(
                " - ".join(
                    part
                    for part in (data.platform.name if data.platform else None, str(data.id))
                    if part
                )
            ),
        } | optionals

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


class PlayerPerspectiveSchema(uno.Schema, db_title="Player Perspectives"):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Player Perspectives)")


class PlayerPerspective(IGDBNotionPage[proto.PlayerPerspective]):
    schema = PlayerPerspectiveSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.PlayerPerspective,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Slug": props.Text(data.slug),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
        } | optionals


class ReleaseDateStatusSchema(uno.Schema, db_title="Release Date Statuses"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    description = PropType.Text("Description")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_release_dates = PropType.Relation("Related to Release Dates (Status)")


class ReleaseDateStatus(IGDBNotionPage[proto.ReleaseDateStatus]):
    schema = ReleaseDateStatusSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.ReleaseDateStatus,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Description": props.Text(data.description[:MAX_TEXT_LENGTH]),
            "Checksum": props.Text(data.checksum),
        } | optionals


class ReleaseDateSchema(uno.Schema, db_title="Release Dates"):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    date = PropType.Date("Date")
    # game = PropType.Relation("Game", schema=GameSchema)
    human = PropType.Text("Human")
    m = PropType.Number("M")
    platform = PropType.Relation(
        "Platform",
        schema=PlatformSchema,
        two_way_prop=PlatformSchema.related_to_release_dates,
    )
    updated_at = PropType.Date("Updated At")
    y = PropType.Number("Y")
    checksum = PropType.Text("Checksum")
    status = PropType.Relation(
        "Status",
        schema=ReleaseDateStatusSchema,
        two_way_prop=ReleaseDateStatusSchema.related_to_release_dates,
    )
    date_format = PropType.Relation(
        "Date Format",
        schema=DateFormatSchema,
        two_way_prop=DateFormatSchema.related_to_release_dates,
    )
    release_region = PropType.Relation(
        "Release Region",
        schema=ReleaseDateRegionSchema,
        two_way_prop=ReleaseDateRegionSchema.related_to_release_dates,
    )
    d = PropType.Number("D")
    title = PropType.Title("Title")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Release Dates)")


class ReleaseDate(IGDBNotionPage[proto.ReleaseDate]):
    schema = ReleaseDateSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.ReleaseDate) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.date is not None:
            optionals["Date"] = props.Date(data.date.isoformat())
        if data.platform is not None:
            optionals["Platform"] = props.Relations(
                Platform.retrieve_or_create_from_data(data.platform)
            )
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        if data.status is not None:
            optionals["Status"] = props.Relations(
                ReleaseDateStatus.retrieve_or_create_from_data(data.status)
            )
        if data.date_format is not None:
            optionals["Date Format"] = props.Relations(
                DateFormat.retrieve_or_create_from_data(data.date_format)
            )
        if data.release_region is not None:
            optionals["Release Region"] = props.Relations(
                ReleaseDateRegion.retrieve_or_create_from_data(data.release_region)
            )
        return {
            "ID": props.Number(data.id),
            "Human": props.Text(data.human),
            "M": props.Number(data.m),
            "Y": props.Number(data.y),
            "Checksum": props.Text(data.checksum),
            "D": props.Number(data.d),
            "Title": props.Title(
                (
                    " - ".join(
                        part
                        for part in (
                            data.platform.name if data.platform else None,
                            f"{data.y}/{data.m}",
                        )
                        if part
                    )
                ),
            ),
        } | optionals

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
                (f"date_format.{f}" for f in DateFormat.get_query_fields()),
                (f"release_region.{f}" for f in ReleaseDateRegion.get_query_fields()),
            )
        )


class ScreenshotSchema(uno.Schema, db_title="Screenshots"):
    id = PropType.Number("ID")
    alpha_channel = PropType.Checkbox("Alpha Channel")
    animated = PropType.Checkbox("Animated")
    # game = PropType.Relation("Game", schema=GameSchema)
    height = PropType.Number("Height")
    image_id = PropType.Text("Image ID")
    url = PropType.URL("URL")
    width = PropType.Number("Width")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Screenshots)")


class Screenshot(IGDBNotionPage[proto.Screenshot]):
    schema = ScreenshotSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Screenshot) -> dict[str, props.PropertyValue]:
        return {
            "ID": props.Number(data.id),
            "Alpha Channel": props.Checkbox(data.alpha_channel),
            "Animated": props.Checkbox(data.animated),
            "Height": props.Number(data.height),
            "Image ID": props.Text(data.image_id),
            "URL": props.URL(data.url or None),
            "Width": props.Number(data.width),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(str(data.id)),
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.Screenshot,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("t_thumb", "t_1080p")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class ThemeSchema(uno.Schema, db_title="Themes"):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Themes)")


class Theme(IGDBNotionPage[proto.Theme]):
    schema = ThemeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Theme) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Slug": props.Text(data.slug),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
        } | optionals


class WebsiteSchema(uno.Schema, db_title="Websites"):
    id = PropType.Number("ID")
    # game = PropType.Relation("Game", schema=GameSchema)
    trusted = PropType.Checkbox("Trusted")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    type = PropType.Relation(
        "Type",
        schema=WebsiteTypeSchema,
        two_way_prop=WebsiteTypeSchema.related_to_websites,
    )
    title = PropType.Title("Title")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Websites)")


class Website(IGDBNotionPage[proto.Website]):
    schema = WebsiteSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Website) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.type is not None:
            optionals["Type"] = props.Relations(
                WebsiteType.retrieve_or_create_from_data(data.type)
            )
        return {
            "ID": props.Number(data.id),
            "Trusted": props.Checkbox(data.trusted),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(
                (data.type.type if data.type else None) or data.url or str(data.id)
            ),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"type.{f}" for f in WebsiteType.get_query_fields()),
            )
        )


class GameSchema(uno.Schema, db_title="IGDB Games"):
    id = PropType.Number("ID")
    age_ratings = PropType.Relation(
        "Age Ratings",
        schema=AgeRatingSchema,
        two_way_prop=AgeRatingSchema.related_to_igdb_games,
    )
    aggregated_rating = PropType.Number("Aggregated Rating")
    aggregated_rating_count = PropType.Number("Aggregated Rating Count")
    alternative_names = PropType.Relation(
        "Alternative Names",
        schema=AlternativeNameSchema,
        two_way_prop=AlternativeNameSchema.related_to_igdb_games,
    )
    artworks = PropType.Relation(
        "Artworks",
        schema=ArtworkSchema,
        two_way_prop=ArtworkSchema.related_to_igdb_games,
    )
    # bundles = PropType.Relation("Bundles", schema=uno.SelfRef)
    cover = PropType.Relation(
        "Cover",
        schema=CoverSchema,
        two_way_prop=CoverSchema.related_to_igdb_games,
    )
    created_at = PropType.Date("Created At")
    # dlcs = PropType.Relation("DLCs", schema=uno.SelfRef)
    # expansions = PropType.Relation("Expansions", schema=uno.SelfRef)
    external_games = PropType.Relation(
        "External Games",
        schema=ExternalGameSchema,
        two_way_prop=ExternalGameSchema.related_to_igdb_games,
    )
    first_release_date = PropType.Date("First Release Date")
    franchises = PropType.Relation(
        "Franchises",
        schema=FranchiseSchema,
        two_way_prop=FranchiseSchema.related_to_igdb_games,
    )
    game_engines = PropType.Relation(
        "Game Engines",
        schema=GameEngineSchema,
        two_way_prop=GameEngineSchema.related_to_igdb_games,
    )
    game_modes = PropType.Relation(
        "Game Modes",
        schema=GameModeSchema,
        two_way_prop=GameModeSchema.related_to_igdb_games,
    )
    genres = PropType.Relation(
        "Genres",
        schema=GenreSchema,
        two_way_prop=GenreSchema.related_to_igdb_games,
    )
    hypes = PropType.Number("Hypes")
    involved_companies = PropType.Relation(
        "Involved Companies",
        schema=InvolvedCompanySchema,
        two_way_prop=InvolvedCompanySchema.related_to_igdb_games,
    )
    keywords = PropType.Relation(
        "Keywords",
        schema=KeywordSchema,
        two_way_prop=KeywordSchema.related_to_igdb_games,
    )
    multiplayer_modes = PropType.Relation(
        "Multiplayer Modes",
        schema=MultiplayerModeSchema,
        two_way_prop=MultiplayerModeSchema.related_to_igdb_games,
    )
    name = PropType.Title("Name")
    # parent_game = PropType.Relation("Parent Game", schema=uno.SelfRef)
    platforms = PropType.Relation(
        "Platforms",
        schema=PlatformSchema,
        two_way_prop=PlatformSchema.related_to_igdb_games,
    )
    player_perspectives = PropType.Relation(
        "Player Perspectives",
        schema=PlayerPerspectiveSchema,
        two_way_prop=PlayerPerspectiveSchema.related_to_igdb_games,
    )
    rating = PropType.Number("Rating")
    rating_count = PropType.Number("Rating Count")
    release_dates = PropType.Relation(
        "Release Dates",
        schema=ReleaseDateSchema,
        two_way_prop=ReleaseDateSchema.related_to_igdb_games,
    )
    screenshots = PropType.Relation(
        "Screenshots",
        schema=ScreenshotSchema,
        two_way_prop=ScreenshotSchema.related_to_igdb_games,
    )
    # similar_games = PropType.Relation("Similar Games", schema=uno.SelfRef)
    slug = PropType.Text("Slug")
    # standalone_expansions = PropType.Relation("Standalone Expansions", schema=uno.SelfRef)
    storyline = PropType.Text("Storyline")
    summary = PropType.Text("Summary")
    themes = PropType.Relation(
        "Themes",
        schema=ThemeSchema,
        two_way_prop=ThemeSchema.related_to_igdb_games,
    )
    total_rating = PropType.Number("Total Rating")
    total_rating_count = PropType.Number("Total Rating Count")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    # version_parent = PropType.Relation("Version Parent", schema=uno.SelfRef)
    version_title = PropType.Text("Version Title")
    videos = PropType.Relation(
        "Videos",
        schema=GameVideoSchema,
        two_way_prop=GameVideoSchema.related_to_igdb_games,
    )
    websites = PropType.Relation(
        "Websites",
        schema=WebsiteSchema,
        two_way_prop=WebsiteSchema.related_to_igdb_games,
    )
    checksum = PropType.Text("Checksum")
    # remakes = PropType.Relation("Remakes", schema=uno.SelfRef)
    # remasters = PropType.Relation("Remasters", schema=uno.SelfRef)
    # expanded_games = PropType.Relation("Expanded Games", schema=uno.SelfRef)
    # ports = PropType.Relation("Ports", schema=uno.SelfRef)
    # forks = PropType.Relation("Forks", schema=uno.SelfRef)
    language_supports = PropType.Relation(
        "Language Supports",
        schema=LanguageSupportSchema,
        two_way_prop=LanguageSupportSchema.related_to_igdb_games,
    )
    game_localizations = PropType.Relation(
        "Game Localizations",
        schema=GameLocalizationSchema,
        two_way_prop=GameLocalizationSchema.related_to_igdb_games,
    )
    # collections = PropType.Relation("Collections", schema=CollectionSchema)
    game_status = PropType.Relation(
        "Game Status",
        schema=GameStatusSchema,
        two_way_prop=GameStatusSchema.related_to_igdb_games,
    )
    game_type = PropType.Relation(
        "Game Type",
        schema=GameTypeSchema,
        two_way_prop=GameTypeSchema.related_to_igdb_games,
    )


class Game(IGDBNotionPage[proto.Game]):
    schema = GameSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Game) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.cover is not None:
            optionals["Cover"] = props.Relations(Cover.retrieve_or_create_from_data(data.cover))
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.first_release_date is not None:
            optionals["First Release Date"] = props.Date(data.first_release_date.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        if data.game_status is not None:
            optionals["Game Status"] = props.Relations(
                GameStatus.retrieve_or_create_from_data(data.game_status)
            )
        if data.game_type is not None:
            optionals["Game Type"] = props.Relations(
                GameType.retrieve_or_create_from_data(data.game_type)
            )
        return {
            "ID": props.Number(data.id),
            "Age Ratings": props.Relations(
                [AgeRating.retrieve_or_create_from_data(ar) for ar in data.age_ratings]
            ),
            "Aggregated Rating": props.Number(data.aggregated_rating),
            "Aggregated Rating Count": props.Number(data.aggregated_rating_count),
            "Alternative Names": props.Relations(
                [
                    AlternativeName.retrieve_or_create_from_data(name)
                    for name in data.alternative_names
                ]
            ),
            "Artworks": props.Relations(
                [Artwork.retrieve_or_create_from_data(artwork) for artwork in data.artworks]
            ),
            # "Collection": props.Relations(
            #     Collection.retrieve_or_create_from_data(data.collection)
            # ),
            "External Games": props.Relations(
                [ExternalGame.retrieve_or_create_from_data(game) for game in data.external_games]
            ),
            # "Follows": props.Number(data.follows),
            # "Franchise": props.Relations(Franchise.retrieve_or_create_from_data(data.franchise)),
            "Franchises": props.Relations(
                [Franchise.retrieve_or_create_from_data(franc) for franc in data.franchises]
            ),
            "Game Engines": props.Relations(
                [GameEngine.retrieve_or_create_from_data(eng) for eng in data.game_engines]
            ),
            "Game Modes": props.Relations(
                [GameMode.retrieve_or_create_from_data(mode) for mode in data.game_modes]
            ),
            "Genres": props.Relations(
                [Genre.retrieve_or_create_from_data(genre) for genre in data.genres]
            ),
            "Hypes": props.Number(data.hypes),
            "Involved Companies": props.Relations(
                [
                    InvolvedCompany.retrieve_or_create_from_data(company)
                    for company in data.involved_companies
                ]
            ),
            "Keywords": props.Relations(
                [
                    Keyword.retrieve_or_create_from_data(keyword)
                    for keyword in data.keywords[:MAX_RELATION_PAGES]
                ]
            ),
            "Multiplayer Modes": props.Relations(
                [
                    MultiplayerMode.retrieve_or_create_from_data(mode)
                    for mode in data.multiplayer_modes
                ]
            ),
            "Name": props.Title(data.name),
            "Platforms": props.Relations(
                [Platform.retrieve_or_create_from_data(platf) for platf in data.platforms]
            ),
            "Player Perspectives": props.Relations(
                [
                    PlayerPerspective.retrieve_or_create_from_data(perspective)
                    for perspective in data.player_perspectives
                ]
            ),
            "Rating": props.Number(data.rating),
            "Rating Count": props.Number(data.rating_count),
            "Release Dates": props.Relations(
                [
                    ReleaseDate.retrieve_or_create_from_data(reldate)
                    for reldate in data.release_dates
                ]
            ),
            "Screenshots": props.Relations(
                [Screenshot.retrieve_or_create_from_data(shot) for shot in data.screenshots]
            ),
            "Slug": props.Text(data.slug),
            "Storyline": props.Text(data.storyline[:MAX_TEXT_LENGTH]),
            "Summary": props.Text(data.summary),
            # "Tags": props.MultiSelect([str(tag) for tag in data.tags]),
            "Themes": props.Relations(
                [Theme.retrieve_or_create_from_data(theme) for theme in data.themes]
            ),
            "Total Rating": props.Number(data.total_rating),
            "Total Rating Count": props.Number(data.total_rating_count),
            "URL": props.URL(data.url or None),
            "Version Title": props.Text(data.version_title),
            "Videos": props.Relations(
                [GameVideo.retrieve_or_create_from_data(vid) for vid in data.videos]
            ),
            "Websites": props.Relations(
                [Website.retrieve_or_create_from_data(site) for site in data.websites]
            ),
            "Checksum": props.Text(data.checksum),
            "Language Supports": props.Relations(
                [
                    LanguageSupport.retrieve_or_create_from_data(lang_support)
                    for lang_support in data.language_supports
                ]
            ),
            "Game Localizations": props.Relations(
                [
                    GameLocalization.retrieve_or_create_from_data(localization)
                    for localization in data.game_localizations
                ]
            ),
            # "Collections": props.Relations(
            #     [Collection.retrieve_or_create_from_data(col) for col in data.collections]
            # ),
        } | optionals

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
                (f"game_status.{f}" for f in GameStatus.get_query_fields()),
                (f"game_type.{f}" for f in GameType.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.Game,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.cover and data.cover.url:
            icon_url = add_https_scheme(data.cover.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class CollectionTypeSchema(uno.Schema, db_title="Collection Types"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    description = PropType.Text("Description")
    updated_at = PropType.Date("Updated At")
    created_at = PropType.Date("Created At")
    checksum = PropType.Text("Checksum")
    related_to_collections = PropType.Relation("Related to Collections (Type)")
    related_to_collection_membership_types = PropType.Relation(
        "Related to Collection Membership Types (Allowed Collection Type)"
    )
    related_to_collection_relation_types_allowed_child_type = PropType.Relation(
        "Related to Collection Relation Types (Allowed Child Type)"
    )
    related_to_collection_relation_types_allowed_parent_type = PropType.Relation(
        "Related to Collection Relation Types (Allowed Parent Type)"
    )


class CollectionType(IGDBNotionPage[proto.CollectionType]):
    schema = CollectionTypeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.CollectionType,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Description": props.Text(data.description[:MAX_TEXT_LENGTH]),
            "Checksum": props.Text(data.checksum),
        } | optionals


class CollectionSchema(uno.Schema, db_title="Collections"):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    games = PropType.Relation("Games", schema=GameSchema)
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    type = PropType.Relation(
        "Type",
        schema=CollectionTypeSchema,
        two_way_prop=CollectionTypeSchema.related_to_collections,
    )
    # as_parent_relations = PropType.Relation(
    #     "As Parent Relations", schema=CollectionRelationSchema
    # )
    # as_child_relations = PropType.Relation("As Child Relations", schema=CollectionRelationSchema)
    related_to_collection_memberships = PropType.Relation(
        "Related to Collection Memberships (Collection)"
    )
    related_to_collection_relations_child_collection = PropType.Relation(
        "Related to Collection Relations (Child Collection)"
    )
    related_to_collection_relations_parent_collection = PropType.Relation(
        "Related to Collection Relations (Parent Collection)"
    )


class Collection(IGDBNotionPage[proto.Collection]):
    schema = CollectionSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Collection) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        if data.type is not None:
            optionals["Type"] = props.Relations(
                CollectionType.retrieve_or_create_from_data(data.type)
            )
        return {
            "ID": props.Number(data.id),
            "Games": props.Relations(
                [Game.retrieve_or_create_from_data(game) for game in data.games]
            ),
            "Name": props.Title(data.name),
            "Slug": props.Text(data.slug),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
        } | optionals

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


class CollectionMembershipTypeSchema(uno.Schema, db_title="Collection Membership Types"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    description = PropType.Text("Description")
    allowed_collection_type = PropType.Relation(
        "Allowed Collection Type",
        schema=CollectionTypeSchema,
        two_way_prop=CollectionTypeSchema.related_to_collection_membership_types,
    )
    updated_at = PropType.Date("Updated At")
    created_at = PropType.Date("Created At")
    checksum = PropType.Text("Checksum")
    related_to_collection_memberships = PropType.Relation(
        "Related to Collection Memberships (Type)"
    )


class CollectionMembershipType(IGDBNotionPage[proto.CollectionMembershipType]):
    schema = CollectionMembershipTypeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.CollectionMembershipType,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.allowed_collection_type is not None:
            optionals["Allowed Collection Type"] = props.Relations(
                CollectionType.retrieve_or_create_from_data(data.allowed_collection_type)
            )
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Description": props.Text(data.description[:MAX_TEXT_LENGTH]),
            "Checksum": props.Text(data.checksum),
        } | optionals

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


class CollectionMembershipSchema(uno.Schema, db_title="Collection Memberships"):
    id = PropType.Number("ID")
    game = PropType.Relation("Game", schema=GameSchema)
    collection = PropType.Relation(
        "Collection",
        schema=CollectionSchema,
        two_way_prop=CollectionSchema.related_to_collection_memberships,
    )
    type = PropType.Relation(
        "Type",
        schema=CollectionMembershipTypeSchema,
        two_way_prop=CollectionMembershipTypeSchema.related_to_collection_memberships,
    )
    updated_at = PropType.Date("Updated At")
    created_at = PropType.Date("Created At")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")


class CollectionMembership(IGDBNotionPage[proto.CollectionMembership]):
    schema = CollectionMembershipSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.CollectionMembership,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.game is not None:
            optionals["Game"] = props.Relations(Game.retrieve_or_create_from_data(data.game))
        if data.collection is not None:
            optionals["Collection"] = props.Relations(
                Collection.retrieve_or_create_from_data(data.collection)
            )
        if data.type is not None:
            optionals["Type"] = props.Relations(
                CollectionMembershipType.retrieve_or_create_from_data(data.type)
            )
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(
                " - ".join(
                    part
                    for part in (
                        data.game.name if data.game else None,
                        data.collection.name if data.collection else None,
                        data.type.name if data.type else None,
                    )
                    if part
                )
            ),
        } | optionals

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


class CollectionRelationTypeSchema(uno.Schema, db_title="Collection Relation Types"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    description = PropType.Text("Description")
    allowed_child_type = PropType.Relation(
        "Allowed Child Type",
        schema=CollectionTypeSchema,
        two_way_prop=CollectionTypeSchema.related_to_collection_relation_types_allowed_child_type,
    )
    allowed_parent_type = PropType.Relation(
        "Allowed Parent Type",
        schema=CollectionTypeSchema,
        two_way_prop=CollectionTypeSchema.related_to_collection_relation_types_allowed_parent_type,
    )
    updated_at = PropType.Date("Updated At")
    created_at = PropType.Date("Created At")
    checksum = PropType.Text("Checksum")
    related_to_collection_relations = PropType.Relation("Related to Collection Relations (Type)")


class CollectionRelationType(IGDBNotionPage[proto.CollectionRelationType]):
    schema = CollectionRelationTypeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.CollectionRelationType,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.allowed_child_type is not None:
            optionals["Allowed Child Type"] = props.Relations(
                CollectionType.retrieve_or_create_from_data(data.allowed_child_type)
            )
        if data.allowed_parent_type is not None:
            optionals["Allowed Parent Type"] = props.Relations(
                CollectionType.retrieve_or_create_from_data(data.allowed_parent_type)
            )
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Description": props.Text(data.description[:MAX_TEXT_LENGTH]),
            "Checksum": props.Text(data.checksum),
        } | optionals

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


class CollectionRelationSchema(uno.Schema, db_title="Collection Relations"):
    id = PropType.Number("ID")
    child_collection = PropType.Relation(
        "Child Collection",
        schema=CollectionSchema,
        two_way_prop=CollectionSchema.related_to_collection_relations_child_collection,
    )
    parent_collection = PropType.Relation(
        "Parent Collection",
        schema=CollectionSchema,
        two_way_prop=CollectionSchema.related_to_collection_relations_parent_collection,
    )
    type = PropType.Relation(
        "Type",
        schema=CollectionRelationTypeSchema,
        two_way_prop=CollectionRelationTypeSchema.related_to_collection_relations,
    )
    updated_at = PropType.Date("Updated At")
    created_at = PropType.Date("Created At")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")


class CollectionRelation(IGDBNotionPage[proto.CollectionRelation]):
    schema = CollectionRelationSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.CollectionRelation,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.child_collection is not None:
            optionals["Child Collection"] = props.Relations(
                Collection.retrieve_or_create_from_data(data.child_collection)
            )
        if data.parent_collection is not None:
            optionals["Parent Collection"] = props.Relations(
                Collection.retrieve_or_create_from_data(data.parent_collection)
            )
        if data.type is not None:
            optionals["Type"] = props.Relations(
                CollectionRelationType.retrieve_or_create_from_data(data.type)
            )
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(
                " - ".join(
                    part
                    for part in (
                        data.parent_collection.name if data.parent_collection else None,
                        data.child_collection.name if data.child_collection else None,
                        data.type.name if data.type else None,
                    )
                    if part
                )
            ),
        } | optionals

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


class GameTimeToBeatSchema(uno.Schema, db_title="Game Times To Beat"):
    id = PropType.Number("ID")
    game_id = PropType.Number("Game ID")
    hastily = PropType.Number("Hastily")
    normally = PropType.Number("Normally")
    completely = PropType.Number("Completely")
    count = PropType.Number("Count")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")


class GameTimeToBeat(IGDBNotionPage[proto.GameTimeToBeat]):
    schema = GameTimeToBeatSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.GameTimeToBeat,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Game ID": props.Number(data.game_id),
            "Hastily": props.Number(data.hastily),
            "Normally": props.Number(data.normally),
            "Completely": props.Number(data.completely),
            "Count": props.Number(data.count),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(str(data.id)),
        } | optionals


class GameVersionFeatureValueSchema(uno.Schema, db_title="Game Version Feature Values"):
    id = PropType.Number("ID")
    game = PropType.Relation("Game", schema=GameSchema)
    # game_feature = PropType.Relation("Game Feature", schema=GameVersionFeatureSchema)
    included_feature = PropType.Select(
        "Included Feature",
        options=[
            uno.Option(nm) for nm in proto.GameVersionFeatureValueIncludedFeatureEnum.__members__
        ],
    )
    note = PropType.Text("Note")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_game_version_features = PropType.Relation(
        "Related to Game Version Features (Values)"
    )


class GameVersionFeatureValue(IGDBNotionPage[proto.GameVersionFeatureValue]):
    schema = GameVersionFeatureValueSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.GameVersionFeatureValue,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.game is not None:
            optionals["Game"] = props.Relations(Game.retrieve_or_create_from_data(data.game))
        return {
            "ID": props.Number(data.id),
            "Included Feature": props.Select(data.included_feature.name or ""),
            "Note": props.Text(data.note[:MAX_TEXT_LENGTH]),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(
                " - ".join(
                    part
                    for part in (
                        data.game.name if data.game else None,
                        data.included_feature.name if data.included_feature else None,
                    )
                    if part
                )
            ),
        } | optionals

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


class GameVersionFeatureSchema(uno.Schema, db_title="Game Version Features"):
    id = PropType.Number("ID")
    category = PropType.Select(
        "Category",
        options=[uno.Option(name) for name in proto.GameVersionFeatureCategoryEnum.__members__],
    )
    description = PropType.Text("Description")
    position = PropType.Number("Position")
    title = PropType.Title("Title")
    values = PropType.Relation(
        "Values",
        schema=GameVersionFeatureValueSchema,
        two_way_prop=GameVersionFeatureValueSchema.related_to_game_version_features,
    )
    checksum = PropType.Text("Checksum")
    related_to_game_versions = PropType.Relation("Related to Game Versions (Features)")


class GameVersionFeature(IGDBNotionPage[proto.GameVersionFeature]):
    schema = GameVersionFeatureSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.GameVersionFeature,
    ) -> dict[str, props.PropertyValue]:
        return {
            "ID": props.Number(data.id),
            "Category": props.Select(data.category.name or ""),
            "Description": props.Text(data.description[:MAX_TEXT_LENGTH]),
            "Position": props.Number(data.position),
            "Title": props.Title(data.title),
            "Values": props.Relations(
                [
                    GameVersionFeatureValue.retrieve_or_create_from_data(value)
                    for value in data.values
                ]
            ),
            "Checksum": props.Text(data.checksum),
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


class CollectionVersionSchema(uno.Schema, db_title="Collection Versions"):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    features = PropType.Relation(
        "Features",
        schema=GameVersionFeatureSchema,
        two_way_prop=GameVersionFeatureSchema.related_to_game_versions,
    )
    game = PropType.Relation("Game", schema=GameSchema)
    games = PropType.Relation("Games", schema=GameSchema)
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")


class GameVersion(IGDBNotionPage[proto.GameVersion]):
    schema = CollectionVersionSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.GameVersion) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.game is not None:
            optionals["Game"] = props.Relations(Game.retrieve_or_create_from_data(data.game))
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Features": props.Relations(
                [GameVersionFeature.retrieve_or_create_from_data(feat) for feat in data.features]
            ),
            "Games": props.Relations(
                [Game.retrieve_or_create_from_data(game) for game in data.games]
            ),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(str(data.id)),
        } | optionals

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


class CharacterGenderSchema(uno.Schema, db_title="Character Genders"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_characters = PropType.Relation("Related to Characters (Character Gender)")


class CharacterGender(IGDBNotionPage[proto.CharacterGender]):
    schema = CharacterGenderSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.CharacterGender,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals


class CharacterMugShotSchema(uno.Schema, db_title="Character Mug Shots"):
    id = PropType.Number("ID")
    alpha_channel = PropType.Checkbox("Alpha Channel")
    animated = PropType.Checkbox("Animated")
    height = PropType.Number("Height")
    image_id = PropType.Text("Image ID")
    url = PropType.URL("URL")
    width = PropType.Number("Width")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_characters = PropType.Relation("Related to Characters (Mug Shot)")


class CharacterMugShot(IGDBNotionPage[proto.CharacterMugShot]):
    schema = CharacterMugShotSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.CharacterMugShot,
    ) -> dict[str, props.PropertyValue]:
        return {
            "ID": props.Number(data.id),
            "Alpha Channel": props.Checkbox(data.alpha_channel),
            "Animated": props.Checkbox(data.animated),
            "Height": props.Number(data.height),
            "Image ID": props.Text(data.image_id),
            "URL": props.URL(data.url or None),
            "Width": props.Number(data.width),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(str(data.id)),
        }

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.CharacterMugShot,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class CharacterSpecieSchema(uno.Schema, db_title="Character Species"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_characters = PropType.Relation("Related to Characters (Character Species)")


class CharacterSpecie(IGDBNotionPage[proto.CharacterSpecie]):
    schema = CharacterSpecieSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.CharacterSpecie,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals


class CharacterSchema(uno.Schema, db_title="Characters"):
    id = PropType.Number("ID")
    akas = PropType.MultiSelect("AKAs", options=[])
    country_name = PropType.Text("Country Name")
    created_at = PropType.Date("Created At")
    description = PropType.Text("Description")
    games = PropType.Relation("Games", schema=GameSchema)
    mug_shot = PropType.Relation(
        "Mug Shot",
        schema=CharacterMugShotSchema,
        two_way_prop=CharacterMugShotSchema.related_to_characters,
    )
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    character_gender = PropType.Relation(
        "Character Gender",
        schema=CharacterGenderSchema,
        two_way_prop=CharacterGenderSchema.related_to_characters,
    )
    character_species = PropType.Relation(
        "Character Species",
        schema=CharacterSpecieSchema,
        two_way_prop=CharacterSpecieSchema.related_to_characters,
    )


class Character(IGDBNotionPage[proto.Character]):
    schema = CharacterSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Character) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.mug_shot is not None:
            optionals["Mug Shot"] = props.Relations(
                CharacterMugShot.retrieve_or_create_from_data(data.mug_shot)
            )
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        if data.character_gender is not None:
            optionals["Character Gender"] = props.Relations(
                CharacterGender.retrieve_or_create_from_data(data.character_gender)
            )
        if data.character_species is not None:
            optionals["Character Species"] = props.Relations(
                CharacterSpecie.retrieve_or_create_from_data(data.character_species)
            )
        return {
            "ID": props.Number(data.id),
            "AKAs": props.MultiSelect(data.akas),
            "Country Name": props.Text(data.country_name),
            "Description": props.Text(data.description[:MAX_TEXT_LENGTH]),
            "Games": props.Relations(
                [Game.retrieve_or_create_from_data(game) for game in data.games]
            ),
            "Name": props.Title(data.name),
            "Slug": props.Text(data.slug),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"games.{f}" for f in Game.get_query_fields()),
                (f"mug_shot.{f}" for f in CharacterMugShot.get_query_fields()),
                (f"character_gender.{f}" for f in CharacterGender.get_query_fields()),
                (f"character_species.{f}" for f in CharacterSpecie.get_query_fields()),
            )
        )

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.Character,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.mug_shot and data.mug_shot.url:
            icon_url = add_https_scheme(data.mug_shot.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_cover_big_2x/")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class EventLogoSchema(uno.Schema, db_title="Event Logos"):
    id = PropType.Number("ID")
    # events = PropType.Relation("Events", schema=EventSchema)
    alpha_channel = PropType.Checkbox("Alpha Channel")
    animated = PropType.Checkbox("Animated")
    height = PropType.Number("Height")
    image_id = PropType.Text("Image ID")
    url = PropType.URL("URL")
    width = PropType.Number("Width")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_events = PropType.Relation("Related to Events (Event Logo)")


class EventLogo(IGDBNotionPage[proto.EventLogo]):
    schema = EventLogoSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.EventLogo) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Alpha Channel": props.Checkbox(data.alpha_channel),
            "Animated": props.Checkbox(data.animated),
            "Height": props.Number(data.height),
            "Image ID": props.Text(data.image_id),
            "URL": props.URL(data.url or None),
            "Width": props.Number(data.width),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(str(data.id)),
        } | optionals

    @override
    @classmethod
    @functools.lru_cache(maxsize=None, typed=True)  # Edit each page only once per run per data obj
    def retrieve_or_create_from_data(
        cls,
        data: proto.EventLogo,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.url:
            icon_url = add_https_scheme(data.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_original/")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class NetworkTypeSchema(uno.Schema, db_title="Network Types"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    # event_networks = PropType.Relation("Event Networks", schema=EventNetworkSchema)
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_event_networks = PropType.Relation("Related to Event Networks (Network Type)")


class NetworkType(IGDBNotionPage[proto.NetworkType]):
    schema = NetworkTypeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.NetworkType) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals


class EventNetworkSchema(uno.Schema, db_title="Event Networks"):
    id = PropType.Number("ID")
    # event = PropType.Relation("Event", schema=EventSchema)
    url = PropType.URL("URL")
    network_type = PropType.Relation(
        "Network Type",
        schema=NetworkTypeSchema,
        two_way_prop=NetworkTypeSchema.related_to_event_networks,
    )
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    title = PropType.Title("Title")
    related_to_events = PropType.Relation("Related to Events (Event Networks)")


class EventNetwork(IGDBNotionPage[proto.EventNetwork]):
    schema = EventNetworkSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.EventNetwork) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.network_type is not None:
            optionals["Network Type"] = props.Relations(
                NetworkType.retrieve_or_create_from_data(data.network_type)
            )
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(
                (
                    " - ".join(
                        part
                        for part in (
                            data.network_type.name if data.network_type else None,
                            str(data.id),
                        )
                        if part
                    )
                ),
            ),
        } | optionals

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


class EventSchema(uno.Schema, db_title="Events"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    description = PropType.Text("Description")
    slug = PropType.Text("Slug")
    event_logo = PropType.Relation(
        "Event Logo",
        schema=EventLogoSchema,
        two_way_prop=EventLogoSchema.related_to_events,
    )
    start_time = PropType.Date("Start Time")
    time_zone = PropType.Text("Time Zone")
    end_time = PropType.Date("End Time")
    live_stream_url = PropType.URL("Live Stream URL")
    games = PropType.Relation("Games", schema=GameSchema)
    videos = PropType.Relation("Videos", schema=GameVideoSchema)
    event_networks = PropType.Relation(
        "Event Networks",
        schema=EventNetworkSchema,
        two_way_prop=EventNetworkSchema.related_to_events,
    )
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")


class Event(IGDBNotionPage[proto.Event]):
    schema = EventSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Event) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.event_logo is not None:
            optionals["Event Logo"] = props.Relations(
                EventLogo.retrieve_or_create_from_data(data.event_logo)
            )
        if data.start_time is not None:
            optionals["Start Time"] = props.Date(data.start_time.isoformat())
        if data.end_time is not None:
            optionals["End Time"] = props.Date(data.end_time.isoformat())
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Description": props.Text(data.description[:MAX_TEXT_LENGTH]),
            "Slug": props.Text(data.slug),
            "Time Zone": props.Text(data.time_zone),
            "Live Stream URL": props.URL(data.live_stream_url),
            "Games": props.Relations(
                [Game.retrieve_or_create_from_data(game) for game in data.games]
            ),
            "Videos": props.Relations(
                [GameVideo.retrieve_or_create_from_data(vid) for vid in data.videos]
            ),
            "Event Networks": props.Relations(
                [EventNetwork.retrieve_or_create_from_data(n) for n in data.event_networks]
            ),
            "Checksum": props.Text(data.checksum),
        } | optionals

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
        data: proto.Event,
        *,
        icon_url: str | None = None,
        cover_url: str | None = None,
    ) -> uno.Page:
        if not icon_url and data.event_logo and data.event_logo.url:
            icon_url = add_https_scheme(data.event_logo.url)
        if not cover_url and icon_url:
            cover_url = icon_url.replace("/t_thumb/", "/t_original/")

        return super().retrieve_or_create_from_data(data, icon_url=icon_url, cover_url=cover_url)


class PopularityTypeSchema(uno.Schema, db_title="Popularity Types"):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    external_popularity_source = PropType.Relation(
        "External Popularity Source", schema=ExternalGameSourceSchema
    )
    related_to_popularity_primitives = PropType.Relation(
        "Related to Popularity Primitives (Popularity Type)"
    )


class PopularityType(IGDBNotionPage[proto.PopularityType]):
    schema = PopularityTypeSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.PopularityType,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        if data.external_popularity_source is not None:
            optionals["External Popularity Source"] = props.Relations(
                ExternalGameSource.retrieve_or_create_from_data(data.external_popularity_source)
            )
        return {
            "ID": props.Number(data.id),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"external_popularity_source.{f}" for f in ExternalGameSource.get_query_fields()),
            )
        )


class PopularityPrimitiveSchema(uno.Schema, db_title="Popularity Primitives"):
    id = PropType.Number("ID")
    game_id = PropType.Number("Game ID")
    popularity_type = PropType.Relation(
        "Popularity Type",
        schema=PopularityTypeSchema,
        two_way_prop=PopularityTypeSchema.related_to_popularity_primitives,
    )
    value = PropType.Number("Value")
    calculated_at = PropType.Date("Calculated At")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    external_popularity_source = PropType.Relation(
        "External Popularity Source", schema=ExternalGameSourceSchema
    )
    title = PropType.Title("Title")


class PopularityPrimitive(IGDBNotionPage[proto.PopularityPrimitive]):
    schema = PopularityPrimitiveSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(
        data: proto.PopularityPrimitive,
    ) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.popularity_type is not None:
            optionals["Popularity Type"] = props.Relations(
                PopularityType.retrieve_or_create_from_data(data.popularity_type)
            )
        if data.calculated_at is not None:
            optionals["Calculated At"] = props.Date(data.calculated_at.isoformat())
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        if data.external_popularity_source is not None:
            optionals["External Popularity Source"] = props.Relations(
                ExternalGameSource.retrieve_or_create_from_data(data.external_popularity_source)
            )
        return {
            "ID": props.Number(data.id),
            "Game ID": props.Number(data.game_id),
            "Value": props.Number(data.value),
            "Checksum": props.Text(data.checksum),
            "Title": props.Title(
                " - ".join(
                    part.name
                    for part in (data.popularity_type, data.external_popularity_source)
                    if part and part.name
                )
            ),
        } | optionals

    @override
    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return tuple(
            itertools.chain(
                super().get_query_fields(),
                (f"popularity_type.{f}" for f in PopularityType.get_query_fields()),
                (f"external_popularity_source.{f}" for f in ExternalGameSource.get_query_fields()),
            )
        )


class TestDummySchema(uno.Schema, db_title="Test Dummies"):
    id = PropType.Number("ID")
    bool_value = PropType.Checkbox("Bool Value")
    created_at = PropType.Date("Created At")
    enum_test = PropType.Select(
        "Enum Test",
        options=[uno.Option(name) for name in proto.TestDummyEnumTestEnum.__members__],
    )
    float_value = PropType.Number("Float Value")
    game = PropType.Relation("Game", schema=GameSchema)
    integer_array = PropType.Text("Integer Array")  # Stored as a string, needs parsing
    integer_value = PropType.Number("Integer Value")
    name = PropType.Title("Name")
    new_integer_value = PropType.Number("New Integer Value")
    private = PropType.Checkbox("Private")
    slug = PropType.Text("Slug")
    string_array = PropType.Text("String Array")  # Stored as a string, needs parsing
    test_dummies = PropType.Relation("Test Dummies", schema=uno.SelfRef)
    test_dummy = PropType.Relation("Test Dummy", schema=uno.SelfRef)
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")


class TestDummy(IGDBNotionPage[proto.TestDummy]):
    schema = TestDummySchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.TestDummy) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.created_at is not None:
            optionals["Created At"] = props.Date(data.created_at.isoformat())
        if data.game is not None:
            optionals["Game"] = props.Relations(Game.retrieve_or_create_from_data(data.game))
        if data.updated_at is not None:
            optionals["Updated At"] = props.Date(data.updated_at.isoformat())
        return {
            "ID": props.Number(data.id),
            "Bool Value": props.Checkbox(data.bool_value),
            "Enum Test": props.Select(data.enum_test.name or "TESTDUMMY_ENUM_TEST_NULL"),
            "Float Value": props.Number(data.float_value),
            "Integer Array": props.Text(str(data.integer_array)),
            "Integer Value": props.Number(data.integer_value),
            "Name": props.Title(data.name),
            "New Integer Value": props.Number(data.new_integer_value),
            "Private": props.Checkbox(data.private),
            "Slug": props.Text(data.slug),
            "String Array": props.Text(str(data.string_array)),
            "URL": props.URL(data.url or None),
            "Checksum": props.Text(data.checksum),
        } | optionals

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


class SearchSchema(uno.Schema, db_title="Searches"):
    id = PropType.Number("ID")
    alternative_name = PropType.Text("Alternative Name")
    character = PropType.Relation("Character", schema=CharacterSchema)
    collection = PropType.Relation("Collection", schema=CollectionSchema)
    company = PropType.Relation("Company", schema=CompanySchema)
    description = PropType.Text("Description")
    game = PropType.Relation("Game", schema=GameSchema)
    name = PropType.Title("Name")
    platform = PropType.Relation("Platform", schema=PlatformSchema)
    published_at = PropType.Date("Published At")
    test_dummy = PropType.Relation("TestDummy", schema=TestDummySchema)
    theme = PropType.Relation("Theme", schema=ThemeSchema)
    checksum = PropType.Text("Checksum")


class Search(IGDBNotionPage[proto.Search]):
    schema = SearchSchema  # type: ignore[mutable-override]

    @override
    @staticmethod
    def get_populated_properties_dict(data: proto.Search) -> dict[str, props.PropertyValue]:
        optionals: dict[str, props.PropertyValue] = {}
        if data.character is not None:
            optionals["Character"] = props.Relations(
                Character.retrieve_or_create_from_data(data.character)
            )
        if data.collection is not None:
            optionals["Collection"] = props.Relations(
                Collection.retrieve_or_create_from_data(data.collection)
            )
        if data.company is not None:
            optionals["Company"] = props.Relations(
                Company.retrieve_or_create_from_data(data.company)
            )
        if data.game is not None:
            optionals["Game"] = props.Relations(Game.retrieve_or_create_from_data(data.game))
        if data.platform is not None:
            optionals["Platform"] = props.Relations(
                Platform.retrieve_or_create_from_data(data.platform)
            )
        if data.published_at is not None:
            optionals["Published At"] = props.Date(data.published_at.isoformat())
        if data.test_dummy is not None:
            optionals["Test Dummy"] = props.Relations(
                TestDummy.retrieve_or_create_from_data(data.test_dummy)
            )
        if data.theme is not None:
            optionals["Theme"] = props.Relations(Theme.retrieve_or_create_from_data(data.theme))
        return {
            "ID": props.Number(data.id),
            "Alternative Name": props.Text(data.alternative_name),
            "Description": props.Text(data.description[:MAX_TEXT_LENGTH]),
            "Name": props.Title(data.name),
            "Checksum": props.Text(data.checksum),
        } | optionals

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

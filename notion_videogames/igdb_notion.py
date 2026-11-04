# pylint: disable=too-many-lines
from __future__ import annotations

import functools
import logging
import operator
import urllib.parse
from typing import TYPE_CHECKING, Any, ClassVar, Final, NamedTuple, Protocol, override

import ultimate_notion as uno
from ultimate_notion import PropType, props
from ultimate_notion.schema import URL, Date, Relation

from notion_videogames import notion
from notion_videogames.proto import proto

if TYPE_CHECKING:
    from ultimate_notion.schema import Property

logger: logging.Logger = logging.getLogger(__name__)

# https://developers.notion.com/reference/request-limits
MAX_RELATION_PAGES: Final[int] = 100

LOGO_SIZE: Final[str] = "t_logo_med"


def add_https_scheme(url: str) -> str:
    parsed_url = urllib.parse.urlparse(url)

    if parsed_url.scheme:
        # If there's already a scheme, return the original URL
        return url

    # If there's no scheme, add 'https'
    return urllib.parse.urlunparse(("https", *parsed_url[1:]))


def _joined(*parts: str | None) -> str:
    return " - ".join(part for part in parts if part)


def is_unmapped(prop: Property) -> bool:
    """Tell back-references and self-references apart: these are never written or queried."""
    return isinstance(prop, Relation) and (
        prop.attr_name.startswith("related_to_") or prop.is_self_ref
    )


class IGDBMessage(Protocol):
    id: int


class ImageRule(NamedTuple):
    """Where a page's icon and cover come from, and which IGDB image sizes to use for them."""

    url_path: str | None = "url"
    icon_size: str = "t_thumb"
    cover_size: str = "t_cover_big_2x"


class IGDBNotionPage[T: IGDBMessage](notion.NotionPageType[T]):
    """
    A Notion database mirroring an IGDB message.

    Schema attributes are named after message fields, so a schema alone defines both what gets
    written to Notion and what gets queried from IGDB. Subclasses only declare what differs.
    """

    image: ClassVar[ImageRule] = ImageRule(url_path=None)

    @override
    @classmethod
    def get_id(cls, data: T) -> int:
        return data.id

    @staticmethod
    def computed(data: T) -> dict[str, object]:
        """Return values for schema attributes that don't simply read a same-named field."""
        return {"title": str(data.id)}

    @override
    @classmethod
    def get_populated_properties_dict(cls, data: T) -> dict[str, props.PropertyValue]:
        computed = cls.computed(data)
        result: dict[str, props.PropertyValue] = {}

        for prop in cls.schema.get_props():
            if is_unmapped(prop):
                continue

            attr = prop.attr_name
            value: Any = computed[attr] if attr in computed else getattr(data, attr)

            match prop:
                case Relation():
                    if value is not None:
                        result[prop.name] = cls._get_relations(prop, value)
                case Date():
                    if value is not None:
                        result[prop.name] = props.Date(value.isoformat())
                case URL():
                    result[prop.name] = props.URL(value or None)
                case _:
                    result[prop.name] = prop.prop_value(value)

        return result

    @classmethod
    def _get_relations(cls, prop: Relation, value: object) -> props.Relations:
        items = value if isinstance(value, list) else [value]
        if len(items) > MAX_RELATION_PAGES:
            logger.warning(
                "%s.%s has %d relations, keeping the first %d (Notion's limit)",
                cls.__name__,
                prop.attr_name,
                len(items),
                MAX_RELATION_PAGES,
            )

        page_type = _page_type_for(prop.schema)
        return props.Relations(
            [page_type.retrieve_or_create_from_data(item) for item in items[:MAX_RELATION_PAGES]]
        )

    @classmethod
    @functools.cache
    def get_query_fields(cls) -> tuple[str, ...]:
        return (
            "*",
            *(
                f"{prop.attr_name}.{field}"
                for prop in cls.schema.get_props()
                if isinstance(prop, Relation) and not is_unmapped(prop)
                for field in _page_type_for(prop.schema).get_query_fields()
            ),
        )

    @override
    @classmethod
    def get_image_urls(cls, data: T) -> tuple[str | None, str | None]:
        url_path, icon_size, cover_size = cls.image
        try:
            url: str | None = operator.attrgetter(url_path)(data) if url_path else None
        except AttributeError:  # An optional message along the path is missing
            url = None
        if not url:
            return None, None

        url = add_https_scheme(url)
        return url.replace("t_thumb", icon_size), url.replace("t_thumb", cover_size)


@functools.cache
def _page_type_for(schema: type[uno.Schema]) -> type[IGDBNotionPage[Any]]:
    return next(cls for cls in IGDBNotionPage.__subclasses__() if cls.schema is schema)


class AgeRatingOrganizationSchema(uno.Schema):
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


class AgeRatingOrganization(
    IGDBNotionPage[proto.AgeRatingOrganization], schema=AgeRatingOrganizationSchema
): ...


class AgeRatingCategorySchema(uno.Schema):
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


class AgeRatingCategory(
    IGDBNotionPage[proto.AgeRatingCategory], schema=AgeRatingCategorySchema
): ...


class AgeRatingContentDescriptionTypeSchema(uno.Schema):
    id = PropType.Number("ID")
    slug = PropType.Text("Slug")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_age_rating_content_descriptions_v2 = PropType.Relation(
        "Related to Age Rating Content Descriptions V2 (Description Type)"
    )


class AgeRatingContentDescriptionType(
    IGDBNotionPage[proto.AgeRatingContentDescriptionType],
    schema=AgeRatingContentDescriptionTypeSchema,
): ...


class AgeRatingContentDescriptionV2Schema(uno.Schema):
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


class AgeRatingContentDescriptionV2(
    IGDBNotionPage[proto.AgeRatingContentDescriptionV2], schema=AgeRatingContentDescriptionV2Schema
): ...


class AgeRatingSchema(uno.Schema):
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


class AgeRating(IGDBNotionPage[proto.AgeRating], schema=AgeRatingSchema):
    @override
    @staticmethod
    def computed(data: proto.AgeRating) -> dict[str, object]:
        return {
            "title": _joined(
                data.organization.name if data.organization else None,
                data.rating_category.rating if data.rating_category else None,
            )
        }


class AlternativeNameSchema(uno.Schema):
    id = PropType.Number("ID")
    comment = PropType.Text("Comment")
    # game = PropType.Relation("Game", schema=GameSchema)
    name = PropType.Title("Name")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Alternative Names)")


class AlternativeName(IGDBNotionPage[proto.AlternativeName], schema=AlternativeNameSchema): ...


class ArtworkTypeSchema(uno.Schema):
    id = PropType.Number("ID")
    slug = PropType.Text("Slug")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_artworks = PropType.Relation("Related to Artworks (Artwork Type)")


class ArtworkType(IGDBNotionPage[proto.ArtworkType], schema=ArtworkTypeSchema): ...


class ArtworkSchema(uno.Schema):
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


class Artwork(IGDBNotionPage[proto.Artwork], schema=ArtworkSchema):
    image = ImageRule(cover_size="t_1080p")


class CompanyLogoSchema(uno.Schema):
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


class CompanyLogo(IGDBNotionPage[proto.CompanyLogo], schema=CompanyLogoSchema):
    image = ImageRule(icon_size=LOGO_SIZE, cover_size=LOGO_SIZE)


class CompanyStatusSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_companies = PropType.Relation("Related to Companies (Status)")


class CompanyStatus(IGDBNotionPage[proto.CompanyStatus], schema=CompanyStatusSchema): ...


class WebsiteTypeSchema(uno.Schema):
    id = PropType.Number("ID")
    type = PropType.Title("Type")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_company_websites = PropType.Relation("Related to Company Websites (Type)")
    related_to_platform_websites = PropType.Relation("Related to Platform Websites (Type)")
    related_to_websites = PropType.Relation("Related to Websites (Type)")


class WebsiteType(IGDBNotionPage[proto.WebsiteType], schema=WebsiteTypeSchema): ...


class CompanyWebsiteSchema(uno.Schema):
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


class CompanyWebsite(IGDBNotionPage[proto.CompanyWebsite], schema=CompanyWebsiteSchema):
    @override
    @staticmethod
    def computed(data: proto.CompanyWebsite) -> dict[str, object]:
        return {"title": (data.type.type if data.type else None) or data.url or str(data.id)}


class DateFormatSchema(uno.Schema):
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


class DateFormat(IGDBNotionPage[proto.DateFormat], schema=DateFormatSchema): ...


class CompanySchema(uno.Schema):
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


class Company(IGDBNotionPage[proto.Company], schema=CompanySchema):
    image = ImageRule("logo.url", LOGO_SIZE, LOGO_SIZE)


class CoverSchema(uno.Schema):
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


class Cover(IGDBNotionPage[proto.Cover], schema=CoverSchema):
    image = ImageRule()


class ExternalGameSourceSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_external_games = PropType.Relation(
        "Related to External Games (External Game Source)"
    )


class ExternalGameSource(
    IGDBNotionPage[proto.ExternalGameSource], schema=ExternalGameSourceSchema
): ...


class GameReleaseFormatSchema(uno.Schema):
    id = PropType.Number("ID")
    format = PropType.Title("Format")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_external_games = PropType.Relation(
        "Related to External Games (Game Release Format)"
    )


class GameReleaseFormat(
    IGDBNotionPage[proto.GameReleaseFormat], schema=GameReleaseFormatSchema
): ...


class PlatformFamilySchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    checksum = PropType.Text("Checksum")
    related_to_platforms = PropType.Relation("Related to Platforms (Platform Family)")


class PlatformFamily(IGDBNotionPage[proto.PlatformFamily], schema=PlatformFamilySchema): ...


class PlatformLogoSchema(uno.Schema):
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


class PlatformLogo(IGDBNotionPage[proto.PlatformLogo], schema=PlatformLogoSchema):
    image = ImageRule(icon_size=LOGO_SIZE, cover_size=LOGO_SIZE)


class PlatformTypeSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_platforms = PropType.Relation("Related to Platforms (Platform Type)")


class PlatformType(IGDBNotionPage[proto.PlatformType], schema=PlatformTypeSchema): ...


class PlatformVersionCompanySchema(uno.Schema):
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


class PlatformVersionCompany(
    IGDBNotionPage[proto.PlatformVersionCompany], schema=PlatformVersionCompanySchema
):
    @override
    @staticmethod
    def computed(data: proto.PlatformVersionCompany) -> dict[str, object]:
        return {"title": _joined(data.company.name if data.company else None, str(data.id))}


class ReleaseDateRegionSchema(uno.Schema):
    id = PropType.Number("ID")
    region = PropType.Title("Region")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_platform_version_release_dates = PropType.Relation(
        "Related to Platform Version Release Dates (Release Region)"
    )
    related_to_release_dates = PropType.Relation("Related to Release Dates (Release Region)")


class ReleaseDateRegion(
    IGDBNotionPage[proto.ReleaseDateRegion], schema=ReleaseDateRegionSchema
): ...


class PlatformVersionReleaseDateSchema(uno.Schema):
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


class PlatformVersionReleaseDate(
    IGDBNotionPage[proto.PlatformVersionReleaseDate], schema=PlatformVersionReleaseDateSchema
):
    @override
    @staticmethod
    def computed(data: proto.PlatformVersionReleaseDate) -> dict[str, object]:
        return {"title": f"{data.y}/{data.m}"}


class PlatformVersionSchema(uno.Schema):
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
    platform_version_release_dates = PropType.Relation(
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


class PlatformVersion(IGDBNotionPage[proto.PlatformVersion], schema=PlatformVersionSchema):
    image = ImageRule("platform_logo.url", LOGO_SIZE, LOGO_SIZE)


class PlatformWebsiteSchema(uno.Schema):
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


class PlatformWebsite(IGDBNotionPage[proto.PlatformWebsite], schema=PlatformWebsiteSchema):
    @override
    @staticmethod
    def computed(data: proto.PlatformWebsite) -> dict[str, object]:
        return {"title": (data.type.type if data.type else None) or data.url or str(data.id)}


class PlatformSchema(uno.Schema):
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


class Platform(IGDBNotionPage[proto.Platform], schema=PlatformSchema):
    image = ImageRule("platform_logo.url", LOGO_SIZE, LOGO_SIZE)


class ExternalGameSchema(uno.Schema):
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


class ExternalGame(IGDBNotionPage[proto.ExternalGame], schema=ExternalGameSchema): ...


class FranchiseSchema(uno.Schema):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    # games = PropType.Relation("Games", schema=GameSchema)
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Franchises)")


class Franchise(IGDBNotionPage[proto.Franchise], schema=FranchiseSchema): ...


class GameEngineLogoSchema(uno.Schema):
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


class GameEngineLogo(IGDBNotionPage[proto.GameEngineLogo], schema=GameEngineLogoSchema):
    image = ImageRule()


class GameEngineSchema(uno.Schema):
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


class GameEngine(IGDBNotionPage[proto.GameEngine], schema=GameEngineSchema):
    image = ImageRule("logo.url")


class RegionSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    category = PropType.Text("Category")
    identifier = PropType.Text("Identifier")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_game_localizations = PropType.Relation("Related to Game Localizations (Region)")


class Region(IGDBNotionPage[proto.Region], schema=RegionSchema): ...


class GameLocalizationSchema(uno.Schema):
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


class GameLocalization(IGDBNotionPage[proto.GameLocalization], schema=GameLocalizationSchema):
    image = ImageRule("cover.url")


class GameModeSchema(uno.Schema):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Game Modes)")


class GameMode(IGDBNotionPage[proto.GameMode], schema=GameModeSchema): ...


class GameStatusSchema(uno.Schema):
    id = PropType.Number("ID")
    status = PropType.Title("Status")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Game Status)")


class GameStatus(IGDBNotionPage[proto.GameStatus], schema=GameStatusSchema): ...


class GameTypeSchema(uno.Schema):
    id = PropType.Number("ID")
    type = PropType.Title("Type")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Game Type)")


class GameType(IGDBNotionPage[proto.GameType], schema=GameTypeSchema): ...


class GameVideoSchema(uno.Schema):
    id = PropType.Number("ID")
    # game = PropType.Relation("Game", schema=GameSchema)
    name = PropType.Title("Name")
    video_id = PropType.Text("Video ID")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Videos)")


class GameVideo(IGDBNotionPage[proto.GameVideo], schema=GameVideoSchema): ...


class GenreSchema(uno.Schema):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Genres)")


class Genre(IGDBNotionPage[proto.Genre], schema=GenreSchema): ...


class InvolvedCompanySchema(uno.Schema):
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


class InvolvedCompany(IGDBNotionPage[proto.InvolvedCompany], schema=InvolvedCompanySchema):
    image = ImageRule("company.logo.url", LOGO_SIZE, LOGO_SIZE)

    @override
    @staticmethod
    def computed(data: proto.InvolvedCompany) -> dict[str, object]:
        return {"title": (data.company.name if data.company else None) or str(data.id)}


class KeywordSchema(uno.Schema):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Keywords)")


class Keyword(IGDBNotionPage[proto.Keyword], schema=KeywordSchema): ...


class LanguageSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    native_name = PropType.Text("Native Name")
    locale = PropType.Text("Locale")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_language_supports = PropType.Relation("Related to Language Supports (Language)")


class Language(IGDBNotionPage[proto.Language], schema=LanguageSchema): ...


class LanguageSupportTypeSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_language_supports = PropType.Relation(
        "Related to Language Supports (Language Support Type)"
    )


class LanguageSupportType(
    IGDBNotionPage[proto.LanguageSupportType], schema=LanguageSupportTypeSchema
): ...


class LanguageSupportSchema(uno.Schema):
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


class LanguageSupport(IGDBNotionPage[proto.LanguageSupport], schema=LanguageSupportSchema):
    @override
    @staticmethod
    def computed(data: proto.LanguageSupport) -> dict[str, object]:
        return {
            "title": _joined(
                data.language.name if data.language else None,
                data.language_support_type.name if data.language_support_type else None,
            )
        }


class MultiplayerModeSchema(uno.Schema):
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


class MultiplayerMode(IGDBNotionPage[proto.MultiplayerMode], schema=MultiplayerModeSchema):
    @override
    @staticmethod
    def computed(data: proto.MultiplayerMode) -> dict[str, object]:
        return {"title": _joined(data.platform.name if data.platform else None, str(data.id))}


class PlayerPerspectiveSchema(uno.Schema):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Player Perspectives)")


class PlayerPerspective(
    IGDBNotionPage[proto.PlayerPerspective], schema=PlayerPerspectiveSchema
): ...


class ReleaseDateStatusSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    description = PropType.Text("Description")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_release_dates = PropType.Relation("Related to Release Dates (Status)")


class ReleaseDateStatus(
    IGDBNotionPage[proto.ReleaseDateStatus], schema=ReleaseDateStatusSchema
): ...


class ReleaseDateSchema(uno.Schema):
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


class ReleaseDate(IGDBNotionPage[proto.ReleaseDate], schema=ReleaseDateSchema):
    @override
    @staticmethod
    def computed(data: proto.ReleaseDate) -> dict[str, object]:
        return {
            "title": _joined(data.platform.name if data.platform else None, f"{data.y}/{data.m}")
        }


class ScreenshotSchema(uno.Schema):
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


class Screenshot(IGDBNotionPage[proto.Screenshot], schema=ScreenshotSchema):
    image = ImageRule(cover_size="t_1080p")


class ThemeSchema(uno.Schema):
    id = PropType.Number("ID")
    created_at = PropType.Date("Created At")
    name = PropType.Title("Name")
    slug = PropType.Text("Slug")
    updated_at = PropType.Date("Updated At")
    url = PropType.URL("URL")
    checksum = PropType.Text("Checksum")
    related_to_igdb_games = PropType.Relation("Related to IGDB Games (Themes)")


class Theme(IGDBNotionPage[proto.Theme], schema=ThemeSchema): ...


class WebsiteSchema(uno.Schema):
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


class Website(IGDBNotionPage[proto.Website], schema=WebsiteSchema):
    @override
    @staticmethod
    def computed(data: proto.Website) -> dict[str, object]:
        return {"title": (data.type.type if data.type else None) or data.url or str(data.id)}


class GameSchema(uno.Schema):
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


class Game(IGDBNotionPage[proto.Game], schema=GameSchema):
    image = ImageRule("cover.url")


class CollectionTypeSchema(uno.Schema):
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


class CollectionType(IGDBNotionPage[proto.CollectionType], schema=CollectionTypeSchema): ...


class CollectionSchema(uno.Schema):
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


class Collection(IGDBNotionPage[proto.Collection], schema=CollectionSchema): ...


class CollectionMembershipTypeSchema(uno.Schema):
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


class CollectionMembershipType(
    IGDBNotionPage[proto.CollectionMembershipType], schema=CollectionMembershipTypeSchema
): ...


class CollectionMembershipSchema(uno.Schema):
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


class CollectionMembership(
    IGDBNotionPage[proto.CollectionMembership], schema=CollectionMembershipSchema
):
    @override
    @staticmethod
    def computed(data: proto.CollectionMembership) -> dict[str, object]:
        return {
            "title": _joined(
                data.game.name if data.game else None,
                data.collection.name if data.collection else None,
                data.type.name if data.type else None,
            )
        }


class CollectionRelationTypeSchema(uno.Schema):
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


class CollectionRelationType(
    IGDBNotionPage[proto.CollectionRelationType], schema=CollectionRelationTypeSchema
): ...


class CollectionRelationSchema(uno.Schema):
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


class CollectionRelation(
    IGDBNotionPage[proto.CollectionRelation], schema=CollectionRelationSchema
):
    @override
    @staticmethod
    def computed(data: proto.CollectionRelation) -> dict[str, object]:
        return {
            "title": _joined(
                data.parent_collection.name if data.parent_collection else None,
                data.child_collection.name if data.child_collection else None,
                data.type.name if data.type else None,
            )
        }


class GameTimeToBeatSchema(uno.Schema):
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


class GameTimeToBeat(IGDBNotionPage[proto.GameTimeToBeat], schema=GameTimeToBeatSchema): ...


class GameVersionFeatureValueSchema(uno.Schema):
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


class GameVersionFeatureValue(
    IGDBNotionPage[proto.GameVersionFeatureValue], schema=GameVersionFeatureValueSchema
):
    @override
    @staticmethod
    def computed(data: proto.GameVersionFeatureValue) -> dict[str, object]:
        return {
            "title": _joined(
                data.game.name if data.game else None,
                data.included_feature.name if data.included_feature else None,
            ),
            "included_feature": data.included_feature.name or "",
        }


class GameVersionFeatureSchema(uno.Schema):
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


class GameVersionFeature(
    IGDBNotionPage[proto.GameVersionFeature], schema=GameVersionFeatureSchema
):
    @override
    @staticmethod
    def computed(data: proto.GameVersionFeature) -> dict[str, object]:
        return {"category": data.category.name or ""}


class GameVersionSchema(uno.Schema):
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


class GameVersion(IGDBNotionPage[proto.GameVersion], schema=GameVersionSchema): ...


class CharacterGenderSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_characters = PropType.Relation("Related to Characters (Character Gender)")


class CharacterGender(IGDBNotionPage[proto.CharacterGender], schema=CharacterGenderSchema): ...


class CharacterMugShotSchema(uno.Schema):
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


class CharacterMugShot(IGDBNotionPage[proto.CharacterMugShot], schema=CharacterMugShotSchema):
    image = ImageRule()


class CharacterSpecieSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_characters = PropType.Relation("Related to Characters (Character Species)")


class CharacterSpecie(IGDBNotionPage[proto.CharacterSpecie], schema=CharacterSpecieSchema): ...


class CharacterSchema(uno.Schema):
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


class Character(IGDBNotionPage[proto.Character], schema=CharacterSchema):
    image = ImageRule("mug_shot.url")


class EventLogoSchema(uno.Schema):
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


class EventLogo(IGDBNotionPage[proto.EventLogo], schema=EventLogoSchema):
    image = ImageRule(cover_size="t_original")


class NetworkTypeSchema(uno.Schema):
    id = PropType.Number("ID")
    name = PropType.Title("Name")
    # event_networks = PropType.Relation("Event Networks", schema=EventNetworkSchema)
    created_at = PropType.Date("Created At")
    updated_at = PropType.Date("Updated At")
    checksum = PropType.Text("Checksum")
    related_to_event_networks = PropType.Relation("Related to Event Networks (Network Type)")


class NetworkType(IGDBNotionPage[proto.NetworkType], schema=NetworkTypeSchema): ...


class EventNetworkSchema(uno.Schema):
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


class EventNetwork(IGDBNotionPage[proto.EventNetwork], schema=EventNetworkSchema):
    @override
    @staticmethod
    def computed(data: proto.EventNetwork) -> dict[str, object]:
        return {
            "title": _joined(data.network_type.name if data.network_type else None, str(data.id))
        }


class EventSchema(uno.Schema):
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


class Event(IGDBNotionPage[proto.Event], schema=EventSchema):
    image = ImageRule("event_logo.url", cover_size="t_original")


class PopularityTypeSchema(uno.Schema):
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


class PopularityType(IGDBNotionPage[proto.PopularityType], schema=PopularityTypeSchema): ...


class PopularityPrimitiveSchema(uno.Schema):
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


class PopularityPrimitive(
    IGDBNotionPage[proto.PopularityPrimitive], schema=PopularityPrimitiveSchema
):
    @override
    @staticmethod
    def computed(data: proto.PopularityPrimitive) -> dict[str, object]:
        return {
            "title": _joined(
                *(
                    part.name
                    for part in (data.popularity_type, data.external_popularity_source)
                    if part
                )
            )
        }


class TestDummySchema(uno.Schema):
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


class TestDummy(IGDBNotionPage[proto.TestDummy], schema=TestDummySchema):
    @override
    @staticmethod
    def computed(data: proto.TestDummy) -> dict[str, object]:
        return {
            "enum_test": data.enum_test.name or "TESTDUMMY_ENUM_TEST_NULL",
            "integer_array": str(data.integer_array),
            "string_array": str(data.string_array),
        }


class SearchSchema(uno.Schema):
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


class Search(IGDBNotionPage[proto.Search], schema=SearchSchema): ...

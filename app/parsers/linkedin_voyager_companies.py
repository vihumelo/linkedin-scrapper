"""Extracts companies from LinkedIn Voyager company search responses."""

import re
from dataclasses import dataclass

from app.core.json_types import JSONValue
from app.schemas.companies import CompanyListing

COMPANY_URN_PATTERN = re.compile(r"urn:li:fsd_company:([0-9]+)")
ENTITY_RESULT_TYPE_SUFFIX = ".EntityResultViewModel"


class CompanySearchStructureError(ValueError):
    """Indicates that a Voyager response does not contain recognized company search results."""


@dataclass(frozen=True)
class CompanySearchPage:
    """Companies found on one results page and LinkedIn's paging metadata."""

    companies: list[CompanyListing]
    total: int | None
    page_size: int | None


def parse_company_search_voyager(payload: dict[str, JSONValue]) -> CompanySearchPage:
    """Maps a normalized Voyager search response to companies in LinkedIn's ranking order."""

    collection = _search_collection(payload)
    elements = collection.get("elements")
    if not isinstance(elements, list):
        raise CompanySearchStructureError("The Voyager search response has no result elements.")
    included = payload.get("included", [])
    if not isinstance(included, list):
        raise CompanySearchStructureError("The Voyager search response has invalid entities.")

    entities = _entity_results_by_urn(included)
    companies: list[CompanyListing] = []
    seen_ids: set[str] = set()
    for reference in _entity_result_references(elements):
        entity = entities.get(reference)
        company = _company(entity) if entity is not None else None
        if company is not None and company.id not in seen_ids:
            seen_ids.add(company.id)
            companies.append(company)

    paging = collection.get("paging")
    paging_data = paging if isinstance(paging, dict) else {}
    return CompanySearchPage(
        companies=companies,
        total=_optional_int(paging_data.get("total")),
        page_size=_optional_int(paging_data.get("count")),
    )


def _search_collection(payload: dict[str, JSONValue]) -> dict[str, JSONValue]:
    """Returns the search collection nested under the GraphQL data envelope."""

    data = payload.get("data")
    inner = data.get("data") if isinstance(data, dict) else None
    collection = inner.get("searchDashClustersByAll") if isinstance(inner, dict) else None
    if not isinstance(collection, dict):
        raise CompanySearchStructureError("The Voyager response does not contain search results.")
    return collection


def _entity_results_by_urn(included: list[JSONValue]) -> dict[str, dict[str, JSONValue]]:
    """Indexes the included search result entities by their entity URN."""

    entities: dict[str, dict[str, JSONValue]] = {}
    for entity in included:
        if not isinstance(entity, dict):
            continue
        entity_type = entity.get("$type")
        urn = entity.get("entityUrn")
        if (
            isinstance(entity_type, str)
            and entity_type.endswith(ENTITY_RESULT_TYPE_SUFFIX)
            and isinstance(urn, str)
        ):
            entities[urn] = entity
    return entities


def _entity_result_references(elements: list[JSONValue]) -> list[str]:
    """Lists the entity result URNs referenced by the result clusters, in display order."""

    references: list[str] = []
    for element in elements:
        items = element.get("items") if isinstance(element, dict) else None
        if not isinstance(items, list):
            continue
        for item in items:
            content = item.get("item") if isinstance(item, dict) else None
            reference = content.get("*entityResult") if isinstance(content, dict) else None
            if isinstance(reference, str):
                references.append(reference)
    return references


def _company(entity: dict[str, JSONValue]) -> CompanyListing | None:
    """Builds a company from a search result entity, or returns None for other entity kinds."""

    urn = entity.get("entityUrn")
    match = COMPANY_URN_PATTERN.search(urn) if isinstance(urn, str) else None
    if match is None:
        return None
    return CompanyListing(
        id=match.group(1),
        name=_text_view(entity.get("title")),
        industry_location=_text_view(entity.get("primarySubtitle")),
        followers=_text_view(entity.get("secondarySubtitle")),
        url=_optional_text(entity.get("navigationUrl")),
    )


def _text_view(value: JSONValue | None) -> str | None:
    """Returns the trimmed text of a Voyager text view model."""

    return _optional_text(value.get("text")) if isinstance(value, dict) else None


def _optional_text(value: JSONValue | None) -> str | None:
    """Returns a trimmed non-empty string for an optional Voyager field."""

    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _optional_int(value: JSONValue | None) -> int | None:
    """Returns an integer paging value, ignoring booleans and other types."""

    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value

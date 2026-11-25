"""Tests for extracting companies from Voyager company search responses."""

import json
from pathlib import Path

import pytest

from app.core.json_types import JSONValue, normalize_json_value
from app.parsers.linkedin_voyager_companies import (
    CompanySearchStructureError,
    parse_company_search_voyager,
)

FIXTURES = Path(__file__).parent / "fixtures"
ENTITY_RESULT_TYPE = "com.linkedin.voyager.dash.search.EntityResultViewModel"


def load_fixture(name: str) -> dict[str, JSONValue]:
    """Loads a sanitized real Voyager response as a typed JSON object."""

    payload = normalize_json_value(json.loads((FIXTURES / name).read_text(encoding="utf-8")))
    assert isinstance(payload, dict)
    return payload


def search_payload(
    references: list[str],
    included: list[JSONValue],
    paging: JSONValue = None,
) -> dict[str, JSONValue]:
    """Builds a minimal Voyager search response referencing the given entity results."""

    collection: dict[str, JSONValue] = {
        "elements": [{"items": [{"item": {"*entityResult": urn}} for urn in references]}],
    }
    if paging is not None:
        collection["paging"] = paging
    return {"data": {"data": {"searchDashClustersByAll": collection}}, "included": included}


def entity_result(urn: str, title: str) -> dict[str, JSONValue]:
    """Builds an included search result entity."""

    return {"$type": ENTITY_RESULT_TYPE, "entityUrn": urn, "title": {"text": title}}


def test_parses_real_results_in_linkedin_ranking_order() -> None:
    """Returns every company from the real response, ordered by the result clusters."""

    page = parse_company_search_voyager(load_fixture("linkedin_company_search_voyager.json"))

    assert [company.id for company in page.companies] == [
        "10248363",
        "10313599",
        "90398486",
        "26668212",
        "18882089",
        "137085",
        "598372",
        "101067576",
        "14531560",
        "68193728",
    ]
    assert page.total == 1000
    assert page.page_size == 10
    first = page.companies[0]
    assert first.name == "Corporate Rebels"
    assert first.industry_location == "Research Services • Eindhoven, North Brabant"
    assert first.followers == "216K followers"
    assert first.url == (
        "https://www.linkedin.com/company/corporate-rebels---the-search-for-the-happy-grail/"
    )


def test_keeps_result_tracked_as_organization_with_text_as_provided() -> None:
    """Reads the ID from the entity URN and keeps a single-part subtitle unchanged."""

    page = parse_company_search_voyager(load_fixture("linkedin_company_search_voyager.json"))

    company = next(item for item in page.companies if item.id == "10313599")
    assert company.name == "Corporate Finance Institute® (CFI)"
    assert company.industry_location == "Vancouver, British Columbia"
    assert company.followers is None


def test_parses_real_empty_result() -> None:
    """Returns no companies and a zero total for a search without matches."""

    page = parse_company_search_voyager(load_fixture("linkedin_company_search_voyager_empty.json"))

    assert page.companies == []
    assert page.total == 0
    assert page.page_size == 10


def test_skips_non_company_results_duplicates_and_unresolved_references() -> None:
    """Keeps only distinct companies whose referenced entity is included."""

    company_urn = "urn:li:fsd_entityResultViewModel:(urn:li:fsd_company:1,SEARCH_SRP,DEFAULT)"
    profile_urn = "urn:li:fsd_entityResultViewModel:(urn:li:fsd_profile:ABC,SEARCH_SRP,DEFAULT)"
    payload = search_payload(
        [profile_urn, company_urn, company_urn, "urn:li:fsd_entityResultViewModel:missing"],
        [entity_result(profile_urn, "Person"), entity_result(company_urn, "Company One")],
    )

    page = parse_company_search_voyager(payload)

    assert [(company.id, company.name) for company in page.companies] == [("1", "Company One")]


def test_reports_unknown_paging_as_none() -> None:
    """Leaves the total and page size unknown when LinkedIn sends no usable paging data."""

    page = parse_company_search_voyager(search_payload([], [], paging={"total": True}))

    assert page.total is None
    assert page.page_size is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": {"status": 500}},
        {"data": {"data": {"searchDashClustersByAll": {"elements": {}}}}},
        {"data": {"data": {"searchDashClustersByAll": {"elements": []}}}, "included": {}},
    ],
)
def test_rejects_unrecognized_structure(payload: dict[str, JSONValue]) -> None:
    """Fails explicitly when the search collection, results, or entities are malformed."""

    with pytest.raises(CompanySearchStructureError):
        parse_company_search_voyager(payload)

"""Extracts job detail fields from LinkedIn Voyager JSON responses."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from app.schemas.jobs import JobDetail


class JobDetailVoyagerStructureError(ValueError):
    """Indicates that a Voyager response does not contain recognized job details."""


def parse_job_detail_voyager(payload: dict[str, Any], job_id: str) -> JobDetail:
    """Maps a normalized Voyager response to the job detail model."""

    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise JobDetailVoyagerStructureError("A resposta Voyager não contém dados da vaga.")

    title = _find_text(data, ("title", "localizedTitle", "formattedTitle"))
    description = _find_text(
        data,
        ("localizedDescription", "descriptionText", "description", "jobDescription"),
    )
    if title is None and description is None:
        raise JobDetailVoyagerStructureError(
            "A resposta Voyager não contém campos reconhecidos de uma vaga."
        )

    company = _find_text(data, ("companyName", "employerName"))
    if company is None:
        company = _company_from_details(data, payload.get("included"))
    formatted_seniority = _find_text(data, ("formattedExperienceLevel",))
    formatted_employment_type = _find_text(data, ("formattedEmploymentStatus",))
    seniority_level = formatted_seniority or _format_enum(
        _find_text(data, ("seniorityLevel", "formattedSeniorityLevel"))
    )
    employment_type = formatted_employment_type or _format_enum(
        _find_text(data, ("employmentType", "employmentStatus"))
    )

    return JobDetail(
        id=job_id,
        title=title,
        company=company,
        location=_find_text(data, ("formattedLocation", "locationName", "location")),
        url=f"https://www.linkedin.com/jobs/view/{job_id}/",
        posted=_posted(data),
        seniority_level=seniority_level,
        employment_type=employment_type,
        workplace_type=_workplace_type(data, payload.get("included")),
        industry=_find_text(data, ("industryName", "industriesText", "industry"))
        or _industry_from_company(data, payload.get("included")),
        description_text=description,
    )


def _workplace_type(data: dict[str, Any], included: object) -> str | None:
    """Resolves workplace type URNs to their localized labels."""

    direct = _find_text(data, ("formattedWorkplaceType",))
    if direct is not None:
        return direct
    if not isinstance(included, list):
        return None

    workplace_urns = (
        {value for value in data.get("workplaceTypes", []) if isinstance(value, str)}
        if isinstance(data.get("workplaceTypes"), list)
        else set()
    )
    resolutions = data.get("workplaceTypesResolutionResults")
    if isinstance(resolutions, dict):
        workplace_urns.update(value for value in resolutions.values() if isinstance(value, str))

    labels = []
    for entity in included:
        if not isinstance(entity, dict):
            continue
        if "WorkplaceType" not in entity.get("$type", ""):
            continue
        if entity.get("entityUrn") not in workplace_urns:
            continue
        label = _find_text(entity, ("localizedName", "name"))
        if label and label not in labels:
            labels.append(label)
    return ", ".join(labels) or None


def _company_from_details(data: dict[str, Any], included: object) -> str | None:
    """Resolves a company reference through the Voyager included entities when possible."""

    details = data.get("companyDetails")
    if isinstance(details, dict):
        direct_name = _find_text(details, ("companyName", "localizedName", "name"))
        if direct_name is not None:
            return direct_name
        entity = _resolved_company_entity(data, included)
        if entity is not None:
            name = _find_text(entity, ("name", "localizedName", "companyName"))
            if name is not None:
                return name

    company = _find_text(data, ("companyName", "employer"))
    if company is not None and company.startswith("urn:li:"):
        return None
    return company


def _industry_from_company(data: dict[str, Any], included: object) -> str | None:
    """Reads industry labels from the company entity referenced by the posting."""

    entity = _resolved_company_entity(data, included)
    if entity is None:
        return None
    industries = entity.get("industries")
    if isinstance(industries, str):
        return _text_value(industries)
    if isinstance(industries, list):
        labels = list(dict.fromkeys(filter(None, (_text_value(item) for item in industries))))
        return ", ".join(labels) or None
    return None


def _resolved_company_entity(data: dict[str, Any], included: object) -> dict[str, Any] | None:
    """Finds the included company entity referenced by company details."""

    details = data.get("companyDetails")
    if not isinstance(details, dict) or not isinstance(included, list):
        return None
    references = {
        value for value in _walk(details) if isinstance(value, str) and value.startswith("urn:li:")
    }
    for entity in included:
        if not isinstance(entity, dict):
            continue
        entity_values = {value for value in _walk(entity) if isinstance(value, str)}
        if references.intersection(entity_values):
            return entity
    return None


def _find_text(source: object, keys: tuple[str, ...]) -> str | None:
    """Finds a non-empty text field by trying the supplied key priority in nested data."""

    for key in keys:
        for value in _walk(source):
            if isinstance(value, dict) and key in value:
                text = _text_value(value[key])
                if text:
                    return text
    return None


def _text_value(value: object) -> str | None:
    """Extracts readable text from Voyager strings and nested text objects."""

    if isinstance(value, str):
        text = " ".join(value.split())
        return text or None
    if isinstance(value, dict):
        for key in ("text", "localizedText", "content", "value", "plainText"):
            if key in value:
                if text := _text_value(value[key]):
                    return text
    if isinstance(value, list):
        parts = [part for item in value if (part := _text_value(item))]
        if parts:
            return " ".join(parts)
    return None


def _walk(value: object) -> Iterator[object]:
    """Yields nested mapping and list values for normalized Voyager payloads."""

    yield value
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def _format_enum(value: str | None) -> str | None:
    """Turns Voyager enum URNs into readable labels while retaining unknown values."""

    if value is None:
        return None
    enum_value = value.rsplit(":", maxsplit=1)[-1]
    known_values = {
        "FULL_TIME": "Full-time",
        "PART_TIME": "Part-time",
        "CONTRACT": "Contract",
        "TEMPORARY": "Temporary",
        "INTERNSHIP": "Internship",
        "VOLUNTEER": "Volunteer",
        "OTHER": "Other",
    }
    if enum_value in known_values:
        return known_values[enum_value]
    return enum_value.replace("_", " ").title()


def _posted(data: dict[str, Any]) -> str | None:
    """Converts Voyager's millisecond timestamp to an ISO 8601 UTC string."""

    for key in ("listedAt", "originalListedAt"):
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                return datetime.fromtimestamp(value / 1000, tz=UTC).isoformat()
            except (OverflowError, OSError, ValueError):
                continue
    return None

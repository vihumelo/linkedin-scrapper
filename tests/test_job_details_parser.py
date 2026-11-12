"""Tests for extracting details from LinkedIn Voyager JSON."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.parsers.linkedin_voyager_job_details import (
    JobDetailVoyagerStructureError,
    parse_job_detail_voyager,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "linkedin_job_detail_voyager.json"


def test_parse_voyager_job_detail_fixture() -> None:
    """Parses the complete sanitized Voyager response while preserving its structure."""

    fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")
    payload = json.loads(fixture_text)
    job = parse_job_detail_voyager(payload, "1234567890")

    assert len(payload) == 2
    assert len(payload["data"]) >= 70
    assert len(payload["included"]) == 8
    assert "4486249045" not in fixture_text
    assert "[NOME REDIGIDO]" in fixture_text
    assert "https://" not in fixture_text
    assert job.id == "1234567890"
    assert job.title == "Técnico em Engenharia Clinica"
    assert job.company == "[EMPRESA REDIGIDA]"
    assert job.location == "São Paulo, Brazil"
    assert job.posted == datetime.fromtimestamp(1793968839, UTC).isoformat()
    assert job.seniority_level is None
    assert job.employment_type == payload["data"]["formattedEmploymentStatus"]
    assert job.industry == "Hospitals and Health Care"
    assert job.workplace_type == "On-site"
    assert job.description_text is not None
    assert "[NOME REDIGIDO]" in job.description_text


def test_rejects_voyager_payload_without_recognized_job_fields() -> None:
    """Rejects payloads that contain no title or description."""

    with pytest.raises(JobDetailVoyagerStructureError):
        parse_job_detail_voyager({"data": {"formattedPostedAt": "Posted yesterday"}}, "123")


def test_accepts_title_when_optional_fields_are_missing() -> None:
    """Keeps optional fields null for a recognized job with only a title."""

    job = parse_job_detail_voyager({"data": {"title": "Vaga reconhecida"}}, "123")

    assert job.title == "Vaga reconhecida"
    assert job.company is None
    assert job.location is None
    assert job.description_text is None


def test_rejects_non_object_data() -> None:
    """Rejects malformed response data before attempting to extract fields."""

    with pytest.raises(JobDetailVoyagerStructureError):
        parse_job_detail_voyager({"data": []}, "123")

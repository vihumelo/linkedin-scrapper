"""Tests for the cache policy in the job details service."""

import asyncio

import pytest

from app.ports.job_cache import JobCacheError
from app.schemas.jobs import JobDetail
from app.services.job_details import JobDetailService

JOB_ID = "4486249045"
COMPLETE_JOB_PAYLOAD = {
    "data": {
        "title": "Técnico em Engenharia Clínica",
        "companyDetails": {"companyName": "Empresa Exemplo"},
        "formattedLocation": "São Paulo, Brasil",
        "localizedDescription": "Descrição completa da vaga.",
    }
}
INCOMPLETE_JOB_PAYLOAD = {"data": {"title": "Vaga sem detalhes suficientes"}}


def make_job(**overrides: str | None) -> JobDetail:
    """Builds a complete job for service tests."""

    fields: dict[str, str | None] = {
        "id": JOB_ID,
        "title": "Técnico em Engenharia Clínica",
        "company": "Empresa Exemplo",
        "location": "São Paulo, Brasil",
        "url": f"https://www.linkedin.com/jobs/view/{JOB_ID}/",
        "description_text": "Descrição completa da vaga.",
    }
    fields.update(overrides)
    return JobDetail(**fields)


class FakeAuthenticatedClient:
    """Fake authenticated client that counts Voyager requests."""

    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload or COMPLETE_JOB_PAYLOAD
        self.requested_ids: list[str] = []

    async def get_job_details(self, job_id: str) -> dict[str, object]:
        """Returns static Voyager JSON and records the queried ID."""

        self.requested_ids.append(job_id)
        return self.payload


class FakeJobCache:
    """Fake cache with controlled failures for testing the service policy."""

    def __init__(self, cached_job: JobDetail | None = None) -> None:
        self.cached_job = cached_job
        self.get_error: Exception | None = None
        self.save_error: Exception | None = None
        self.get_calls: list[str] = []
        self.saved_jobs: list[JobDetail] = []

    async def get(self, job_id: str) -> JobDetail | None:
        """Returns the configured value or simulates a read failure."""

        self.get_calls.append(job_id)
        if self.get_error:
            raise self.get_error
        return self.cached_job

    async def save(self, job: JobDetail) -> None:
        """Records the job or simulates a write failure."""

        if self.save_error:
            raise self.save_error
        self.saved_jobs.append(job)

    async def delete(self, job_id: str) -> None:
        """Removes the fake job when its stored ID matches."""

        if self.cached_job and self.cached_job.id == job_id:
            self.cached_job = None


def test_returns_cached_job_without_calling_linkedin() -> None:
    """Returns the stored details and avoids an external request on a cache hit."""

    client = FakeAuthenticatedClient()
    cache = FakeJobCache(make_job())

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job == cache.cached_job
    assert client.requested_ids == []


def test_fetches_and_caches_complete_job_on_cache_miss() -> None:
    """Queries LinkedIn and stores complete details when the cache is empty."""

    client = FakeAuthenticatedClient()
    cache = FakeJobCache()

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job.id == JOB_ID
    assert client.requested_ids == [JOB_ID]
    assert cache.saved_jobs == [response.job]


def test_cache_read_failure_falls_back_to_linkedin() -> None:
    """Fetches the job from LinkedIn when reading the cache fails."""

    client = FakeAuthenticatedClient()
    cache = FakeJobCache()
    cache.get_error = JobCacheError("cache indisponível")

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job.id == JOB_ID
    assert client.requested_ids == [JOB_ID]
    assert cache.saved_jobs == [response.job]


def test_incomplete_cached_job_falls_back_to_linkedin() -> None:
    """Does not return incomplete records already present in the database."""

    client = FakeAuthenticatedClient()
    cache = FakeJobCache(make_job(description_text=None))

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job.description_text == "Descrição completa da vaga."
    assert client.requested_ids == [JOB_ID]
    assert cache.saved_jobs == [response.job]


def test_cache_write_failure_does_not_discard_linkedin_response() -> None:
    """Returns LinkedIn details even when they cannot be written to the cache."""

    client = FakeAuthenticatedClient()
    cache = FakeJobCache()
    cache.save_error = JobCacheError("cache indisponível")

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job.id == JOB_ID
    assert client.requested_ids == [JOB_ID]


def test_does_not_cache_title_only_job() -> None:
    """Does not cache the job if any required cache field is missing."""

    client = FakeAuthenticatedClient(INCOMPLETE_JOB_PAYLOAD)
    cache = FakeJobCache()

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job.title == "Vaga sem detalhes suficientes"
    assert cache.saved_jobs == []


def test_refresh_skips_cache_read_and_saves_updated_job() -> None:
    """Bypasses the current cache entry and updates it after fetching the job."""

    client = FakeAuthenticatedClient()
    cache = FakeJobCache(make_job(title="Título antigo"))

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID, refresh=True))

    assert cache.get_calls == []
    assert client.requested_ids == [JOB_ID]
    assert cache.saved_jobs == [response.job]


@pytest.mark.parametrize(
    ("required_field", "missing_value"),
    [
        ("id", ""),
        ("title", None),
        ("company", None),
        ("url", None),
        ("description_text", None),
    ],
)
def test_does_not_cache_job_missing_a_required_field(
    required_field: str,
    missing_value: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Does not cache the job if any required cache field is missing."""

    job = make_job(**{required_field: missing_value})
    cache = FakeJobCache()
    client = FakeAuthenticatedClient()
    monkeypatch.setattr("app.services.job_details.parse_job_detail_voyager", lambda *_: job)

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job == job
    assert cache.saved_jobs == []

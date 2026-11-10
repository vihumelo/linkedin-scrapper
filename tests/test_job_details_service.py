"""Testes de política do cache no serviço de detalhes da vaga."""

import asyncio

import pytest

from app.ports.job_cache import JobCacheError
from app.schemas.jobs import JobDetail
from app.services.job_details import JobDetailService

JOB_ID = "4486249045"
COMPLETE_JOB_HTML = """
<h2 class="topcard__title">Técnico em Engenharia Clínica</h2>
<a class="topcard__org-name-link">Empresa Exemplo</a>
<div class="show-more-less-html__markup"><p>Descrição completa da vaga.</p></div>
"""
INCOMPLETE_JOB_HTML = '<h2 class="topcard__title">Vaga sem detalhes suficientes</h2>'


def make_job(**overrides: str | None) -> JobDetail:
    """Monta uma vaga completa para os testes do serviço."""

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


class FakePublicClient:
    """Cliente público falso que conta as consultas ao LinkedIn."""

    def __init__(self, html: str = COMPLETE_JOB_HTML) -> None:
        self.html = html
        self.requested_ids: list[str] = []

    async def get_job_details_html(self, job_id: str) -> str:
        """Retorna HTML estático e registra o ID consultado."""

        self.requested_ids.append(job_id)
        return self.html


class FakeJobCache:
    """Cache falso com falhas controladas para testar a política do serviço."""

    def __init__(self, cached_job: JobDetail | None = None) -> None:
        self.cached_job = cached_job
        self.get_error: Exception | None = None
        self.save_error: Exception | None = None
        self.get_calls: list[str] = []
        self.saved_jobs: list[JobDetail] = []

    async def get(self, job_id: str) -> JobDetail | None:
        """Retorna o valor configurado ou simula falha de leitura."""

        self.get_calls.append(job_id)
        if self.get_error:
            raise self.get_error
        return self.cached_job

    async def save(self, job: JobDetail) -> None:
        """Registra a vaga ou simula falha de gravação."""

        if self.save_error:
            raise self.save_error
        self.saved_jobs.append(job)

    async def delete(self, job_id: str) -> None:
        """Remove a vaga falsa quando o ID armazenado corresponde."""

        if self.cached_job and self.cached_job.id == job_id:
            self.cached_job = None


def test_returns_cached_job_without_calling_linkedin() -> None:
    """Retorna o detalhe armazenado e evita a consulta externa quando há cache hit."""

    client = FakePublicClient()
    cache = FakeJobCache(make_job())

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job == cache.cached_job
    assert client.requested_ids == []


def test_fetches_and_caches_complete_job_on_cache_miss() -> None:
    """Consulta o LinkedIn e grava os detalhes completos quando não há cache."""

    client = FakePublicClient()
    cache = FakeJobCache()

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job.id == JOB_ID
    assert client.requested_ids == [JOB_ID]
    assert cache.saved_jobs == [response.job]


def test_cache_read_failure_falls_back_to_linkedin() -> None:
    """Busca a vaga no LinkedIn quando a leitura do cache falha."""

    client = FakePublicClient()
    cache = FakeJobCache()
    cache.get_error = JobCacheError("cache indisponível")

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job.id == JOB_ID
    assert client.requested_ids == [JOB_ID]
    assert cache.saved_jobs == [response.job]


def test_incomplete_cached_job_falls_back_to_linkedin() -> None:
    """Não retorna registros incompletos que já existam no banco."""

    client = FakePublicClient()
    cache = FakeJobCache(make_job(description_text=None))

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job.description_text == "Descrição completa da vaga."
    assert client.requested_ids == [JOB_ID]
    assert cache.saved_jobs == [response.job]


def test_cache_write_failure_does_not_discard_linkedin_response() -> None:
    """Retorna os detalhes do LinkedIn mesmo quando não é possível gravar no cache."""

    client = FakePublicClient()
    cache = FakeJobCache()
    cache.save_error = JobCacheError("cache indisponível")

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job.id == JOB_ID
    assert client.requested_ids == [JOB_ID]


def test_does_not_cache_title_only_job() -> None:
    """Não grava a vaga se faltar qualquer campo obrigatório para o cache."""

    client = FakePublicClient(INCOMPLETE_JOB_HTML)
    cache = FakeJobCache()

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job.title == "Vaga sem detalhes suficientes"
    assert cache.saved_jobs == []


def test_refresh_skips_cache_read_and_saves_updated_job() -> None:
    """Ignora o cache atual e atualiza o registro após buscar a vaga."""

    client = FakePublicClient()
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
    """Não grava a vaga se faltar qualquer campo obrigatório para o cache."""

    job = make_job(**{required_field: missing_value})
    cache = FakeJobCache()
    client = FakePublicClient()
    monkeypatch.setattr("app.services.job_details.parse_job_detail_html", lambda *_: job)

    response = asyncio.run(JobDetailService(client, cache).get_job(JOB_ID))

    assert response.job == job
    assert cache.saved_jobs == []

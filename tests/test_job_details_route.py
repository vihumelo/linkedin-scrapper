"""Testes offline do endpoint HTTP de detalhes da vaga."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_job_cache, get_public_linkedin_client
from app.main import create_app
from app.schemas.jobs import JobDetail

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "linkedin_job_detail.html"


class FakePublicLinkedInClient:
    """Cliente falso que retorna o HTML real preservado para teste."""

    async def get_job_details_html(self, job_id: str) -> str:
        """Retorna o HTML de referência sem realizar uma chamada externa."""

        return FIXTURE_PATH.read_text(encoding="utf-8")


class FakeJobCache:
    """Cache falso vazio para manter os testes da rota offline."""

    def __init__(self, cached_job: JobDetail | None = None) -> None:
        """Configura o registro retornado pelo cache e prepara o histórico."""

        self.cached_job = cached_job
        self.get_calls: list[str] = []
        self.saved_jobs: list[JobDetail] = []

    async def get(self, job_id: str) -> JobDetail | None:
        """Simula ausência da vaga no cache."""

        self.get_calls.append(job_id)
        return self.cached_job

    async def save(self, job: JobDetail) -> None:
        """Aceita a gravação sem persistir dados de teste."""

        self.saved_jobs.append(job)

    async def delete(self, job_id: str) -> None:
        """Implementa a operação exigida pelo contrato de cache."""

        if self.cached_job and self.cached_job.id == job_id:
            self.cached_job = None


def test_get_job_details_returns_structured_json() -> None:
    """Retorna detalhes validados sem incluir a página HTML bruta."""

    app = create_app()
    app.dependency_overrides[get_public_linkedin_client] = lambda: FakePublicLinkedInClient()
    app.dependency_overrides[get_job_cache] = lambda: FakeJobCache()

    with TestClient(app) as client:
        response = client.get("/api/jobs/4486249045")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "linkedin_jobs_guest"
    assert payload["job"]["id"] == "4486249045"
    assert payload["job"]["title"] == "Técnico em Engenharia Clinica"
    assert payload["job"]["url"] == "https://www.linkedin.com/jobs/view/4486249045/"
    assert "description_html" in payload["job"]
    assert "<html" not in response.text


def test_refresh_query_bypasses_cached_job() -> None:
    """A query refresh=true força consulta ao LinkedIn e atualiza o cache."""

    cache = FakeJobCache(
        JobDetail(
            id="4486249045",
            title="Título antigo",
            company="Empresa antiga",
            location="São Paulo, Brasil",
            url="https://www.linkedin.com/jobs/view/4486249045/",
            description_text="Descrição antiga.",
        )
    )
    app = create_app()
    app.dependency_overrides[get_public_linkedin_client] = lambda: FakePublicLinkedInClient()
    app.dependency_overrides[get_job_cache] = lambda: cache

    with TestClient(app) as client:
        response = client.get("/api/jobs/4486249045?refresh=true")

    assert response.status_code == 200
    assert response.json()["job"]["title"] == "Técnico em Engenharia Clinica"
    assert cache.get_calls == []
    assert cache.saved_jobs[0].title == "Técnico em Engenharia Clinica"


def test_get_job_details_rejects_non_numeric_id() -> None:
    """Retorna 422 quando o ID da vaga não contém apenas dígitos."""

    app = create_app()
    app.dependency_overrides[get_public_linkedin_client] = lambda: FakePublicLinkedInClient()
    app.dependency_overrides[get_job_cache] = lambda: FakeJobCache()

    with TestClient(app) as client:
        response = client.get("/api/jobs/not-a-job-id")

    assert response.status_code == 422


@pytest.mark.parametrize("job_id", ["١٢٣", "１２３"])
def test_get_job_details_rejects_unicode_decimal_id(job_id: str) -> None:
    """Rejeita dígitos Unicode, pois IDs do LinkedIn usam dígitos ASCII."""

    app = create_app()
    app.dependency_overrides[get_public_linkedin_client] = lambda: FakePublicLinkedInClient()
    app.dependency_overrides[get_job_cache] = lambda: FakeJobCache()

    with TestClient(app) as client:
        response = client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 422

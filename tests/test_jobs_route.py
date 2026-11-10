"""Testes do endpoint HTTP de busca de vagas."""

from fastapi.testclient import TestClient

from app.core.dependencies import get_authenticated_linkedin_client
from app.main import create_app


class FakeAuthenticatedLinkedInClient:
    """Cliente falso com uma página de resultados estática."""

    async def search_jobs(self, keywords: str, geo_id: str, start: int) -> str:
        """Retorna um cartão e um controle acessível de próxima página."""

        assert (keywords, geo_id, start) == ("biomedicina", "106057199", 0)
        return """
        <div componentkey="job-card-component-ref-123">
          <p><span aria-hidden="true">Analista de biomedicina</span></p>
          <p>Empresa</p><p>São Paulo, Brasil</p>
        </div>
        <a rel="next" href="?start=1">Próxima</a>
        """


def test_search_jobs_response_contract() -> None:
    """Retorna consulta, paginação e vagas sem expor HTML."""

    fake_client = FakeAuthenticatedLinkedInClient()
    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: fake_client

    with TestClient(app) as client:
        response = client.get("/api/jobs/search", params={"keywords": "biomedicina"})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == {"keywords": "biomedicina", "geo_id": "106057199"}
    assert body["pagination"] == {
        "start": 0,
        "count": 1,
        "next_start": 1,
        "has_next": True,
    }
    assert body["jobs"][0]["id"] == "123"
    assert "html" not in body


def test_search_jobs_rejects_negative_start() -> None:
    """Valida que o offset de paginação seja não negativo."""

    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: (
        FakeAuthenticatedLinkedInClient()
    )

    with TestClient(app) as client:
        response = client.get("/api/jobs/search", params={"keywords": "biomedicina", "start": -1})

    assert response.status_code == 422

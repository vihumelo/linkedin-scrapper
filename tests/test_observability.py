"""Testes dos logs e metadados globais de requisição."""

import logging
import re

from fastapi.testclient import TestClient

from app.core.dependencies import get_authenticated_linkedin_client
from app.main import create_app


class FailingAuthenticatedClient:
    """Cliente falso que levanta uma falha inesperada durante a busca."""

    async def search_jobs(self, keywords: str, geo_id: str, start: int) -> str:
        """Simula uma exceção não tratada do serviço externo."""

        raise RuntimeError("falha interna simulada")


def test_request_id_is_returned_and_logged_without_query_values(caplog) -> None:
    """Correlaciona a resposta com o log e registra apenas o template da rota."""

    app = create_app()
    app.dependency_overrides[get_authenticated_linkedin_client] = lambda: (
        FailingAuthenticatedClient()
    )

    with caplog.at_level(logging.INFO):
        with TestClient(app) as client:
            response = client.get(
                "/api/jobs/search",
                params={"keywords": "termo privado", "geo_id": "106057199"},
                headers={"X-Request-ID": "trace-abc_123"},
            )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "trace-abc_123"
    assert response.json()["request_id"] == "trace-abc_123"
    completed = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "http.request.completed"
    )
    assert completed.request_id == "trace-abc_123"
    assert completed.route == "/jobs/search"
    assert completed.status_code == 500
    assert not hasattr(completed, "query")
    assert "termo privado" not in caplog.text


def test_invalid_request_id_is_replaced() -> None:
    """Não reflete valores arbitrários no header de correlação."""

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/openapi.json", headers={"X-Request-ID": "bad id"})

    assert response.status_code == 200
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["X-Request-ID"])

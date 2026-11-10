"""Tests for logs and global request metadata."""

import logging
import re

from fastapi.testclient import TestClient

from app.core.dependencies import get_authenticated_linkedin_client
from app.main import create_app


class FailingAuthenticatedClient:
    """Fake client that raises an unexpected error during the search."""

    async def search_jobs(self, keywords: str, geo_id: str, start: int) -> str:
        """Simulates an unhandled exception from the external service."""

        raise RuntimeError("falha interna simulada")


def test_request_id_is_returned_and_logged_without_query_values(caplog) -> None:
    """Correlates the response with the log and records only the route template."""

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
    """Does not echo arbitrary values in the correlation header."""

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/openapi.json", headers={"X-Request-ID": "bad id"})

    assert response.status_code == 200
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["X-Request-ID"])

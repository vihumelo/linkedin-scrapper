"""Teste online opcional da rota pública de detalhes de uma vaga.

Para executá-lo explicitamente:
    RUN_LINKEDIN_JOB_DETAILS_INTEGRATION=1 .venv/bin/python -m pytest \
        tests/integration/test_linkedin_job_details.py
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

JOB_ID = "4486249045"


@pytest.mark.skipif(
    os.getenv("RUN_LINKEDIN_JOB_DETAILS_INTEGRATION") != "1",
    reason=(
        "teste online desativado; habilite-o explicitamente com "
        "RUN_LINKEDIN_JOB_DETAILS_INTEGRATION=1"
    ),
)
def test_job_details_route_with_live_linkedin_response() -> None:
    """Consulta a rota local e valida os detalhes retornados pelo LinkedIn real."""

    app = create_app()
    with TestClient(app) as client:
        response = client.get(f"/api/jobs/{JOB_ID}?refresh=true")

    assert response.status_code == 200
    payload = response.json()
    job = payload["job"]
    assert payload["source"] == "linkedin_jobs_guest"
    assert job["id"] == JOB_ID
    assert job["title"]
    assert job["company"]
    assert job["description_text"]
    assert job["description_html"]

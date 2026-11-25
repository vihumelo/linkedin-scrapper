"""Optional online test for the authenticated Voyager job details route.

Run it explicitly with:
    pytest --integration tests/integration/test_linkedin_job_details.py
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.jobs import JobDetail, JobDetailResponse

pytestmark = pytest.mark.integration

JOB_ID = "4486249045"


@pytest.mark.usefixtures("linkedin_settings")
def test_job_details_route_with_live_linkedin_response() -> None:
    """Queries the local route and validates the details returned by real LinkedIn."""

    app = create_app()
    with TestClient(app) as client:
        response = client.get(f"/api/job/{JOB_ID}?refresh=true")

    assert response.status_code == 200
    payload = response.json()
    result = JobDetailResponse.model_validate(payload)
    job = result.job

    assert set(payload) == {"is_cached", "job"}
    assert set(payload["job"]) == set(JobDetail.model_fields)
    assert result.is_cached is False
    assert job.id == JOB_ID
    assert job.title
    assert job.company
    assert job.description_text
    assert job.job_state is None or job.job_state
    assert job.closed_at is None or datetime.fromisoformat(job.closed_at)
    assert job.expires_at is None or datetime.fromisoformat(job.expires_at)
    assert job.application_url is None or job.application_url.startswith(("http://", "https://"))

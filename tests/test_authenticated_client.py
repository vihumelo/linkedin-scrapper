"""Offline tests for authenticated LinkedIn job searches."""

import asyncio

import httpx
import pytest

from app.clients.authenticated_client import AuthenticatedLinkedInClient
from app.core.config import Settings


@pytest.mark.parametrize("f_tpr", ["r86400", "r604800", "r2592000"])
def test_search_jobs_sends_location_and_time_filter(f_tpr: str) -> None:
    """Includes LinkedIn's geo and date filters in the upstream search URL."""

    requests: list[httpx.Request] = []

    def return_results(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            text="<html>results</html>",
            headers={"content-type": "text/html"},
            request=request,
        )

    async def call_client() -> None:
        settings = Settings(linkedin_li_at="li-at-test", linkedin_jsessionid="session-test")
        async with httpx.AsyncClient(transport=httpx.MockTransport(return_results)) as http_client:
            linkedin_client = AuthenticatedLinkedInClient(http_client, settings)
            await linkedin_client.search_jobs(
                keywords="software engineer",
                geo_id="90009574",
                f_tpr=f_tpr,
                start=25,
            )

    asyncio.run(call_client())

    assert len(requests) == 1
    params = requests[0].url.params
    assert params["keywords"] == "software engineer"
    assert params["geoId"] == "90009574"
    assert params["f_TPR"] == f_tpr
    assert params["start"] == "25"

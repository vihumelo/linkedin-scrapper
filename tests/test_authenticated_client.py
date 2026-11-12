"""Offline tests for authenticated LinkedIn job searches."""

import asyncio

import httpx
import pytest

from app.clients.authenticated_client import (
    AuthenticatedLinkedInClient,
    LinkedInAuthenticationError,
    LinkedInCredentialsError,
    LinkedInResponseError,
    LinkedInTimeoutError,
)
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


def test_search_jobs_requires_credentials_before_request() -> None:
    """Does not send a request when the authentication cookies are missing."""

    def fail_if_called(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"Não deveria enviar uma requisição para {request.url}.")

    async def call_client() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail_if_called)) as http_client:
            client = AuthenticatedLinkedInClient(
                http_client,
                Settings(linkedin_li_at="", linkedin_jsessionid=""),
            )
            with pytest.raises(LinkedInCredentialsError):
                await client.search_jobs("python", "1", "r86400", 0)

    asyncio.run(call_client())


@pytest.mark.parametrize(
    ("network_error", "expected_error"),
    [
        (httpx.ReadTimeout, LinkedInTimeoutError),
        (httpx.ConnectError, LinkedInResponseError),
    ],
)
def test_search_jobs_maps_network_errors(
    network_error: type[httpx.RequestError],
    expected_error: type[Exception],
) -> None:
    """Maps timeouts and other network errors to safe integration errors."""

    def fail_request(request: httpx.Request) -> httpx.Response:
        raise network_error("network failure", request=request)

    async def call_client() -> None:
        settings = Settings(linkedin_li_at="li-at-test", linkedin_jsessionid="session-test")
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail_request)) as http_client:
            client = AuthenticatedLinkedInClient(http_client, settings)
            with pytest.raises(expected_error):
                await client.search_jobs("python", "1", "r86400", 0)

    asyncio.run(call_client())


@pytest.mark.parametrize(
    ("status_code", "content_type", "body", "expected_error"),
    [
        (401, "text/html", "login", LinkedInAuthenticationError),
        (500, "text/html", "error", LinkedInResponseError),
        (200, "application/json", "{}", LinkedInResponseError),
        (200, "text/html", "  ", LinkedInResponseError),
    ],
)
def test_search_jobs_rejects_invalid_upstream_responses(
    status_code: int,
    content_type: str,
    body: str,
    expected_error: type[Exception],
) -> None:
    """Rejects authentication failures, HTTP errors, and invalid search pages."""

    def return_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            text=body,
            headers={"content-type": content_type},
            request=request,
        )

    async def call_client() -> None:
        settings = Settings(linkedin_li_at="li-at-test", linkedin_jsessionid="session-test")
        async with httpx.AsyncClient(transport=httpx.MockTransport(return_response)) as http_client:
            client = AuthenticatedLinkedInClient(http_client, settings)
            with pytest.raises(expected_error):
                await client.search_jobs("python", "1", "r86400", 0)

    asyncio.run(call_client())

"""Offline tests for authenticated LinkedIn Voyager requests."""

import asyncio

import httpx
import pytest

from app.clients.linkedin_session import (
    LinkedInAuthenticationError,
    LinkedInCredentialsError,
    LinkedInResponseError,
    LinkedInServiceUnavailableError,
    LinkedInSession,
    LinkedInTimeoutError,
)
from app.clients.linkedin_voyager_client import LinkedInVoyagerClient, VoyagerNotFoundError
from app.core.config import Settings

JOB_ID = "4486249045"
QUERY_ID = "voyagerSearchDashClusters.test"
JSON_CONTENT_TYPE = "application/vnd.linkedin.normalized+json+2.1"


def test_get_job_details_sends_voyager_headers_and_decoration() -> None:
    """Requests normalized job details with the Voyager protocol headers."""

    requests: list[httpx.Request] = []

    def return_job(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": {"title": "Engenheiro de software"}},
            headers={"content-type": JSON_CONTENT_TYPE},
            request=request,
        )

    async def call_client() -> None:
        settings = Settings(linkedin_li_at="li-at-test", linkedin_jsessionid="session-test")
        async with httpx.AsyncClient(transport=httpx.MockTransport(return_job)) as http_client:
            client = LinkedInVoyagerClient(LinkedInSession(http_client, settings), QUERY_ID)
            payload = await client.get_job_details(JOB_ID)
            assert payload["data"]["title"] == "Engenheiro de software"

    asyncio.run(call_client())

    assert len(requests) == 1
    request = requests[0]
    assert request.url.path == f"/voyager/api/jobs/jobPostings/{JOB_ID}"
    assert (
        request.url.params["decorationId"]
        == "com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65"
    )
    assert request.headers["accept"] == JSON_CONTENT_TYPE
    assert request.headers["x-restli-protocol-version"] == "2.0.0"
    assert request.headers["csrf-token"] == "session-test"


@pytest.mark.parametrize("job_id", ["١٢٣", "１２３"])
def test_get_job_details_rejects_unicode_decimal_id(job_id: str) -> None:
    """Rejects non-ASCII IDs before sending an HTTP request."""

    def fail_if_called(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"Should not send a request to {request.url}.")

    async def call_client() -> None:
        settings = Settings(linkedin_li_at="li-at-test", linkedin_jsessionid="session-test")
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail_if_called)) as http_client:
            client = LinkedInVoyagerClient(LinkedInSession(http_client, settings), QUERY_ID)
            with pytest.raises(ValueError):
                await client.get_job_details(job_id)

    asyncio.run(call_client())


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (401, LinkedInAuthenticationError),
        (403, LinkedInAuthenticationError),
        (404, VoyagerNotFoundError),
        (429, LinkedInServiceUnavailableError),
        (503, LinkedInServiceUnavailableError),
    ],
)
def test_get_job_details_maps_upstream_status(
    status_code: int,
    error_type: type[Exception],
) -> None:
    """Maps authentication, missing job, and temporary upstream failures."""

    def return_status(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request)

    async def call_client() -> None:
        settings = Settings(linkedin_li_at="li-at-test", linkedin_jsessionid="session-test")
        async with httpx.AsyncClient(transport=httpx.MockTransport(return_status)) as http_client:
            client = LinkedInVoyagerClient(LinkedInSession(http_client, settings), QUERY_ID)
            with pytest.raises(error_type):
                await client.get_job_details(JOB_ID)

    asyncio.run(call_client())


def test_get_job_details_requires_credentials_before_request() -> None:
    """Fails without making a request if the LinkedIn cookies are missing."""

    def fail_if_called(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"Should not send a request to {request.url}.")

    async def call_client() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail_if_called)) as http_client:
            client = LinkedInVoyagerClient(
                LinkedInSession(http_client, Settings(linkedin_li_at="", linkedin_jsessionid="")),
                QUERY_ID,
            )
            with pytest.raises(LinkedInCredentialsError, match="authentication cookies"):
                await client.get_job_details(JOB_ID)

    asyncio.run(call_client())


@pytest.mark.parametrize(
    ("network_error", "expected_error"),
    [
        (httpx.ReadTimeout, LinkedInTimeoutError),
        (httpx.ConnectError, LinkedInResponseError),
    ],
)
def test_get_job_details_maps_network_errors(
    network_error: type[httpx.RequestError],
    expected_error: type[Exception],
) -> None:
    """Maps upstream timeouts and transport failures to safe integration errors."""

    def fail_request(request: httpx.Request) -> httpx.Response:
        raise network_error("network failure", request=request)

    async def call_client() -> None:
        settings = Settings(linkedin_li_at="li-at-test", linkedin_jsessionid="session-test")
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail_request)) as http_client:
            client = LinkedInVoyagerClient(LinkedInSession(http_client, settings), QUERY_ID)
            with pytest.raises(expected_error):
                await client.get_job_details(JOB_ID)

    asyncio.run(call_client())


@pytest.mark.parametrize(
    ("status_code", "content_type", "body"),
    [
        (400, JSON_CONTENT_TYPE, '{"error": "bad request"}'),
        (200, "text/html", "<html>not JSON</html>"),
        (200, JSON_CONTENT_TYPE, "{invalid json"),
        (200, JSON_CONTENT_TYPE, "[]"),
    ],
)
def test_get_job_details_rejects_invalid_upstream_responses(
    status_code: int,
    content_type: str,
    body: str,
) -> None:
    """Rejects HTTP errors, invalid media types, malformed JSON, and non-object payloads."""

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
            client = LinkedInVoyagerClient(LinkedInSession(http_client, settings), QUERY_ID)
            with pytest.raises(LinkedInResponseError):
                await client.get_job_details(JOB_ID)

    asyncio.run(call_client())


def test_get_job_details_logs_status_and_duration(caplog) -> None:
    """Logs the upstream status and duration without exposing credentials."""

    def return_rate_limit(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)

    async def call_client() -> None:
        settings = Settings(linkedin_li_at="li-at-secret", linkedin_jsessionid="session-secret")
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(return_rate_limit)
        ) as http_client:
            client = LinkedInVoyagerClient(LinkedInSession(http_client, settings), QUERY_ID)
            with pytest.raises(LinkedInServiceUnavailableError):
                await client.get_job_details(JOB_ID)

    with caplog.at_level("INFO"):
        asyncio.run(call_client())

    record = next(
        item for item in caplog.records if getattr(item, "event", None) == "upstream.response"
    )
    assert record.integration == "linkedin_job_details_voyager"
    assert record.upstream_status == 429
    assert record.duration_ms >= 0
    assert "li-at-secret" not in caplog.text
    assert "session-secret" not in caplog.text


def run_company_search(
    handler: httpx.MockTransport,
    name: str = "corporate",
    start: int = 0,
    settings: Settings | None = None,
) -> dict[str, object]:
    """Runs a company search against a mocked Voyager transport."""

    async def call_client() -> dict[str, object]:
        async with httpx.AsyncClient(transport=handler) as http_client:
            client = LinkedInVoyagerClient(
                LinkedInSession(
                    http_client,
                    settings
                    or Settings(linkedin_li_at="li-at-test", linkedin_jsessionid="session-test"),
                ),
                QUERY_ID,
            )
            return dict(await client.search_companies(name, start))

    return asyncio.run(call_client())


def test_search_companies_sends_graphql_query_with_escaped_name() -> None:
    """Escapes Rest.li syntax characters in the name and sends the configured query ID."""

    requests: list[httpx.Request] = []

    def return_results(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": {"data": {}}},
            headers={"content-type": JSON_CONTENT_TYPE},
            request=request,
        )

    payload = run_company_search(
        httpx.MockTransport(return_results), name="Acme (BR), Inc: Labs", start=20
    )

    assert payload == {"data": {"data": {}}}
    request = requests[0]
    assert request.url.path == "/voyager/api/graphql"
    raw_query = request.url.query.decode()
    assert raw_query.endswith(f"&queryId={QUERY_ID}")
    assert "(start:20,origin:GLOBAL_SEARCH_HEADER," in raw_query
    assert "keywords:Acme%20%28BR%29%2C%20Inc%3A%20Labs," in raw_query
    assert "value:List(COMPANIES)" in raw_query
    assert request.headers["accept"] == JSON_CONTENT_TYPE
    assert request.headers["x-restli-protocol-version"] == "2.0.0"
    assert request.headers["csrf-token"] == "session-test"


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (401, LinkedInAuthenticationError),
        (404, VoyagerNotFoundError),
        (500, LinkedInServiceUnavailableError),
        (400, LinkedInResponseError),
    ],
)
def test_search_companies_maps_upstream_status(
    status_code: int,
    error_type: type[Exception],
) -> None:
    """Applies the shared Voyager status mapping to company searches."""

    def return_status(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request)

    with pytest.raises(error_type):
        run_company_search(httpx.MockTransport(return_status))


def test_search_companies_validates_input_before_request() -> None:
    """Rejects missing credentials and negative offsets without contacting LinkedIn."""

    def fail_if_called(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"Should not send a request to {request.url}.")

    transport = httpx.MockTransport(fail_if_called)
    with pytest.raises(LinkedInCredentialsError):
        run_company_search(transport, settings=Settings(linkedin_li_at="", linkedin_jsessionid=""))
    with pytest.raises(ValueError):
        run_company_search(transport, start=-1)


def test_search_companies_logs_its_integration(caplog: pytest.LogCaptureFixture) -> None:
    """Identifies company search responses in the upstream logs."""

    def return_unavailable(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"data": {"status": 500}}, request=request)

    with caplog.at_level("INFO"), pytest.raises(LinkedInServiceUnavailableError):
        run_company_search(httpx.MockTransport(return_unavailable))

    record = next(
        item for item in caplog.records if getattr(item, "event", None) == "upstream.response"
    )
    assert record.__dict__["integration"] == "linkedin_company_search_voyager"
    assert record.__dict__["upstream_status"] == 500

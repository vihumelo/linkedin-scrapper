"""Asynchronous client for LinkedIn's Voyager JSON API."""

import logging
from time import perf_counter
from urllib.parse import quote

import httpx

from app.clients.linkedin_session import (
    LinkedInAuthenticationError,
    LinkedInClientError,
    LinkedInResponseError,
    LinkedInServiceUnavailableError,
    LinkedInSession,
    LinkedInTimeoutError,
    redirected_to_authentication,
)
from app.core.json_types import JSONValue, normalize_json_value

logger = logging.getLogger(__name__)
LINKEDIN_JOB_DETAILS_URL = "https://www.linkedin.com/voyager/api/jobs/jobPostings/{job_id}"
LINKEDIN_JOB_DETAILS_DECORATION = "com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65"
LINKEDIN_GRAPHQL_URL = "https://www.linkedin.com/voyager/api/graphql"
LINKEDIN_VOYAGER_ACCEPT = "application/vnd.linkedin.normalized+json+2.1"
LINKEDIN_RESTLI_PROTOCOL_VERSION = "2.0.0"
JOB_DETAILS_INTEGRATION = "linkedin_job_details_voyager"
COMPANY_SEARCH_INTEGRATION = "linkedin_company_search_voyager"


class VoyagerNotFoundError(LinkedInClientError):
    """Indicates that Voyager answered HTTP 404 for the requested resource."""


class LinkedInVoyagerClient:
    """Performs authenticated requests to LinkedIn's Voyager API."""

    def __init__(self, session: LinkedInSession, company_search_query_id: str) -> None:
        """Initializes the client with the shared session and the GraphQL query IDs."""

        self._session = session
        self._company_search_query_id = company_search_query_id

    async def get_job_details(self, job_id: str) -> dict[str, JSONValue]:
        """Requests normalized job details for one job posting."""

        self._session.require_credentials(JOB_DETAILS_INTEGRATION)
        if not job_id.isascii() or not job_id.isdigit():
            raise ValueError("The job ID must contain only ASCII digits.")

        return await self._get(
            LINKEDIN_JOB_DETAILS_URL.format(job_id=job_id),
            JOB_DETAILS_INTEGRATION,
            params={"decorationId": LINKEDIN_JOB_DETAILS_DECORATION},
        )

    async def search_companies(self, name: str, start: int) -> dict[str, JSONValue]:
        """Requests one page of LinkedIn company search results for a company name."""

        self._session.require_credentials(COMPANY_SEARCH_INTEGRATION)
        if start < 0:
            raise ValueError("The start offset must not be negative.")

        return await self._get(
            _company_search_url(name, start, self._company_search_query_id),
            COMPANY_SEARCH_INTEGRATION,
        )

    async def _get(
        self,
        url: str,
        integration: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, JSONValue]:
        """Sends a Voyager GET request and returns the validated JSON object."""

        started_at = perf_counter()
        try:
            response = await self._session.http_client.get(
                url,
                params=params,
                headers={
                    "Accept": LINKEDIN_VOYAGER_ACCEPT,
                    "x-restli-protocol-version": LINKEDIN_RESTLI_PROTOCOL_VERSION,
                    "csrf-token": self._session.csrf_token,
                },
            )
        except httpx.TimeoutException as exc:
            logger.warning(
                "The LinkedIn Voyager request timed out.",
                extra={
                    "event": "upstream.request.failed",
                    "integration": integration,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise LinkedInTimeoutError("The LinkedIn request exceeded the time limit.") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "A network error occurred while requesting the LinkedIn Voyager API.",
                extra={
                    "event": "upstream.request.failed",
                    "integration": integration,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise LinkedInResponseError("Could not query LinkedIn.") from exc

        logger.log(
            logging.WARNING if response.status_code >= 400 else logging.INFO,
            "Received a response from LinkedIn.",
            extra={
                "event": "upstream.response",
                "integration": integration,
                "upstream_status": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        _validate_voyager_response(response)
        return _decode_voyager_payload(response)


def _company_search_url(name: str, start: int, query_id: str) -> str:
    """Builds the GraphQL search URL, escaping the name so it cannot break the Rest.li syntax."""

    variables = (
        f"(start:{start},origin:GLOBAL_SEARCH_HEADER,"
        f"query:(keywords:{quote(name, safe='')},flagshipSearchIntent:SEARCH_SRP,"
        "queryParameters:List((key:resultType,value:List(COMPANIES))),"
        "includeFiltersInResponse:false))"
    )
    return f"{LINKEDIN_GRAPHQL_URL}?variables={variables}&queryId={quote(query_id, safe='.')}"


def _validate_voyager_response(response: httpx.Response) -> None:
    """Raises a safe integration error when Voyager returns an unsuccessful response."""

    if response.status_code in (401, 403) or redirected_to_authentication(response):
        raise LinkedInAuthenticationError("LinkedIn rejected the configured authentication.")
    if response.status_code == 404:
        raise VoyagerNotFoundError("LinkedIn's Voyager API returned HTTP 404.")
    if response.status_code == 429 or response.status_code >= 500:
        raise LinkedInServiceUnavailableError("LinkedIn's Voyager endpoint is unavailable.")
    if response.is_error:
        raise LinkedInResponseError("LinkedIn returned an error response.")
    if LINKEDIN_VOYAGER_ACCEPT not in response.headers.get("content-type", "").casefold():
        raise LinkedInResponseError("LinkedIn did not return a valid Voyager JSON response.")


def _decode_voyager_payload(response: httpx.Response) -> dict[str, JSONValue]:
    """Decodes and validates the JSON object returned by the Voyager API."""

    try:
        payload: object = response.json()
    except ValueError as exc:
        raise LinkedInResponseError("LinkedIn returned invalid JSON.") from exc
    try:
        normalized_payload = normalize_json_value(payload)
    except ValueError as exc:
        raise LinkedInResponseError("LinkedIn returned an invalid JSON structure.") from exc
    if not isinstance(normalized_payload, dict):
        raise LinkedInResponseError("LinkedIn returned an unexpected JSON structure.")
    return normalized_payload

"""Asynchronous client for LinkedIn HTML pages."""

import logging
from time import perf_counter
from typing import Literal

import httpx

from app.clients.linkedin_session import (
    LinkedInAuthenticationError,
    LinkedInResponseError,
    LinkedInSession,
    LinkedInTimeoutError,
    redirected_to_authentication,
)

logger = logging.getLogger(__name__)
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs/search-results/"
JOBS_SEARCH_INTEGRATION = "linkedin_jobs_search"


class LinkedInHtmlClient:
    """Requests LinkedIn HTML pages through the authenticated session."""

    def __init__(self, session: LinkedInSession) -> None:
        """Initializes the client with the shared authenticated session."""

        self._session = session

    async def search_jobs(
        self,
        keywords: str | None,
        geo_id: str,
        f_tpr: Literal["r86400", "r604800", "r2592000"],
        start: int,
        company_id: str | None = None,
    ) -> str:
        """Requests the LinkedIn results HTML page for the supplied parameters."""

        self._session.require_credentials(JOBS_SEARCH_INTEGRATION)

        started_at = perf_counter()
        params: dict[str, str | int] = {
            "keywords": keywords if keywords is not None else "jobs",
            "geoId": geo_id,
            "f_TPR": f_tpr,
            "origin": "SEMANTIC_SEARCH_LANDING_PAGE",
            "start": start,
        }
        if company_id is not None:
            params["f_C"] = company_id
        try:
            response = await self._session.http_client.get(
                LINKEDIN_SEARCH_URL,
                params=params,
            )
        except httpx.TimeoutException as exc:
            logger.warning(
                "The LinkedIn integration request timed out.",
                extra={
                    "event": "upstream.request.failed",
                    "integration": JOBS_SEARCH_INTEGRATION,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise LinkedInTimeoutError("The LinkedIn request exceeded the time limit.") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "A network error occurred while requesting LinkedIn.",
                extra={
                    "event": "upstream.request.failed",
                    "integration": JOBS_SEARCH_INTEGRATION,
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
                "integration": JOBS_SEARCH_INTEGRATION,
                "upstream_status": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        if response.status_code in (401, 403):
            raise LinkedInAuthenticationError("LinkedIn rejected the configured authentication.")
        if response.is_error:
            logger.warning("LinkedIn responded with HTTP status %s.", response.status_code)
            raise LinkedInResponseError("LinkedIn returned an error response.")
        if redirected_to_authentication(response):
            raise LinkedInAuthenticationError("LinkedIn redirected the request to authentication.")
        if "text/html" not in response.headers.get("content-type", "").casefold():
            raise LinkedInResponseError("LinkedIn did not return a valid HTML page.")
        if not response.text.strip():
            raise LinkedInResponseError("LinkedIn returned an empty page.")
        return response.text

"""Authenticated LinkedIn session and errors shared by every LinkedIn client."""

import logging
from urllib.parse import urlparse

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class LinkedInClientError(Exception):
    """Safe error raised by the LinkedIn integration."""


class LinkedInCredentialsError(LinkedInClientError):
    """Indicates that the required cookies are not configured."""


class LinkedInAuthenticationError(LinkedInClientError):
    """Indicates that LinkedIn rejected the configured authentication."""


class LinkedInResponseError(LinkedInClientError):
    """Indicates an invalid or unexpected response from LinkedIn."""


class LinkedInTimeoutError(LinkedInClientError):
    """Indicates that the LinkedIn request timed out."""


class LinkedInServiceUnavailableError(LinkedInClientError):
    """Indicates that LinkedIn is rate limiting or temporarily unavailable."""


class LinkedInSession:
    """Holds the authenticated HTTP session and the credentials it was built from."""

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        """Stores the shared HTTP session and integration settings."""

        self._http_client = http_client
        self._settings = settings

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Returns the HTTP session carrying the LinkedIn cookies and headers."""

        return self._http_client

    @property
    def csrf_token(self) -> str:
        """Returns the CSRF token LinkedIn expects, derived from the JSESSIONID cookie."""

        return self._settings.linkedin_jsessionid.strip('"')

    def require_credentials(self, integration: str) -> None:
        """Raises before any request is sent when the LinkedIn cookies are missing."""

        if self._settings.linkedin_li_at and self._settings.linkedin_jsessionid:
            return
        logger.error(
            "LinkedIn request skipped because integration credentials are missing.",
            extra={
                "event": "upstream.request.skipped",
                "integration": integration,
                "reason": "credentials_missing",
            },
        )
        raise LinkedInCredentialsError("LinkedIn authentication cookies are not configured.")


def create_authenticated_http_client(settings: Settings) -> httpx.AsyncClient:
    """Creates a reusable HTTP/2 session with the integration headers and cookies."""

    return httpx.AsyncClient(
        http2=True,
        timeout=settings.http_timeout_seconds,
        follow_redirects=True,
        cookies={
            "li_at": settings.linkedin_li_at,
            "JSESSIONID": settings.linkedin_jsessionid,
        },
        headers={
            "User-Agent": settings.linkedin_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
        },
    )


def redirected_to_authentication(response: httpx.Response) -> bool:
    """Detects redirects to login, authwall, or checkpoint pages without reading the HTML."""

    urls = [response.url, *(item.url for item in response.history)]
    return any(
        any(
            part in urlparse(str(url)).path.casefold()
            for part in ("authwall", "checkpoint", "/login")
        )
        for url in urls
    )

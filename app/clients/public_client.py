"""Reusable HTTP client for public LinkedIn endpoints."""

import logging
import re
from time import perf_counter

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)
PUBLIC_JOB_DETAILS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
LINKEDIN_ACCEPT = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
LINKEDIN_ACCEPT_LANGUAGE = "pt-BR,pt;q=0.9"


class PublicClientError(Exception):
    """Safe error raised when querying public LinkedIn endpoints."""


class PublicJobNotFoundError(PublicClientError):
    """Indicates that the job does not exist or is no longer available."""


class PublicServiceUnavailableError(PublicClientError):
    """Indicates that the public LinkedIn service is unavailable."""


class PublicResponseError(PublicClientError):
    """Indicates an invalid response from the public endpoint."""


class PublicTimeoutError(PublicClientError):
    """Indicates that the public request timed out."""


class PublicLinkedInClient:
    """Queries public LinkedIn pages without sending authentication cookies."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        """Initializes the client with an HTTP session that has no authentication cookies."""

        self._http_client = http_client

    async def get_job_details_html(self, job_id: str) -> str:
        """Returns the public job details HTML for a numeric job ID."""

        if re.fullmatch(r"[0-9]+", job_id) is None:
            raise ValueError("O identificador da vaga deve conter apenas dígitos.")

        started_at = perf_counter()
        try:
            response = await self._http_client.get(
                PUBLIC_JOB_DETAILS_URL.format(job_id=job_id),
            )
        except httpx.TimeoutException as exc:
            logger.warning(
                "Timeout na consulta pública ao LinkedIn.",
                extra={
                    "event": "upstream.request.failed",
                    "integration": "linkedin_job_details_guest",
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise PublicTimeoutError("A consulta pública excedeu o tempo limite.") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Falha de rede na consulta pública ao LinkedIn.",
                extra={
                    "event": "upstream.request.failed",
                    "integration": "linkedin_job_details_guest",
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise PublicServiceUnavailableError(
                "Não foi possível consultar o endpoint público do LinkedIn."
            ) from exc

        response_fields = {
            "event": "upstream.response",
            "integration": "linkedin_job_details_guest",
            "upstream_status": response.status_code,
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
        }
        if response.status_code == 429 and response.headers.get("retry-after"):
            response_fields["retry_after"] = response.headers["retry-after"][:64]
        logger.log(
            logging.WARNING if response.status_code >= 400 else logging.INFO,
            "Resposta recebida do endpoint público do LinkedIn.",
            extra=response_fields,
        )
        if response.status_code == 404:
            raise PublicJobNotFoundError("A vaga não existe ou não está mais disponível.")
        if response.status_code == 429 or response.status_code >= 500:
            raise PublicServiceUnavailableError("O endpoint público do LinkedIn está indisponível.")
        if response.is_error:
            raise PublicResponseError("O endpoint público do LinkedIn retornou um erro.")
        if "text/html" not in response.headers.get("content-type", "").casefold():
            raise PublicResponseError("O endpoint público não retornou HTML.")
        if not response.text.strip():
            raise PublicResponseError("O endpoint público retornou uma página vazia.")
        return response.text


def create_public_http_client(settings: Settings) -> httpx.AsyncClient:
    """Creates a reusable HTTP/2 session without authentication cookies."""

    return httpx.AsyncClient(
        http2=True,
        timeout=settings.http_timeout_seconds,
        follow_redirects=True,
        headers={
            "User-Agent": settings.linkedin_user_agent,
            "Accept": LINKEDIN_ACCEPT,
            "Accept-Language": LINKEDIN_ACCEPT_LANGUAGE,
        },
    )

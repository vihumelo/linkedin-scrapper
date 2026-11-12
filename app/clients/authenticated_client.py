"""Asynchronous client for LinkedIn job searches."""

import logging
from time import perf_counter
from typing import Literal
from urllib.parse import urlparse

import httpx

from app.core.config import Settings
from app.core.json_types import JSONValue, normalize_json_value

logger = logging.getLogger(__name__)
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs/search-results/"
LINKEDIN_JOB_DETAILS_URL = "https://www.linkedin.com/voyager/api/jobs/jobPostings/{job_id}"
LINKEDIN_JOB_DETAILS_DECORATION = "com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65"
LINKEDIN_VOYAGER_ACCEPT = "application/vnd.linkedin.normalized+json+2.1"
LINKEDIN_RESTLI_PROTOCOL_VERSION = "2.0.0"


class AuthenticatedClientError(Exception):
    """Safe error raised by the LinkedIn integration."""


class LinkedInCredentialsError(AuthenticatedClientError):
    """Indicates that the required cookies are not configured."""


class LinkedInAuthenticationError(AuthenticatedClientError):
    """Indicates that LinkedIn rejected the configured authentication."""


class LinkedInResponseError(AuthenticatedClientError):
    """Indicates an invalid or unexpected response from LinkedIn."""


class LinkedInTimeoutError(AuthenticatedClientError):
    """Indicates that the LinkedIn request timed out."""


class LinkedInJobNotFoundError(AuthenticatedClientError):
    """Indicates that the requested job does not exist or is unavailable."""


class LinkedInServiceUnavailableError(AuthenticatedClientError):
    """Indicates that LinkedIn is rate limiting or temporarily unavailable."""


class AuthenticatedLinkedInClient:
    """Performs authenticated LinkedIn search and job detail requests."""

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        """Initializes the client with the HTTP session and integration settings."""

        self._http_client = http_client
        self._settings = settings

    async def search_jobs(
        self,
        keywords: str,
        geo_id: str,
        f_tpr: Literal["r86400", "r604800", "r2592000"],
        start: int,
    ) -> str:
        """Requests the LinkedIn results HTML page for the supplied parameters."""

        if not self._settings.linkedin_li_at or not self._settings.linkedin_jsessionid:
            logger.error(
                "Busca do LinkedIn não iniciada: faltam credenciais de integração.",
                extra={
                    "event": "upstream.request.skipped",
                    "integration": "linkedin_jobs_search",
                    "reason": "credentials_missing",
                },
            )
            raise LinkedInCredentialsError("Os cookies de autenticação não estão configurados.")

        started_at = perf_counter()
        try:
            response = await self._http_client.get(
                LINKEDIN_SEARCH_URL,
                params={
                    "keywords": keywords,
                    "geoId": geo_id,
                    "f_TPR": f_tpr,
                    "origin": "SEMANTIC_SEARCH_LANDING_PAGE",
                    "start": start,
                },
            )
        except httpx.TimeoutException as exc:
            logger.warning(
                "Falha de timeout na integração com o LinkedIn.",
                extra={
                    "event": "upstream.request.failed",
                    "integration": "linkedin_jobs_search",
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise LinkedInTimeoutError("A consulta ao LinkedIn excedeu o tempo limite.") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Falha de rede na integração com o LinkedIn.",
                extra={
                    "event": "upstream.request.failed",
                    "integration": "linkedin_jobs_search",
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise LinkedInResponseError("Não foi possível consultar o LinkedIn.") from exc

        logger.log(
            logging.WARNING if response.status_code >= 400 else logging.INFO,
            "Resposta recebida do LinkedIn.",
            extra={
                "event": "upstream.response",
                "integration": "linkedin_jobs_search",
                "upstream_status": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        if response.status_code in (401, 403):
            raise LinkedInAuthenticationError("O LinkedIn recusou a autenticação configurada.")
        if response.is_error:
            logger.warning("O LinkedIn respondeu com status HTTP %s.", response.status_code)
            raise LinkedInResponseError("O LinkedIn retornou uma resposta de erro.")
        if _redirected_to_authentication(response):
            raise LinkedInAuthenticationError(
                "O LinkedIn redirecionou a consulta para autenticação."
            )
        if "text/html" not in response.headers.get("content-type", "").casefold():
            raise LinkedInResponseError("O LinkedIn não retornou uma página HTML válida.")
        if not response.text.strip():
            raise LinkedInResponseError("O LinkedIn retornou uma página vazia.")
        return response.text

    async def get_job_details(self, job_id: str) -> dict[str, JSONValue]:
        """Requests normalized job details from LinkedIn's Voyager API."""

        if not self._settings.linkedin_li_at or not self._settings.linkedin_jsessionid:
            logger.error(
                "Detalhes da vaga não consultados: faltam credenciais de integração.",
                extra={
                    "event": "upstream.request.skipped",
                    "integration": "linkedin_job_details_voyager",
                    "reason": "credentials_missing",
                },
            )
            raise LinkedInCredentialsError("Os cookies de autenticação não estão configurados.")
        if not job_id.isascii() or not job_id.isdigit():
            raise ValueError("O identificador da vaga deve conter apenas dígitos ASCII.")

        started_at = perf_counter()
        try:
            response = await self._http_client.get(
                LINKEDIN_JOB_DETAILS_URL.format(job_id=job_id),
                params={"decorationId": LINKEDIN_JOB_DETAILS_DECORATION},
                headers={
                    "Accept": LINKEDIN_VOYAGER_ACCEPT,
                    "x-restli-protocol-version": LINKEDIN_RESTLI_PROTOCOL_VERSION,
                    "csrf-token": self._settings.linkedin_jsessionid.strip('"'),
                },
            )
        except httpx.TimeoutException as exc:
            logger.warning(
                "Timeout na consulta autenticada dos detalhes da vaga.",
                extra={
                    "event": "upstream.request.failed",
                    "integration": "linkedin_job_details_voyager",
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise LinkedInTimeoutError("A consulta ao LinkedIn excedeu o tempo limite.") from exc
        except httpx.RequestError as exc:
            logger.warning(
                "Falha de rede na consulta autenticada dos detalhes da vaga.",
                extra={
                    "event": "upstream.request.failed",
                    "integration": "linkedin_job_details_voyager",
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise LinkedInResponseError("Não foi possível consultar o LinkedIn.") from exc

        logger.log(
            logging.WARNING if response.status_code >= 400 else logging.INFO,
            "Resposta recebida do LinkedIn.",
            extra={
                "event": "upstream.response",
                "integration": "linkedin_job_details_voyager",
                "upstream_status": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        _validate_job_details_response(response)
        return _decode_job_details_payload(response)


def _validate_job_details_response(response: httpx.Response) -> None:
    """Raises a safe integration error when Voyager returns an unsuccessful response."""

    if response.status_code in (401, 403) or _redirected_to_authentication(response):
        raise LinkedInAuthenticationError("O LinkedIn recusou a autenticação configurada.")
    if response.status_code == 404:
        raise LinkedInJobNotFoundError("A vaga não existe ou não está mais disponível.")
    if response.status_code == 429 or response.status_code >= 500:
        raise LinkedInServiceUnavailableError("O endpoint Voyager do LinkedIn está indisponível.")
    if response.is_error:
        raise LinkedInResponseError("O LinkedIn retornou uma resposta de erro.")
    if (
        LINKEDIN_VOYAGER_ACCEPT.split(";")[0]
        not in response.headers.get("content-type", "").casefold()
    ):
        raise LinkedInResponseError("O LinkedIn não retornou uma resposta JSON Voyager válida.")


def _decode_job_details_payload(response: httpx.Response) -> dict[str, JSONValue]:
    """Decodes and validates the JSON object returned by the Voyager endpoint."""

    try:
        payload: object = response.json()
    except ValueError as exc:
        raise LinkedInResponseError("O LinkedIn retornou um JSON inválido.") from exc
    try:
        normalized_payload = normalize_json_value(payload)
    except ValueError as exc:
        raise LinkedInResponseError("O LinkedIn retornou uma estrutura JSON inválida.") from exc
    if not isinstance(normalized_payload, dict):
        raise LinkedInResponseError("O LinkedIn retornou uma estrutura JSON inesperada.")
    return normalized_payload


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


def _redirected_to_authentication(response: httpx.Response) -> bool:
    """Detects redirects to login, authwall, or checkpoint pages without reading the HTML."""

    urls = [response.url, *(item.url for item in response.history)]
    return any(
        any(
            part in urlparse(str(url)).path.casefold()
            for part in ("authwall", "checkpoint", "/login")
        )
        for url in urls
    )

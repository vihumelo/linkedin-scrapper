"""Cliente HTTP reutilizável para endpoints públicos do LinkedIn."""

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
    """Erro seguro ao consultar endpoints públicos do LinkedIn."""


class PublicJobNotFoundError(PublicClientError):
    """Indica que a vaga não existe ou não está mais disponível."""


class PublicServiceUnavailableError(PublicClientError):
    """Indica que o serviço público do LinkedIn está indisponível."""


class PublicResponseError(PublicClientError):
    """Indica uma resposta inválida do endpoint público."""


class PublicTimeoutError(PublicClientError):
    """Indica que a consulta pública excedeu o tempo limite."""


class PublicLinkedInClient:
    """Consulta páginas públicas do LinkedIn sem enviar cookies de autenticação."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        """Inicializa o cliente com uma sessão HTTP sem cookies de autenticação."""

        self._http_client = http_client

    async def get_job_details_html(self, job_id: str) -> str:
        """Retorna o HTML público de detalhes de uma vaga identificada por ID numérico."""

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
    """Cria uma sessão HTTP/2 reutilizável sem cookies de autenticação."""

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

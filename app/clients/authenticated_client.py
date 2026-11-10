"""Cliente assíncrono para a busca de vagas do LinkedIn."""

import logging
from time import perf_counter
from urllib.parse import urlparse

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs/search-results/"


class AuthenticatedClientError(Exception):
    """Erro seguro da integração com o LinkedIn."""


class LinkedInCredentialsError(AuthenticatedClientError):
    """Indica que os cookies necessários não foram configurados."""


class LinkedInAuthenticationError(AuthenticatedClientError):
    """Indica que o LinkedIn recusou a autenticação configurada."""


class LinkedInResponseError(AuthenticatedClientError):
    """Indica uma resposta inválida ou inesperada do LinkedIn."""


class LinkedInTimeoutError(AuthenticatedClientError):
    """Indica que a requisição ao LinkedIn excedeu o tempo limite."""


class AuthenticatedLinkedInClient:
    """Executa consultas de busca usando um cliente HTTP compartilhado."""

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        """Inicializa o cliente com a sessão HTTP e as configurações da integração."""

        self._http_client = http_client
        self._settings = settings

    async def search_jobs(self, keywords: str, geo_id: str, start: int) -> str:
        """Solicita ao LinkedIn a página HTML de resultados para os parâmetros recebidos."""

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


def create_authenticated_http_client(settings: Settings) -> httpx.AsyncClient:
    """Cria uma sessão HTTP/2 reutilizável com os headers e cookies da integração."""

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
    """Detecta redirecionamentos para login, authwall ou checkpoint sem ler o HTML."""

    urls = [response.url, *(item.url for item in response.history)]
    return any(
        any(
            part in urlparse(str(url)).path.casefold()
            for part in ("authwall", "checkpoint", "/login")
        )
        for url in urls
    )

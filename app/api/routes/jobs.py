"""Rotas para operações sobre conjuntos de vagas."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.clients.authenticated_client import (
    AuthenticatedLinkedInClient,
    LinkedInAuthenticationError,
    LinkedInCredentialsError,
    LinkedInResponseError,
    LinkedInTimeoutError,
)
from app.core.dependencies import get_authenticated_linkedin_client
from app.parsers.linkedin_jobs import HTMLStructureError
from app.schemas.jobs import JobSearchResponse
from app.services.job_search import JobSearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/search", response_model=JobSearchResponse)
async def search_jobs(
    keywords: str = Query(..., min_length=1),
    geo_id: str = Query("106057199", min_length=1),
    start: int = Query(0, ge=0),
    linkedin_client: AuthenticatedLinkedInClient = Depends(get_authenticated_linkedin_client),
) -> JobSearchResponse:
    """Busca vagas no LinkedIn e retorna cartões e paginação estruturados."""

    if not keywords.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O parâmetro keywords não pode conter apenas espaços.",
        )

    try:
        return await JobSearchService(linkedin_client).search(keywords, geo_id, start)
    except LinkedInCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A integração com o LinkedIn não está configurada.",
        ) from exc
    except LinkedInAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="O LinkedIn recusou a autenticação configurada.",
        ) from exc
    except LinkedInTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="A consulta ao LinkedIn excedeu o tempo limite.",
        ) from exc
    except LinkedInResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível obter resultados válidos do LinkedIn.",
        ) from exc
    except HTMLStructureError as exc:
        logger.warning("A estrutura da página de resultados do LinkedIn mudou.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="O formato da resposta do LinkedIn não é reconhecido.",
        ) from exc

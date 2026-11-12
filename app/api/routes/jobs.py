"""Routes for operations on job collections."""

import logging
from typing import Annotated, Literal

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
    linkedin_client: Annotated[
        AuthenticatedLinkedInClient,
        Depends(get_authenticated_linkedin_client),
    ],
    keywords: str = Query(..., min_length=1),
    geo_id: str = Query("90009574", min_length=1),
    f_tpr: Literal["r86400", "r604800", "r2592000"] = Query(
        "r2592000",
        alias="f_TPR",
    ),
    start: int = Query(0, ge=0),
) -> JobSearchResponse:
    """Searches LinkedIn jobs and returns structured cards and pagination data."""

    if not keywords.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O parâmetro keywords não pode conter apenas espaços.",
        )

    try:
        return await JobSearchService(linkedin_client).search(keywords, geo_id, f_tpr, start)
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

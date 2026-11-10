"""Rotas para operações sobre uma vaga específica."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.clients.public_client import (
    PublicJobNotFoundError,
    PublicLinkedInClient,
    PublicResponseError,
    PublicServiceUnavailableError,
    PublicTimeoutError,
)
from app.core.dependencies import get_job_cache, get_public_linkedin_client
from app.parsers.linkedin_job_details import (
    JobDetailHTMLStructureError,
    JobDetailNotFoundError,
)
from app.ports.job_cache import JobCache
from app.schemas.jobs import JobDetailResponse
from app.services.job_details import JobDetailService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["job"])


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job_details(
    job_id: str = Path(..., min_length=1, pattern=r"^[0-9]+$"),
    refresh: bool = Query(False),
    public_client: PublicLinkedInClient = Depends(get_public_linkedin_client),
    cache: JobCache = Depends(get_job_cache),
) -> JobDetailResponse:
    """Retorna os detalhes públicos estruturados de uma vaga do LinkedIn."""

    try:
        return await JobDetailService(public_client, cache).get_job(job_id, refresh)
    except (PublicJobNotFoundError, JobDetailNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A vaga não existe ou não está mais disponível.",
        ) from exc
    except PublicServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O serviço público do LinkedIn está indisponível.",
        ) from exc
    except PublicTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="A consulta ao LinkedIn excedeu o tempo limite.",
        ) from exc
    except (PublicResponseError, JobDetailHTMLStructureError) as exc:
        logger.warning("Não foi possível interpretar os detalhes retornados pelo LinkedIn.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="O LinkedIn retornou um formato de vaga inválido.",
        ) from exc

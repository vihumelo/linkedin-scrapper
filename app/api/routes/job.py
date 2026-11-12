"""Routes for operations on a specific job."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.clients.authenticated_client import (
    AuthenticatedLinkedInClient,
    LinkedInAuthenticationError,
    LinkedInCredentialsError,
    LinkedInJobNotFoundError,
    LinkedInResponseError,
    LinkedInServiceUnavailableError,
    LinkedInTimeoutError,
)
from app.core.dependencies import get_authenticated_linkedin_client, get_job_cache
from app.parsers.linkedin_voyager_job_details import JobDetailVoyagerStructureError
from app.ports.job_cache import JobCache
from app.schemas.jobs import JobDetailResponse
from app.services.job_details import JobDetailService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/job", tags=["job"])


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job_details(
    linkedin_client: Annotated[
        AuthenticatedLinkedInClient,
        Depends(get_authenticated_linkedin_client),
    ],
    cache: Annotated[JobCache, Depends(get_job_cache)],
    job_id: str = Path(..., min_length=1, pattern=r"^[0-9]+$"),
    refresh: bool = Query(False),
) -> JobDetailResponse:
    """Returns structured details for a LinkedIn job."""

    try:
        return await JobDetailService(linkedin_client, cache).get_job(job_id, refresh)
    except LinkedInJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A vaga não existe ou não está mais disponível.",
        ) from exc
    except (LinkedInCredentialsError, LinkedInServiceUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O serviço autenticado do LinkedIn está indisponível.",
        ) from exc
    except LinkedInTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="A consulta ao LinkedIn excedeu o tempo limite.",
        ) from exc
    except LinkedInAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="O LinkedIn recusou a autenticação configurada.",
        ) from exc
    except (LinkedInResponseError, JobDetailVoyagerStructureError) as exc:
        logger.warning("Não foi possível interpretar os detalhes retornados pelo LinkedIn.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="O LinkedIn retornou um formato de vaga inválido.",
        ) from exc

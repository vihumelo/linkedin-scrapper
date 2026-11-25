"""Routes for operations on LinkedIn companies."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.clients.linkedin_session import (
    LinkedInAuthenticationError,
    LinkedInCredentialsError,
    LinkedInResponseError,
    LinkedInServiceUnavailableError,
    LinkedInTimeoutError,
)
from app.clients.linkedin_voyager_client import LinkedInVoyagerClient, VoyagerNotFoundError
from app.core.dependencies import get_linkedin_voyager_client
from app.parsers.linkedin_voyager_companies import CompanySearchStructureError
from app.schemas.companies import CompanySearchResponse
from app.services.company_search import CompanySearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/search", response_model=CompanySearchResponse)
async def search_companies(
    voyager_client: Annotated[
        LinkedInVoyagerClient,
        Depends(get_linkedin_voyager_client),
    ],
    name: str = Query(..., min_length=1),
    start: int = Query(0, ge=0),
) -> CompanySearchResponse:
    """Searches LinkedIn companies by name and returns their IDs for job searches."""

    if not name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The name parameter must not contain only whitespace.",
        )

    try:
        return await CompanySearchService(voyager_client).search(name, start)
    except (LinkedInCredentialsError, LinkedInServiceUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The authenticated LinkedIn service is unavailable.",
        ) from exc
    except LinkedInTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The LinkedIn request exceeded the time limit.",
        ) from exc
    except LinkedInAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LinkedIn rejected the configured authentication.",
        ) from exc
    except (VoyagerNotFoundError, LinkedInResponseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not obtain valid results from LinkedIn.",
        ) from exc
    except CompanySearchStructureError as exc:
        logger.warning("The LinkedIn company search response structure was not recognized.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LinkedIn response format is not recognized.",
        ) from exc

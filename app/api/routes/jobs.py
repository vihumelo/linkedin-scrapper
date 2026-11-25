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
    keywords: str | None = Query(None, min_length=1),
    company_id: str | None = Query(None, pattern=r"^[0-9]+$"),
    geo_id: str = Query("90009574", min_length=1),
    f_tpr: Literal["r86400", "r604800", "r2592000"] = Query(
        "r2592000",
        alias="f_TPR",
    ),
    start: int = Query(0, ge=0),
) -> JobSearchResponse:
    """Searches LinkedIn jobs and returns structured cards and pagination data."""

    if keywords is not None and not keywords.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The keywords parameter must not contain only whitespace.",
        )
    if keywords is None and company_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either keywords or company_id to search.",
        )

    try:
        return await JobSearchService(linkedin_client).search(
            keywords,
            geo_id,
            f_tpr,
            start,
            company_id=company_id,
        )
    except LinkedInCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The LinkedIn integration is not configured.",
        ) from exc
    except LinkedInAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LinkedIn rejected the configured authentication.",
        ) from exc
    except LinkedInTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The LinkedIn request exceeded the time limit.",
        ) from exc
    except LinkedInResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not obtain valid results from LinkedIn.",
        ) from exc
    except HTMLStructureError as exc:
        logger.warning("The LinkedIn search results page structure has changed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LinkedIn response format is not recognized.",
        ) from exc

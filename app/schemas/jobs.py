"""Pydantic models for job searches and responses."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class JobQuery(BaseModel):
    """Parameters actually used in the job search."""

    model_config = ConfigDict(extra="forbid")

    keywords: str | None
    company_id: str | None = None
    geo_id: str
    f_tpr: Literal["r86400", "r604800", "r2592000"]


class JobPagination(BaseModel):
    """Known information about the results page."""

    model_config = ConfigDict(extra="forbid")

    start: int
    count: int
    next_start: int | None
    has_next: bool | None


class JobListing(BaseModel):
    """Job extracted from the LinkedIn results page."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str | None
    company: str | None
    location: str | None
    url: str | None


class JobSearchResponse(BaseModel):
    """Structured response for a job search."""

    model_config = ConfigDict(extra="forbid")

    query: JobQuery
    pagination: JobPagination
    jobs: list[JobListing]


class JobDetail(JobListing):
    """Additional data extracted from a LinkedIn job posting."""

    posted: str | None = None
    seniority_level: str | None = None
    employment_type: str | None = None
    workplace_type: str | None = None
    industry: str | None = None
    description_text: str | None = None
    job_state: str | None = None
    closed_at: str | None = None
    expires_at: str | None = None
    application_url: str | None = None


class JobDetailResponse(BaseModel):
    """Structured response from the authenticated LinkedIn job details endpoint."""

    model_config = ConfigDict(extra="forbid")

    is_cached: bool
    job: JobDetail

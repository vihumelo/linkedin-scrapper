"""Pydantic models for company searches and responses."""

from pydantic import BaseModel, ConfigDict


class CompanyQuery(BaseModel):
    """Parameters actually used in the company search."""

    model_config = ConfigDict(extra="forbid")

    name: str
    start: int


class CompanyPagination(BaseModel):
    """Known information about the company results page."""

    model_config = ConfigDict(extra="forbid")

    start: int
    count: int
    total: int | None
    next_start: int | None
    has_next: bool | None


class CompanyListing(BaseModel):
    """Company extracted from the LinkedIn search results."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str | None
    industry_location: str | None
    followers: str | None
    url: str | None


class CompanySearchResponse(BaseModel):
    """Structured response for a company search."""

    model_config = ConfigDict(extra="forbid")

    query: CompanyQuery
    pagination: CompanyPagination
    companies: list[CompanyListing]

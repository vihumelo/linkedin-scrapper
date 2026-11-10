"""Modelos Pydantic para busca e resposta de vagas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class JobQuery(BaseModel):
    """Parâmetros efetivamente utilizados na busca de vagas."""

    model_config = ConfigDict(extra="forbid")

    keywords: str
    geo_id: str


class JobPagination(BaseModel):
    """Informações conhecidas sobre a página de resultados."""

    model_config = ConfigDict(extra="forbid")

    start: int
    count: int
    next_start: int | None
    has_next: bool | None


class JobListing(BaseModel):
    """Vaga extraída da página de resultados do LinkedIn."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str | None
    company: str | None
    location: str | None
    url: str | None


class JobSearchResponse(BaseModel):
    """Resposta estruturada da busca de vagas."""

    model_config = ConfigDict(extra="forbid")

    query: JobQuery
    pagination: JobPagination
    jobs: list[JobListing]


class JobDetail(JobListing):
    """Dados adicionais extraídos da página pública de uma vaga."""

    posted_text: str | None = None
    seniority_level: str | None = None
    employment_type: str | None = None
    industry: str | None = None
    description_text: str | None = None
    description_html: str | None = None


class JobDetailResponse(BaseModel):
    """Resposta estruturada do endpoint público de detalhes da vaga."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["linkedin_jobs_guest"] = "linkedin_jobs_guest"
    job: JobDetail

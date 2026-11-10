"""Orquestra a consulta ao LinkedIn e a extração dos resultados."""

from app.clients.authenticated_client import AuthenticatedLinkedInClient
from app.parsers.linkedin_jobs import parse_job_search_html
from app.schemas.jobs import (
    JobPagination,
    JobQuery,
    JobSearchResponse,
)


class JobSearchService:
    """Coordena a busca externa, o parsing e a montagem da resposta."""

    def __init__(self, linkedin_client: AuthenticatedLinkedInClient) -> None:
        """Armazena o cliente utilizado para consultar o LinkedIn."""

        self._linkedin_client = linkedin_client

    async def search(self, keywords: str, geo_id: str, start: int) -> JobSearchResponse:
        """Busca vagas e produz a resposta validada da API."""

        html = await self._linkedin_client.search_jobs(keywords, geo_id, start)
        jobs, has_next = parse_job_search_html(html, start)
        count = len(jobs)
        next_start = start + count if has_next is True else None
        return JobSearchResponse(
            query=JobQuery(keywords=keywords, geo_id=geo_id),
            pagination=JobPagination(
                start=start,
                count=count,
                next_start=next_start,
                has_next=has_next,
            ),
            jobs=jobs,
        )

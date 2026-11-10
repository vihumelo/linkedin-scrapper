"""Testes offline do cliente HTTP público do LinkedIn."""

import asyncio

import httpx
import pytest

from app.clients.public_client import PublicLinkedInClient, PublicServiceUnavailableError


@pytest.mark.parametrize("job_id", ["١٢٣", "１２３"])
def test_public_client_rejects_unicode_decimal_id(job_id: str) -> None:
    """Rejeita IDs não ASCII antes de enviar uma requisição HTTP."""

    def fail_if_called(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"Não deveria enviar uma requisição para {request.url}.")

    async def call_client() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail_if_called)) as http_client:
            public_client = PublicLinkedInClient(http_client)
            with pytest.raises(ValueError):
                await public_client.get_job_details_html(job_id)

    asyncio.run(call_client())


def test_public_client_logs_upstream_status_and_duration(caplog) -> None:
    """Registra status e duração da origem ao receber uma resposta de erro."""

    def return_rate_limit(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"content-type": "text/html"}, request=request)

    async def call_client() -> None:
        transport = httpx.MockTransport(return_rate_limit)
        async with httpx.AsyncClient(transport=transport) as http_client:
            public_client = PublicLinkedInClient(http_client)
            with pytest.raises(PublicServiceUnavailableError):
                await public_client.get_job_details_html("4486249045")

    with caplog.at_level("INFO"):
        asyncio.run(call_client())

    record = next(
        item for item in caplog.records if getattr(item, "event", None) == "upstream.response"
    )
    assert record.integration == "linkedin_job_details_guest"
    assert record.upstream_status == 429
    assert record.duration_ms >= 0

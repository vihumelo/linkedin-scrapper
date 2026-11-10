"""Testes do parser HTML de cartões de vagas."""

import pytest

from app.parsers.linkedin_jobs import HTMLStructureError, parse_job_search_html


def test_parse_componentkey_cards_and_deduplicate_ids() -> None:
    """Extrai os campos dos cartões modernos e elimina IDs repetidos."""

    html = """
    <html><body>
      <div componentkey="job-card-component-ref-123">
        <div componentkey="job-card-component-ref-123">
          <p><span aria-hidden="true">Título original</span></p>
          <p>Empresa</p><p>São Paulo, Brasil</p>
        </div>
      </div>
      <div componentkey="job-card-component-ref-456">
        <p><span aria-hidden="true">Outra vaga</span></p>
        <p>Outra empresa</p><p>Recife, Brasil</p>
      </div>
      <nav><a rel="next" href="?start=25">Próxima</a></nav>
    </body></html>
    """

    jobs, has_next = parse_job_search_html(html, start=0)

    assert len(jobs) == 2
    assert jobs[0].model_dump() == {
        "id": "123",
        "title": "Título original",
        "company": "Empresa",
        "location": "São Paulo, Brasil",
        "url": "https://www.linkedin.com/jobs/view/123/",
    }
    assert has_next is True


def test_parse_legacy_cards_and_unknown_pagination() -> None:
    """Lê cartões sem componentkey e mantém paginação desconhecida como nula."""

    html = """
    <div data-entity-urn="urn:li:jobPosting:789">
      <h3>Técnica de laboratório</h3><h4>Laboratório Central</h4>
      <span data-testid="job-location">Curitiba, Brasil</span>
    </div>
    """

    jobs, has_next = parse_job_search_html(html, start=25)

    assert jobs[0].id == "789"
    assert jobs[0].title == "Técnica de laboratório"
    assert jobs[0].company == "Laboratório Central"
    assert jobs[0].location == "Curitiba, Brasil"
    assert has_next is None


def test_empty_state_is_valid_but_unknown_html_is_an_error() -> None:
    """Aceita estado explícito sem resultados e sinaliza markup não reconhecido."""

    jobs, has_next = parse_job_search_html("<p>Nenhuma vaga encontrada.</p>", start=0)

    assert jobs == []
    assert has_next is None
    with pytest.raises(HTMLStructureError):
        parse_job_search_html("<html><body>conteúdo inesperado</body></html>", start=0)


def test_detects_next_page_from_active_and_last_page_indicators() -> None:
    """Identifica páginas seguintes pelos indicadores numerados do HTML real."""

    html = """
    <div componentkey="job-card-component-ref-123">
      <p><span aria-hidden="true">Vaga de teste</span></p>
      <p>Empresa</p><p>São Paulo, Brasil</p>
    </div>
    <ul data-testid="pagination-controls-list">
      <li><button data-testid="pagination-indicator-0" aria-label="Página 1"
                  aria-current="true">1</button></li>
      <li><button data-testid="pagination-indicator-1" aria-label="Página 2"
                  aria-current="false">2</button></li>
      <li><button data-testid="pagination-indicator-2" aria-label="Página 3"
                  aria-current="false">3</button></li>
    </ul>
    """

    jobs, has_next = parse_job_search_html(html, start=0)

    assert jobs
    assert has_next is True


def test_reports_no_next_page_when_active_indicator_is_last() -> None:
    """Retorna falso quando a página ativa é a última indicada pela paginação."""

    html = """
    <div componentkey="job-card-component-ref-123">
      <p><span aria-hidden="true">Vaga de teste</span></p>
      <p>Empresa</p><p>São Paulo, Brasil</p>
    </div>
    <ul data-testid="pagination-controls-list">
      <li><button data-testid="pagination-indicator-0" aria-label="Página 1"
                  aria-current="false">1</button></li>
      <li><button data-testid="pagination-indicator-1" aria-label="Página 2"
                  aria-current="false">2</button></li>
      <li><button data-testid="pagination-indicator-2" aria-label="Página 3"
                  aria-current="true">3</button></li>
    </ul>
    """

    _, has_next = parse_job_search_html(html, start=50)

    assert has_next is False


def test_rejects_card_with_only_status_text() -> None:
    """Não interpreta textos de status como título, empresa ou localização."""

    html = """
    <div componentkey="job-card-component-ref-987">
      <p>Avaliando candidaturas</p>
      <p>Visto</p>
      <p>Candidatura simplificada</p>
    </div>
    """

    with pytest.raises(HTMLStructureError):
        parse_job_search_html(html, start=0)


@pytest.mark.parametrize("remaining_value", ["Empresa Exemplo", "São Paulo, Brasil"])
def test_rejects_ambiguous_company_or_location_value(remaining_value: str) -> None:
    """Rejeita um único campo sem marcador que pode ser empresa ou localização."""

    html = f"""
    <div componentkey="job-card-component-ref-654">
      <p><span aria-hidden="true">Vaga de teste</span></p>
      <p>{remaining_value}</p>
    </div>
    """

    with pytest.raises(HTMLStructureError):
        parse_job_search_html(html, start=0)


def test_rejects_posting_age_as_location_when_location_is_missing() -> None:
    """Não interpreta a idade da publicação como localização quando ela está ausente."""

    html = """
    <div componentkey="job-card-component-ref-321">
      <p><span aria-hidden="true">Vaga de teste</span></p>
      <p>Empresa Exemplo</p>
      <p>há 1 mês</p>
    </div>
    """

    with pytest.raises(HTMLStructureError):
        parse_job_search_html(html, start=0)


@pytest.mark.parametrize(
    "identifier_attribute",
    [
        'componentkey="job-card-component-ref-١٢٣"',
        'data-entity-urn="urn:li:jobPosting:١٢٣"',
    ],
)
def test_rejects_unicode_digits_in_job_ids(identifier_attribute: str) -> None:
    """Rejeita IDs com algarismos Unicode nas duas estruturas de cartão reconhecidas."""

    html = f"""
    <div {identifier_attribute}>
      <p><span aria-hidden="true">Vaga de teste</span></p>
      <p>Empresa Exemplo</p>
      <p>São Paulo, Brasil</p>
    </div>
    """

    with pytest.raises(HTMLStructureError):
        parse_job_search_html(html, start=0)

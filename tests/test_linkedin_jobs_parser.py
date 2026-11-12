"""Tests for the job card HTML parser."""

from pathlib import Path

import pytest

from app.parsers.linkedin_jobs import HTMLStructureError, parse_job_search_html

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "linkedin_job_search.html"


def test_parse_full_sanitized_real_job_search_response() -> None:
    """Parses all job cards and pagination from a full sanitized search response."""

    html = FIXTURE_PATH.read_text(encoding="utf-8")
    jobs, has_next = parse_job_search_html(html, start=0)

    assert len(jobs) == 25
    assert len({job.id for job in jobs}) == 25
    assert all(job.company == "EMPRESA REDIGIDA" for job in jobs)
    assert all(job.title for job in jobs)
    assert has_next is True
    assert "EMPRESA REDIGIDA" in html
    assert "linkedin.com" not in html.casefold()


def test_parse_componentkey_cards_and_deduplicate_ids() -> None:
    """Extracts fields from modern cards and removes duplicate IDs."""

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
    """Reads cards without a componentkey and keeps unknown pagination as None."""

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
    """Accepts an explicit no-results state and flags unrecognized markup."""

    jobs, has_next = parse_job_search_html("<p>Nenhuma vaga encontrada.</p>", start=0)

    assert jobs == []
    assert has_next is None
    with pytest.raises(HTMLStructureError):
        parse_job_search_html("<html><body>conteúdo inesperado</body></html>", start=0)


def test_detects_next_page_from_active_and_last_page_indicators() -> None:
    """Identifies subsequent pages using numbered indicators from real HTML."""

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
    """Returns False when the active page is the last one shown in pagination."""

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
    """Does not interpret status messages as the title, company, or location."""

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
    """Rejects a single unmarked field that could be either the company or location."""

    html = f"""
    <div componentkey="job-card-component-ref-654">
      <p><span aria-hidden="true">Vaga de teste</span></p>
      <p>{remaining_value}</p>
    </div>
    """

    with pytest.raises(HTMLStructureError):
        parse_job_search_html(html, start=0)


def test_rejects_posting_age_as_location_when_location_is_missing() -> None:
    """Does not treat the posting age as the location when the location is absent."""

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
    """Rejects IDs containing Unicode digits in both recognized card structures."""

    html = f"""
    <div {identifier_attribute}>
      <p><span aria-hidden="true">Vaga de teste</span></p>
      <p>Empresa Exemplo</p>
      <p>São Paulo, Brasil</p>
    </div>
    """

    with pytest.raises(HTMLStructureError):
        parse_job_search_html(html, start=0)

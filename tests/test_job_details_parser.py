"""Testes do parser de detalhes baseado em um trecho HTML real do LinkedIn."""

from pathlib import Path

import pytest

from app.parsers.linkedin_job_details import (
    JobDetailHTMLStructureError,
    parse_job_detail_html,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "linkedin_job_detail.html"


def test_parse_real_job_detail_html() -> None:
    """Extrai campos e critérios do HTML real preservado como fixture."""

    html = FIXTURE_PATH.read_text(encoding="utf-8")
    job = parse_job_detail_html(html, "4486249045")

    assert job.id == "4486249045"
    assert job.title == "Técnico em Engenharia Clinica"
    assert job.company == "CALIBRAMED ENGENHARIA LTDA"
    assert job.location == "São Paulo, Brasil"
    assert job.posted_text == "Há 4 dias"
    assert job.seniority_level == "Assistente"
    assert job.employment_type == "Tempo integral"
    assert job.industry == "Hospitais e atividades de atenção à saúde humana"
    assert job.description_text is not None and len(job.description_text) > 500
    assert job.description_html is not None and "<p>" in job.description_html
    assert "31 candidaturas" not in (job.location or "")


def test_rejects_partial_markup_with_only_posted_time() -> None:
    """Rejeita markup parcial que não contém nenhum campo central da vaga."""

    html = '<span class="posted-time-ago__text">Há 4 dias</span>'

    with pytest.raises(JobDetailHTMLStructureError):
        parse_job_detail_html(html, "4486249045")


def test_accepts_recognized_job_with_optional_fields_missing() -> None:
    """Mantém campos opcionais nulos quando a página contém um título válido."""

    html = '<h2 class="topcard__title">Vaga reconhecida</h2>'

    job = parse_job_detail_html(html, "4486249045")

    assert job.title == "Vaga reconhecida"
    assert job.company is None
    assert job.location is None
    assert job.description_text is None
    assert job.description_html is None

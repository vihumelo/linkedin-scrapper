"""Extracts job details from a public LinkedIn job page."""

import re
import unicodedata

from bs4 import BeautifulSoup, Tag

from app.schemas.jobs import JobDetail

JOB_NOT_FOUND_PATTERN = re.compile(
    r"(job (?:is )?no longer available|job not found|no longer accepting applications|"
    r"vaga (?:não|nao) encontrada|vaga (?:não|nao) está mais disponível|"
    r"vaga (?:não|nao) aceita mais candidaturas|vaga indisponível)",
    re.IGNORECASE,
)
CRITERION_FIELDS = {
    "seniority_level": {"nível de experiência", "seniority level"},
    "employment_type": {"tipo de emprego", "tipo de contratação", "employment type"},
    "industry": {"setores", "industry"},
}
APPLICANT_COUNT_PATTERN = re.compile(
    r"^\s*[\d.,]+\s+(?:candidaturas?|applicants?|people clicked apply)\b",
    re.IGNORECASE,
)


class JobDetailHTMLStructureError(ValueError):
    """Indicates that the HTML does not match a recognized job page."""


class JobDetailNotFoundError(ValueError):
    """Indicates that the HTML reports the job is no longer available."""


def parse_job_detail_html(html: str, job_id: str) -> JobDetail:
    """Extracts known job fields without analyzing or summarizing their content."""

    soup = BeautifulSoup(html, "lxml")
    title_node = _select_one(soup, ".topcard__title", '[itemprop="title"]')
    company_node = _select_one(
        soup,
        ".topcard__org-name-link",
        '[itemprop="hiringOrganization"]',
    )
    location = _extract_location(soup)
    posted_node = _select_one(soup, ".posted-time-ago__text", "time[datetime]")
    description_node = _select_one(soup, ".show-more-less-html__markup", '[itemprop="description"]')
    criteria_nodes = soup.select(".description__job-criteria-item")
    title = _clean_text(title_node)
    description_text = _clean_text(description_node)

    if title is None and description_text is None:
        page_text = soup.get_text(" ", strip=True)
        if JOB_NOT_FOUND_PATTERN.search(page_text):
            raise JobDetailNotFoundError("A vaga não existe ou não está mais disponível.")
        raise JobDetailHTMLStructureError("A página não contém campos reconhecidos de uma vaga.")

    criteria = _extract_criteria(criteria_nodes)
    description_html = None
    if description_node is not None:
        html_content = description_node.decode_contents(formatter="html")
        description_html = html_content or None

    return JobDetail(
        id=job_id,
        title=title,
        company=_clean_text(company_node),
        location=location,
        url=f"https://www.linkedin.com/jobs/view/{job_id}/",
        posted_text=_clean_text(posted_node),
        seniority_level=criteria.get("seniority_level"),
        employment_type=criteria.get("employment_type"),
        industry=criteria.get("industry"),
        description_text=description_text,
        description_html=description_html,
    )


def _select_one(soup: BeautifulSoup, *selectors: str) -> Tag | None:
    """Returns the first element found among known semantic selectors."""

    for selector in selectors:
        if node := soup.select_one(selector):
            return node
    return None


def _clean_text(node: Tag | None) -> str | None:
    """Returns visible text with normalized whitespace while preserving words and punctuation."""

    if node is None:
        return None
    text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
    return text or None


def _extract_location(soup: BeautifulSoup) -> str | None:
    """Selects the location and discards the applicant count from the same block."""

    for selector in ("[data-test-job-location]", '[data-testid*="location"]'):
        if node := soup.select_one(selector):
            if value := _clean_text(node):
                return value

    for node in soup.select(".topcard__flavor--bullet"):
        value = _clean_text(node)
        if value and not APPLICANT_COUNT_PATTERN.search(value):
            return value
    return None


def _extract_criteria(nodes: list[Tag]) -> dict[str, str]:
    """Maps known criteria from the labels displayed on the page."""

    criteria: dict[str, str] = {}
    for node in nodes:
        label_node = node.find(["h2", "h3", "h4"])
        value_node = node.find(["span", "p"])
        label = _normalize_label(_clean_text(label_node))
        value = _clean_text(value_node)
        if not label or not value:
            continue
        for field, labels in CRITERION_FIELDS.items():
            if label in {_normalize_label(item) for item in labels}:
                criteria[field] = value
                break
    return criteria


def _normalize_label(value: str | None) -> str:
    """Normalizes accents and case to compare localized criteria labels."""

    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char)).strip()

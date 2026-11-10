"""Extracts jobs and pagination data from LinkedIn HTML."""

import re
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag

from app.schemas.jobs import JobListing

JOB_COMPONENT_PATTERN = re.compile(r"job-card-component-ref-([0-9]+)")
JOB_URN_PATTERN = re.compile(r"urn:li:jobPosting:([0-9]+)")
NEXT_CONTROL_PATTERN = re.compile(
    r"\b(next|next page|próxima|seguinte|ver mais vagas|mostrar mais vagas|load more)\b",
    re.IGNORECASE,
)
EMPTY_RESULTS_PATTERN = re.compile(
    r"(no jobs found|no results found|nenhuma vaga|não encontramos vagas|sem resultados)",
    re.IGNORECASE,
)
JOB_CARD_STATUS_TEXTS = {
    "actively reviewing applicants",
    "actively reviewing applications",
    "avaliando candidaturas",
    "candidatura simplificada",
    "easy apply",
    "promoted",
    "promovida",
    "visto",
    "viewed",
}
APPLICANT_COUNT_PATTERN = re.compile(
    r"^\s*[\d.,]+\s+(?:candidaturas?|applicants?)\b",
    re.IGNORECASE,
)
POSTED_TEXT_PATTERN = re.compile(
    r"^(?:(?:há\s+)?\d+\s+(?:segundos?|minutos?|horas?|dias?|semanas?|meses?|mês|anos?)|"
    r"\d+\s+(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)(?:\s+ago)?|"
    r"hoje|ontem|today|yesterday)\b",
    re.IGNORECASE,
)


class HTMLStructureError(ValueError):
    """Indicates that the page does not contain a recognized results structure."""


def parse_job_search_html(html: str, start: int) -> tuple[list[JobListing], bool | None]:
    """Extracts unique jobs and the next-page indicator when it can be determined."""

    soup = BeautifulSoup(html, "lxml")
    cards = _find_job_cards(soup)
    if not cards and not _has_explicit_empty_state(soup):
        raise HTMLStructureError("A página não contém cartões de vagas reconhecidos.")

    jobs: list[JobListing] = []
    seen_ids: set[str] = set()
    for job_id, card in cards:
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        jobs.append(_parse_job_card(job_id, card))

    return jobs, _find_has_next(soup, start)


def _find_job_cards(soup: BeautifulSoup) -> list[tuple[str, Tag]]:
    """Finds job cards using semantic identifiers present in the HTML."""

    cards: list[tuple[str, Tag]] = []
    seen_ids: set[str] = set()
    for element in soup.find_all(attrs={"componentkey": JOB_COMPONENT_PATTERN}):
        match = JOB_COMPONENT_PATTERN.fullmatch(str(element.get("componentkey", "")))
        if match and match.group(1) not in seen_ids:
            job_id = match.group(1)
            cards.append((job_id, element))
            seen_ids.add(job_id)

    if cards:
        return cards

    for element in soup.find_all(attrs={"data-entity-urn": JOB_URN_PATTERN}):
        match = JOB_URN_PATTERN.search(str(element.get("data-entity-urn", "")))
        if match and match.group(1) not in seen_ids:
            job_id = match.group(1)
            cards.append((job_id, element))
            seen_ids.add(job_id)
    return cards


def _parse_job_card(job_id: str, card: Tag) -> JobListing:
    """Extracts card fields after validating the title markup."""

    paragraphs = card.find_all("p")
    first_paragraph_index = next(
        (index for index, paragraph in enumerate(paragraphs) if _text_value(paragraph)),
        None,
    )
    title_span = (
        paragraphs[first_paragraph_index].find("span", attrs={"aria-hidden": "true"})
        if first_paragraph_index is not None
        else None
    )

    if title_span is not None and _text_value(title_span):
        title_index = first_paragraph_index
        title = _text_value(title_span)
        field_values = [
            value
            for paragraph in paragraphs[title_index + 1 :]
            if (value := _text_value(paragraph)) and not _is_job_card_metadata(value)
        ]
        if len(field_values) == 1:
            raise HTMLStructureError(
                "O cartão contém um único campo sem marcador para empresa ou localização."
            )
        company = field_values[0] if field_values else None
        location = field_values[1] if len(field_values) > 1 else None
    else:
        headings = card.find_all(["h1", "h2", "h3", "h4"])
        title = _text_value(headings[0]) if headings else None
        company = _text_value(headings[1]) if len(headings) > 1 else None
        location = _find_semantic_location(card)

    if title is None:
        raise HTMLStructureError("O cartão não contém um título reconhecível.")

    return JobListing(
        id=job_id,
        title=title,
        company=company,
        location=location,
        url=f"https://www.linkedin.com/jobs/view/{job_id}/",
    )


def _is_job_card_metadata(value: str) -> bool:
    """Identifies known status messages that are not job fields."""

    normalized = value.casefold().strip()
    return (
        normalized in JOB_CARD_STATUS_TEXTS
        or bool(APPLICANT_COUNT_PATTERN.match(value))
        or bool(POSTED_TEXT_PATTERN.match(value))
    )


def _text_values(elements: Iterable[Tag]) -> list[str]:
    """Returns the non-empty text values from a sequence of elements."""

    return [value for element in elements if (value := _text_value(element)) is not None]


def _text_value(element: Tag | None) -> str | None:
    """Gets visible text and trims surrounding whitespace without changing its content."""

    if element is None:
        return None
    value = element.get_text(" ", strip=True)
    return value or None


def _find_semantic_location(card: Tag) -> str | None:
    """Finds an element whose semantic attribute identifies the location."""

    for element in card.find_all(["span", "div"], attrs={"data-testid": True}):
        test_id = str(element.get("data-testid", ""))
        if "location" in test_id.casefold():
            return _text_value(element)
    for element in card.find_all(["span", "div"], attrs={"aria-label": True}):
        label = str(element.get("aria-label", ""))
        if "location" in label.casefold() or "localização" in label.casefold():
            return _text_value(element)
    for element in card.find_all(["span", "div"], attrs={"class": True}):
        classes = element.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()
        if any(value in {"location", "job-search-card__location"} for value in classes):
            return _text_value(element)
    return None


def _has_explicit_empty_state(soup: BeautifulSoup) -> bool:
    """Distinguishes a search with no results from an unexpected HTML page."""

    text = soup.get_text(" ", strip=True)
    return bool(EMPTY_RESULTS_PATTERN.search(text))


def _find_has_next(soup: BeautifulSoup, start: int) -> bool | None:
    """Determines whether another page exists from pagination indicators or controls."""

    roots = _find_pagination_roots(soup)
    states = [state for root in roots if (state := _page_indicator_state(root)) is not None]
    if states:
        return states[0] if all(state == states[0] for state in states) else None

    for root in roots:
        state = _find_next_control_state(root, start)
        if state is not None:
            return state

    if _has_rel_next(soup):
        return True
    return None


def _find_pagination_roots(soup: BeautifulSoup) -> list[Tag]:
    """Finds pagination containers by accessible or semantic attributes."""

    roots = soup.select('[data-testid="pagination-controls-list"]')
    if roots:
        return roots

    roots = []
    for element in soup.find_all(["nav", "div", "ul"], attrs={"aria-label": True}):
        label = str(element.get("aria-label", ""))
        if re.search(r"pagination|página|pagina|page", label, re.IGNORECASE):
            roots.append(element)
    return roots


def _page_indicator_state(root: Tag) -> bool | None:
    """Compares the active page with the last page shown in the control."""

    indicators = root.select('[data-testid^="pagination-indicator-"]')
    if not indicators:
        indicators = [
            control
            for control in root.find_all(["a", "button"])
            if control.has_attr("aria-current")
        ]
    if not indicators:
        return None

    numbered_pages = [
        page_number
        for indicator in indicators
        if (page_number := _page_number(indicator)) is not None
    ]
    active_pages = [
        _page_number(indicator)
        for indicator in indicators
        if str(indicator.get("aria-current", "")).casefold() in {"true", "page"}
    ]
    if len(active_pages) != 1 or active_pages[0] is None or not numbered_pages:
        return None

    current_page = active_pages[0]
    last_visible_page = max(numbered_pages)
    if current_page > last_visible_page:
        return None
    return current_page < last_visible_page


def _page_number(indicator: Tag) -> int | None:
    """Extracts the page number from the indicator label, text, or index."""

    for attribute in ("aria-label", "title"):
        label = str(indicator.get(attribute, ""))
        match = re.search(r"(?:page|página|pagina)\s+(\d+)\b", label, re.IGNORECASE)
        if match:
            return int(match.group(1))

    text = _text_value(indicator) or ""
    if re.fullmatch(r"\d+", text):
        return int(text)

    test_id = str(indicator.get("data-testid", ""))
    match = re.fullmatch(r"pagination-indicator-(\d+)", test_id)
    return int(match.group(1)) + 1 if match else None


def _find_next_control_state(root: Tag, start: int) -> bool | None:
    """Reads controls with labels or offsets only within the pagination area."""

    saw_disabled_next = False
    for control in root.find_all(["a", "button"]):
        rel = control.get("rel", [])
        if isinstance(rel, str):
            rel = rel.split()
        labels = " ".join(
            str(control.get(attribute, ""))
            for attribute in ("aria-label", "title", "data-control-name")
        )
        labels = f"{labels} {_text_value(control) or ''}"
        href = str(control.get("href", ""))
        offset = re.search(r"(?:[?&]|&amp;)start=(\d+)", href)
        explicit_next = "next" in {str(value).casefold() for value in rel}
        explicit_next = explicit_next or bool(NEXT_CONTROL_PATTERN.search(labels))
        if offset and int(offset.group(1)) > start:
            explicit_next = True
        if not explicit_next:
            continue

        disabled = (
            control.has_attr("disabled")
            or str(control.get("aria-disabled", "")).casefold() == "true"
        )
        if disabled:
            saw_disabled_next = True
        else:
            return True
    return False if saw_disabled_next else None


def _has_rel_next(soup: BeautifulSoup) -> bool:
    """Recognizes a link explicitly marked as next by its HTML semantics."""

    for link in soup.find_all("a", attrs={"rel": True}):
        rel = link.get("rel", [])
        if isinstance(rel, str):
            rel = rel.split()
        if "next" in {str(value).casefold() for value in rel}:
            return True
    return False

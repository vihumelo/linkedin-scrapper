"""Tests for the authenticated LinkedIn session shared by the clients."""

import httpx
import pytest

from app.clients.linkedin_session import (
    LinkedInCredentialsError,
    LinkedInSession,
    redirected_to_authentication,
)
from app.core.config import Settings


def make_session(li_at: str, jsessionid: str) -> LinkedInSession:
    """Builds a session over an HTTP client that is never used for requests."""

    return LinkedInSession(
        httpx.AsyncClient(),
        Settings(linkedin_li_at=li_at, linkedin_jsessionid=jsessionid),
    )


def test_csrf_token_removes_quotes_from_jsessionid() -> None:
    """Derives the CSRF token from the quoted JSESSIONID cookie value."""

    session = make_session("li-at-test", '"ajax:123"')

    assert session.csrf_token == "ajax:123"


def test_require_credentials_accepts_configured_cookies() -> None:
    """Allows requests when both LinkedIn cookies are configured."""

    make_session("li-at-test", "session-test").require_credentials("test_integration")


@pytest.mark.parametrize(("li_at", "jsessionid"), [("", "session-secret"), ("li-at-secret", "")])
def test_require_credentials_rejects_missing_cookie_without_logging_secrets(
    li_at: str,
    jsessionid: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Fails and logs the integration name when any cookie is missing."""

    session = make_session(li_at, jsessionid)

    with caplog.at_level("ERROR"), pytest.raises(LinkedInCredentialsError):
        session.require_credentials("test_integration")

    record = next(item for item in caplog.records if getattr(item, "event", None))
    assert record.__dict__["integration"] == "test_integration"
    assert record.__dict__["reason"] == "credentials_missing"
    assert "secret" not in caplog.text


@pytest.mark.parametrize(
    ("final_url", "redirect_url", "expected"),
    [
        ("https://www.linkedin.com/jobs/", None, False),
        ("https://www.linkedin.com/authwall?trk=x", None, True),
        ("https://www.linkedin.com/jobs/", "https://www.linkedin.com/checkpoint/lg", True),
        ("https://www.linkedin.com/login", None, True),
    ],
)
def test_redirected_to_authentication_checks_final_url_and_history(
    final_url: str,
    redirect_url: str | None,
    expected: bool,
) -> None:
    """Detects login, authwall, and checkpoint pages in the response or its redirects."""

    history = (
        [httpx.Response(302, request=httpx.Request("GET", redirect_url))]
        if redirect_url is not None
        else []
    )
    response = httpx.Response(
        200,
        request=httpx.Request("GET", final_url),
        history=history,
    )

    assert redirected_to_authentication(response) is expected

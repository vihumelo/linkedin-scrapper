"""Shared pytest configuration, including the opt-in online integration tests."""

import pytest

from app.core.config import Settings


def pytest_addoption(parser: pytest.Parser) -> None:
    """Registers the flag that enables tests calling the real LinkedIn."""

    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run online integration tests that call the real LinkedIn.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skips integration tests unless the --integration flag is given."""

    if config.getoption("--integration"):
        return

    skip_integration = pytest.mark.skip(reason="Online test disabled; run with --integration")
    for item in items:
        if item.get_closest_marker("integration") is not None:
            item.add_marker(skip_integration)


@pytest.fixture
def linkedin_settings() -> Settings:
    """Returns settings with LinkedIn cookies, skipping the test when they are missing."""

    settings = Settings()
    if not settings.linkedin_li_at or not settings.linkedin_jsessionid:
        pytest.skip("LinkedIn authentication cookies are not configured in the environment")
    return settings

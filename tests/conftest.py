"""Shared pytest configuration, including the opt-in online integration tests."""

import pytest

from app.core.config import Settings


def pytest_addoption(parser: pytest.Parser) -> None:
    """Registers the flag that enables tests calling the real LinkedIn."""

    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run only the online integration tests that call the real LinkedIn.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Runs only integration tests with --integration and skips them otherwise."""

    integration_items = [item for item in items if is_integration(item)]

    if config.getoption("--integration"):
        offline_items = [item for item in items if not is_integration(item)]
        if offline_items:
            config.hook.pytest_deselected(items=offline_items)
        items[:] = integration_items
        return

    skip_integration = pytest.mark.skip(reason="Online test disabled; run with --integration")
    for item in integration_items:
        item.add_marker(skip_integration)


def is_integration(item: pytest.Item) -> bool:
    """Tells whether a collected test carries the integration marker."""

    return item.get_closest_marker("integration") is not None


@pytest.fixture
def linkedin_settings() -> Settings:
    """Returns settings with LinkedIn cookies, skipping the test when they are missing."""

    settings = Settings()
    if not settings.linkedin_li_at or not settings.linkedin_jsessionid:
        pytest.skip("LinkedIn authentication cookies are not configured in the environment")
    return settings

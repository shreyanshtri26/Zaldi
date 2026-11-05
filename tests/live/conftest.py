"""Live tests call the Google API: marked ``live`` and skipped when no key is configured."""
import pytest

from zaldi import config


def pytest_collection_modifyitems(items):
    for item in items:
        if "live" in str(item.path.parent):
            item.add_marker(pytest.mark.live)
            if not config.GOOGLE_API_KEY:
                item.add_marker(pytest.mark.skip(reason="GOOGLE_API_KEY not set"))

"""Shared pytest configuration: make the Lab6 root importable from tests."""
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))


def pytest_configure(config):
    """Register custom markers (added by the weather-test author)."""
    config.addinivalue_line(
        "markers", "live: test hits the real network (wttr.in); skipped automatically if offline"
    )

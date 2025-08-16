"""Pytest configuration for market-service."""

import pytest


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--real-ctp",
        action="store_true",
        default=False,
        help="Run real CTP account tests (requires credentials)",
    )


@pytest.fixture
def real_ctp_enabled(request):
    """Check if real CTP tests are enabled"""
    return request.config.getoption("--real-ctp")

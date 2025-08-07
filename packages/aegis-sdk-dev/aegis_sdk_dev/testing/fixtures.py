"""Test fixtures for SDK testing."""

from pydantic import BaseModel


class ServiceFixture(BaseModel):
    """Service fixture for testing."""

    name: str
    url: str

    model_config = {"strict": True}

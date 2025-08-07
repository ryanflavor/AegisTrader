"""Test environment management."""

from pydantic import BaseModel


class TestEnvironment(BaseModel):
    """Test environment configuration."""

    nats_url: str = "nats://localhost:4222"
    service_name: str = "test-service"

    model_config = {"strict": True}

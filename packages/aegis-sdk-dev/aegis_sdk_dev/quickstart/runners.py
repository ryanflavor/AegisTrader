"""Quickstart runners for rapid development."""

from pydantic import BaseModel


class QuickstartRunner(BaseModel):
    """Runner for quickstart operations."""

    service_name: str

    model_config = {"strict": True}

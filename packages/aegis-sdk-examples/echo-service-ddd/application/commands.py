"""Commands for Echo Service application layer.

Commands represent actions that change the state of the system.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Command(BaseModel):
    """Base command class for all commands."""

    correlation_id: str | None = Field(default=None, description="Correlation ID for tracking")


class ProcessEchoCommand(Command):
    """Command to process an echo request."""

    message: str = Field(..., min_length=1, max_length=1000, description="Message to echo")
    mode: str = Field(default="simple", description="Echo mode to use")
    delay: float = Field(default=0.0, ge=0.0, le=10.0, description="Delay for delayed mode")
    transform_type: str | None = Field(default=None, description="Transformation type")
    priority: str = Field(default="normal", description="Message priority")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    request_id: str | None = Field(default=None, description="Request identifier")


class ProcessBatchEchoCommand(Command):
    """Command to process multiple echo requests in batch."""

    requests: list[ProcessEchoCommand] = Field(
        ..., min_length=1, max_length=100, description="List of echo commands to process"
    )
    batch_id: str | None = Field(default=None, description="Batch identifier")
    priority: str = Field(default="normal", description="Batch priority")


class RegisterServiceCommand(Command):
    """Command to register service with monitor-api."""

    service_name: str = Field(..., description="Service name")
    owner: str = Field(..., description="Service owner")
    description: str = Field(..., description="Service description")
    version: str = Field(..., description="Service version")
    instance_id: str = Field(..., description="Instance identifier")
    nats_url: str = Field(..., description="NATS connection URL")


class RefreshRegistrationCommand(Command):
    """Command to refresh service registration."""

    instance_id: str = Field(..., description="Instance identifier to refresh")


class ResetMetricsCommand(Command):
    """Command to reset service metrics."""

    confirm: bool = Field(..., description="Confirmation flag to prevent accidental reset")


class UpdateHealthStatusCommand(Command):
    """Command to update health check status."""

    component: str = Field(..., description="Component name")
    status: bool = Field(..., description="Health status")
    details: str | None = Field(default=None, description="Additional details")

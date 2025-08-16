"""
Event Publisher Adapter for SDK Integration.

This adapter implements the domain's EventPublisher interface
using the AegisSDK's Service.publish_event() functionality.
It translates between domain events and SDK events.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from aegis_sdk.domain.models import Event as SDKEvent
from pydantic import BaseModel, ConfigDict, Field

from domain.shared.events import DomainEvent

if TYPE_CHECKING:
    from aegis_sdk.application.service import Service


class EventPayload(BaseModel):
    """Structured payload for SDK events."""

    model_config = ConfigDict(strict=True)

    event_id: str = Field(description="Unique event identifier")
    occurred_at: str = Field(description="ISO format timestamp")
    aggregate_id: str = Field(description="Aggregate root identifier")
    event_type: str = Field(description="Type of the event")

    # Optional fields based on event type
    gateway_id: str | None = Field(default=None, description="Gateway identifier")
    gateway_type: str | None = Field(default=None, description="Type of gateway")
    session_id: str | None = Field(default=None, description="Session identifier")
    reason: str | None = Field(default=None, description="Reason for event")
    symbol: str | None = Field(default=None, description="Trading symbol")
    exchange: str | None = Field(default=None, description="Exchange name")
    price: float | None = Field(default=None, description="Price value", ge=0)
    volume: int | None = Field(default=None, description="Volume value", ge=0)
    timestamp: str | None = Field(default=None, description="Event timestamp in ISO format")
    subscription_id: str | None = Field(default=None, description="Subscription identifier")
    subscriber_id: str | None = Field(default=None, description="Subscriber identifier")


class SDKEventPublisherAdapter:
    """Adapter that implements EventPublisher using SDK Service."""

    def __init__(self, service: Service):
        """Initialize with SDK Service instance.

        Args:
            service: The SDK Service instance that provides publish_event
        """
        self._service = service

    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event.

        Translates the domain event to SDK event format and publishes it.

        Args:
            event: Domain event to publish
        """
        sdk_event = self._translate_to_sdk_event(event)
        await self._service.publish_event(sdk_event)

    async def publish_batch(self, events: list[DomainEvent]) -> None:
        """Publish multiple domain events.

        Args:
            events: List of domain events to publish
        """
        for event in events:
            await self.publish(event)

    def _translate_to_sdk_event(self, domain_event: DomainEvent) -> SDKEvent:
        """Translate domain event to SDK event format.

        Args:
            domain_event: Domain event to translate

        Returns:
            SDK Event object
        """
        # Build structured payload
        payload_data = {
            "event_id": str(domain_event.event_id),
            "occurred_at": domain_event.occurred_at.isoformat(),
            "aggregate_id": domain_event.aggregate_id,
            "event_type": domain_event.event_type,
        }

        # Map optional fields with proper type conversion
        field_mappings = [
            ("gateway_id", "gateway_id", str),
            ("gateway_type", "gateway_type", str),
            ("session_id", "session_id", lambda x: str(x) if isinstance(x, UUID) else str(x)),
            ("reason", "reason", str),
            ("symbol", "symbol", str),
            ("exchange", "exchange", str),
            ("price", "price", float),
            ("volume", "volume", int),
            (
                "timestamp",
                "timestamp",
                lambda x: x.isoformat() if isinstance(x, datetime) else str(x),
            ),
            (
                "subscription_id",
                "subscription_id",
                lambda x: str(x) if isinstance(x, UUID) else str(x),
            ),
            ("subscriber_id", "subscriber_id", str),
        ]

        for attr_name, payload_key, converter in field_mappings:
            if hasattr(domain_event, attr_name):
                value = getattr(domain_event, attr_name)
                if value is not None:
                    payload_data[payload_key] = converter(value)

        # Validate payload with Pydantic model
        validated_payload = EventPayload(**payload_data)

        # Create SDK event with validated payload
        return SDKEvent(
            domain="market-service",
            event_type=domain_event.event_type,
            payload=validated_payload.model_dump(exclude_none=True),
            source=self._service.instance_id,
        )

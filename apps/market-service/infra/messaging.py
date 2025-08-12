"""Messaging implementation for market-service."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Event:
    """Base event class."""

    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class MessageBus:
    """Simple message bus implementation."""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        """Publish event to subscribers."""
        if event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                await handler(event)


class EventStore:
    """Simple event store."""

    def __init__(self):
        self._events: list[Event] = []

    async def append(self, event: Event) -> None:
        """Append event to store."""
        self._events.append(event)

    async def get_events(self, from_timestamp: datetime = None) -> list[Event]:
        """Get events from store."""
        if from_timestamp:
            return [e for e in self._events if e.timestamp >= from_timestamp]
        return self._events

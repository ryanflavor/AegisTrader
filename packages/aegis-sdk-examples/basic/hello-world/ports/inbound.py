"""Inbound ports (interfaces) for Hello World service."""

from abc import ABC, abstractmethod
from typing import Protocol

from ..domain.models import HelloRequest, HelloResponse, ServiceStatus


class HelloServicePort(Protocol):
    """Inbound port for hello service operations."""

    async def process_hello(self, request: HelloRequest) -> HelloResponse:
        """Process a hello request and return a response."""
        ...

    async def get_status(self) -> ServiceStatus:
        """Get the current service status."""
        ...


class MessageHandlerPort(ABC):
    """Abstract base class for message handlers."""

    @abstractmethod
    async def handle_hello_request(self, data: dict) -> dict:
        """Handle incoming hello request message."""
        pass

    @abstractmethod
    async def handle_status_request(self) -> dict:
        """Handle status request."""
        pass

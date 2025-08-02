"""Message bus interface - Port definition for messaging infrastructure."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from ..domain.models import Command, Event, RPCRequest, RPCResponse


class MessageBusPort(ABC):
    """Abstract interface for message bus operations."""

    @abstractmethod
    async def connect(self, servers: list[str]) -> None:
        """Connect to message bus servers."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from message bus."""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to message bus."""
        ...

    # RPC Operations
    @abstractmethod
    async def register_rpc_handler(
        self, service: str, method: str, handler: Callable[[dict[str, Any]], Any]
    ) -> None:
        """Register an RPC handler."""
        ...

    @abstractmethod
    async def call_rpc(self, request: RPCRequest) -> RPCResponse:
        """Make an RPC call."""
        ...

    # Event Operations
    @abstractmethod
    async def subscribe_event(
        self, pattern: str, handler: Callable, durable: str | None = None
    ) -> None:
        """Subscribe to events matching pattern."""
        ...

    @abstractmethod
    async def publish_event(self, event: Event) -> None:
        """Publish an event."""
        ...

    # Command Operations
    @abstractmethod
    async def register_command_handler(
        self, service: str, command: str, handler: Callable[[Command, Callable], Any]
    ) -> None:
        """Register a command handler with progress callback."""
        ...

    @abstractmethod
    async def send_command(self, command: Command, track_progress: bool = True) -> dict[str, Any]:
        """Send a command with optional progress tracking."""
        ...

    # Service Registration
    @abstractmethod
    async def register_service(self, service_name: str, instance_id: str) -> None:
        """Register service instance."""
        ...

    @abstractmethod
    async def unregister_service(self, service_name: str, instance_id: str) -> None:
        """Unregister service instance."""
        ...

    @abstractmethod
    async def send_heartbeat(self, service_name: str, instance_id: str) -> None:
        """Send service heartbeat."""
        ...

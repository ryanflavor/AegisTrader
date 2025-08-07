"""Port interface for service bus operations.

This port defines the contract for service bus capabilities
including RPC registration and lifecycle management.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import Any


class ServiceBusPort(ABC):
    """Port interface for service bus operations."""

    @abstractmethod
    async def start(self) -> None:
        """Start the service bus connection.

        Raises:
            ConnectionError: If unable to connect to the service bus
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the service bus connection gracefully."""
        ...

    @abstractmethod
    def register_rpc_handler(
        self, method: str, handler: Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]
    ) -> None:
        """Register an RPC handler for a specific method.

        Args:
            method: The RPC method name to handle
            handler: Async function to handle the RPC call

        Raises:
            ValueError: If method is already registered
        """
        ...

    @abstractmethod
    async def call_rpc(
        self, target: str, method: str, params: dict[str, Any], timeout: float = 5.0
    ) -> dict[str, Any]:
        """Call an RPC method on a target service.

        Args:
            target: Target service name
            method: Method to call
            params: Parameters for the method
            timeout: Timeout in seconds

        Returns:
            Response from the RPC call

        Raises:
            TimeoutError: If the call times out
            ConnectionError: If unable to reach the target
        """
        ...

    @abstractmethod
    def get_instance_id(self) -> str:
        """Get the unique instance ID for this service.

        Returns:
            Unique instance identifier
        """
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the service bus is connected.

        Returns:
            True if connected, False otherwise
        """
        ...

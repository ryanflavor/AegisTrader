"""Infrastructure adapter for Aegis SDK service bus.

This adapter implements the ServiceBusPort interface using the Aegis SDK,
providing a concrete implementation that can be swapped out for testing.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from aegis_sdk.application.service import Service
from aegis_sdk.domain.models import RPCRequest

from ..ports.service_bus import ServiceBusPort

logger = logging.getLogger(__name__)


class AegisServiceBusAdapter(ServiceBusPort):
    """Aegis SDK implementation of the service bus port."""

    def __init__(self, service: Service) -> None:
        """Initialize the adapter with an Aegis SDK service.

        Args:
            service: Configured Aegis SDK service instance
        """
        self._service = service
        self._handlers: dict[str, Callable] = {}
        self._is_connected = False

    async def start(self) -> None:
        """Start the service bus connection.

        Raises:
            ConnectionError: If unable to connect to NATS
        """
        try:
            # Register all handlers before starting
            for method, handler in self._handlers.items():
                self._service.rpc(method)(handler)

            # Start the service
            await self._service.start()
            self._is_connected = True
            logger.info(f"Service bus started with instance ID: {self._service.instance_id}")
        except Exception as e:
            logger.error(f"Failed to start service bus: {e}")
            raise ConnectionError(f"Unable to connect to service bus: {e}") from e

    async def stop(self) -> None:
        """Stop the service bus connection gracefully."""
        try:
            if self._is_connected:
                await self._service.stop()
                self._is_connected = False
                logger.info("Service bus stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping service bus: {e}")
            # Don't raise - we want graceful shutdown even if stop fails
            self._is_connected = False

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
        if method in self._handlers:
            raise ValueError(f"RPC handler for method '{method}' is already registered")

        self._handlers[method] = handler

        # If service is already started, register immediately
        if self._is_connected:
            self._service.rpc(method)(handler)

        logger.debug(f"Registered RPC handler for method: {method}")

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
        if not self._is_connected:
            raise ConnectionError("Service bus is not connected")

        try:
            request = RPCRequest(target=target, method=method, params=params, timeout=timeout)

            response = await self._service._bus.call_rpc(request)

            if response.error:
                logger.error(f"RPC call error: {response.error}")
                return {"error": response.error}

            return response.result

        except TimeoutError as e:
            logger.error(f"RPC call timed out: {e}")
            raise
        except Exception as e:
            logger.error(f"RPC call failed: {e}")
            raise ConnectionError(f"Failed to call RPC: {e}") from e

    def get_instance_id(self) -> str:
        """Get the unique instance ID for this service.

        Returns:
            Unique instance identifier
        """
        return self._service.instance_id

    def is_connected(self) -> bool:
        """Check if the service bus is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._is_connected

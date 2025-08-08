"""Infrastructure adapter for Aegis SDK service bus.

This adapter implements the ServiceBusPort interface using the Aegis SDK's NATSAdapter,
providing a concrete implementation that can be swapped out for testing.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from aegis_sdk.domain.models import RPCRequest, RPCResponse
from aegis_sdk.infrastructure import NATSAdapter

from ..ports.service_bus import ServiceBusPort

logger = logging.getLogger(__name__)


class AegisServiceBusAdapter(ServiceBusPort):
    """Aegis SDK implementation of the service bus port using NATSAdapter directly."""

    def __init__(self, nats_adapter: NATSAdapter, service_name: str, instance_id: str) -> None:
        """Initialize the adapter with an Aegis SDK NATS adapter.

        Args:
            nats_adapter: Connected NATS adapter from aegis-sdk
            service_name: Name of the service
            instance_id: Unique instance identifier
        """
        self._nats = nats_adapter
        self._service_name = service_name
        self._instance_id = instance_id
        self._handlers: dict[str, Callable] = {}
        self._is_started = False

    async def start(self) -> None:
        """Start the service bus and register RPC handlers.

        Raises:
            ConnectionError: If unable to start service bus
        """
        try:
            # Register all handlers with NATS adapter
            for method, handler in self._handlers.items():
                await self._nats.register_rpc_handler(
                    service=self._service_name, method=method, handler=handler
                )
                logger.info(f"Registered RPC handler: {self._service_name}.{method}")

            self._is_started = True
            logger.info(
                f"Service bus started for {self._service_name} (instance: {self._instance_id})"
            )
        except Exception as e:
            logger.error(f"Failed to start service bus: {e}")
            raise ConnectionError(f"Unable to start service bus: {e}") from e

    async def stop(self) -> None:
        """Stop the service bus connection gracefully."""
        try:
            if self._is_started:
                # SDK's NATSAdapter handles cleanup internally
                self._is_started = False
                logger.info("Service bus stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping service bus: {e}")
            # Don't raise - we want graceful shutdown even if stop fails
            self._is_started = False

    def register_rpc_handler(
        self,
        method: str,
        handler: Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]],
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
        logger.debug(f"Queued RPC handler for method: {method}")

        # Note: Actual registration happens in start() method

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
        if not self._is_started:
            raise ConnectionError("Service bus is not started")

        try:
            # Create RPC request using SDK models
            request = RPCRequest(
                id=f"{self._instance_id}-{asyncio.get_event_loop().time()}",
                method=method,
                params=params,
                target=target,
            )

            # Call through SDK's NATS adapter
            response: RPCResponse = await asyncio.wait_for(
                self._nats.call_rpc(request), timeout=timeout
            )

            if response.error:
                logger.error(f"RPC call error: {response.error}")
                return {"error": response.error}

            return response.result or {}

        except TimeoutError as e:
            logger.error(f"RPC call timed out after {timeout}s: {e}")
            raise TimeoutError(f"RPC call timed out after {timeout} seconds") from e
        except Exception as e:
            logger.error(f"RPC call failed: {e}")
            raise ConnectionError(f"Failed to call RPC: {e}") from e

    def get_instance_id(self) -> str:
        """Get the unique instance ID for this service.

        Returns:
            Unique instance identifier
        """
        return self._instance_id

    def is_connected(self) -> bool:
        """Check if the service bus is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._is_started and self._nats.is_connected()

"""Service bus adapter for Echo Service using NATS.

This adapter provides service bus functionality without depending on
aegis_sdk.developer, implementing RPC patterns directly with NATS.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from ..ports.service_bus import ServiceBusPort
from .nats_connection_adapter import NATSConnectionAdapter

logger = logging.getLogger(__name__)


class RPCRequest(BaseModel):
    """RPC request model."""

    method: str
    params: dict[str, Any] | None = None
    id: str | None = None


class RPCResponse(BaseModel):
    """RPC response model."""

    result: Any | None = None
    error: dict[str, Any] | None = None
    id: str | None = None


class ServiceBusAdapter(ServiceBusPort):
    """Adapter for service bus operations using NATS.

    This adapter provides RPC functionality over NATS without
    relying on aegis_sdk.developer, implementing the patterns directly.
    """

    def __init__(self, nats_adapter: NATSConnectionAdapter, service_name: str) -> None:
        """Initialize service bus adapter.

        Args:
            nats_adapter: NATS connection adapter
            service_name: Name of this service
        """
        self._nats = nats_adapter
        self._service_name = service_name
        self._handlers: dict[str, Callable] = {}
        self._subscriptions: list[str] = []
        self._is_started = False

    async def start(self) -> None:
        """Start the service bus and subscribe to RPC subjects."""
        if self._is_started:
            logger.warning("Service bus already started")
            return

        try:
            # Subscribe to service-specific RPC subject
            rpc_subject = f"rpc.{self._service_name}"
            sub_id = await self._nats.subscribe(
                rpc_subject,
                self._handle_rpc_request,
                queue=self._service_name,  # Use queue group for load balancing
            )
            self._subscriptions.append(sub_id)

            # Subscribe to broadcast subject (no queue group)
            broadcast_subject = f"broadcast.{self._service_name}"
            sub_id = await self._nats.subscribe(
                broadcast_subject,
                self._handle_broadcast_message,
            )
            self._subscriptions.append(sub_id)

            self._is_started = True
            logger.info(f"Service bus started for {self._service_name}")

        except Exception as e:
            logger.error(f"Failed to start service bus: {e}")
            raise

    async def stop(self) -> None:
        """Stop the service bus and unsubscribe from all subjects."""
        if not self._is_started:
            return

        try:
            # Unsubscribe from all subscriptions
            for sub_id in self._subscriptions:
                await self._nats.unsubscribe(sub_id)

            self._subscriptions.clear()
            self._is_started = False

            logger.info("Service bus stopped")

        except Exception as e:
            logger.error(f"Error stopping service bus: {e}")

    def register_rpc_handler(self, method: str, handler: Callable) -> None:
        """Register an RPC method handler.

        This is an alias for register_handler to match the port interface.

        Args:
            method: Method name to handle
            handler: Async function to handle the method
        """
        self.register_handler(method, handler)

    def register_handler(self, method: str, handler: Callable) -> None:
        """Register an RPC method handler.

        Args:
            method: Method name to handle
            handler: Async function to handle the method
        """
        self._handlers[method] = handler
        logger.debug(f"Registered handler for method: {method}")

    async def call_rpc(
        self,
        target: str,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        """Call an RPC method on a target service.

        This is an alias for call_remote to match the port interface.

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
        result = await self.call_remote(target, method, params, timeout)
        # Ensure we return a dict as specified by the port
        if not isinstance(result, dict):
            return {"result": result}
        return result

    async def call_remote(
        self,
        service: str,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 5.0,
    ) -> Any:
        """Call a remote service method via RPC.

        Args:
            service: Target service name
            method: Method to call
            params: Method parameters
            timeout: Call timeout in seconds

        Returns:
            Method result

        Raises:
            TimeoutError: If call times out
            RuntimeError: If call fails
        """
        # Create RPC request
        request = RPCRequest(
            method=method,
            params=params or {},
            id=f"{self._service_name}-{asyncio.get_event_loop().time()}",
        )

        # Send request and wait for response
        subject = f"rpc.{service}"
        try:
            response_data = await self._nats.request(
                subject,
                request.model_dump(),
                timeout=timeout,
            )

            # Parse response
            if isinstance(response_data, dict):
                response = RPCResponse(**response_data)
                if response.error:
                    raise RuntimeError(f"RPC error: {response.error}")
                return response.result
            else:
                return response_data

        except TimeoutError as e:
            raise TimeoutError(f"RPC call to {service}.{method} timed out") from e
        except Exception as e:
            logger.error(f"RPC call failed: {e}")
            raise RuntimeError(f"RPC call failed: {e}") from e

    async def publish_event(self, event_type: str, data: Any) -> None:
        """Publish an event to the message bus.

        Args:
            event_type: Type of event
            data: Event data
        """
        subject = f"events.{self._service_name}.{event_type}"
        await self._nats.publish(subject, data)
        logger.debug(f"Published event: {event_type}")

    async def subscribe_to_events(
        self,
        service: str,
        event_type: str,
        handler: Callable,
    ) -> str:
        """Subscribe to events from another service.

        Args:
            service: Service to subscribe to
            event_type: Event type to subscribe to
            handler: Handler for events

        Returns:
            Subscription ID
        """
        subject = f"events.{service}.{event_type}"
        sub_id = await self._nats.subscribe(subject, handler)
        self._subscriptions.append(sub_id)
        logger.debug(f"Subscribed to events: {subject}")
        return sub_id

    async def _handle_rpc_request(self, data: Any) -> Any:
        """Handle incoming RPC request.

        Args:
            data: Request data

        Returns:
            Response data
        """
        try:
            # Parse request
            if isinstance(data, dict):
                request = RPCRequest(**data)
            else:
                request = RPCRequest(method="unknown", params={})

            # Find handler
            handler = self._handlers.get(request.method)
            if not handler:
                return RPCResponse(
                    error={"code": -32601, "message": f"Method not found: {request.method}"},
                    id=request.id,
                ).model_dump()

            # Execute handler
            try:
                result = await handler(request.params or {})
                return RPCResponse(
                    result=result,
                    id=request.id,
                ).model_dump()
            except Exception as e:
                logger.error(f"Handler error for {request.method}: {e}")
                return RPCResponse(
                    error={"code": -32603, "message": str(e)},
                    id=request.id,
                ).model_dump()

        except Exception as e:
            logger.error(f"Failed to handle RPC request: {e}")
            return RPCResponse(
                error={"code": -32700, "message": "Parse error"},
            ).model_dump()

    async def _handle_broadcast_message(self, data: Any) -> None:
        """Handle incoming broadcast message.

        Args:
            data: Broadcast data
        """
        logger.debug(f"Received broadcast: {data}")
        # Broadcast messages don't require a response

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on service bus.

        Returns:
            Health status
        """
        return {
            "status": "healthy" if self._is_started else "stopped",
            "service_name": self._service_name,
            "handlers_registered": len(self._handlers),
            "active_subscriptions": len(self._subscriptions),
            "nats_connected": self._nats.is_connected,
        }

    def get_instance_id(self) -> str:
        """Get the unique instance ID for this service.

        Returns:
            Unique instance identifier
        """
        return f"{self._service_name}-{id(self)}"

    def is_connected(self) -> bool:
        """Check if the service bus is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._is_started and self._nats.is_connected

"""
Gateway Service properly using SingleActiveService from SDK
Avoids reinventing the wheel by leveraging existing SDK functionality
"""

from __future__ import annotations

import asyncio

from aegis_sdk.application.single_active_dtos import SingleActiveConfig
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.ports.kv_store import KVStorePort
from aegis_sdk.ports.logger import LoggerPort
from aegis_sdk.ports.message_bus import MessageBusPort
from aegis_sdk.ports.metrics import MetricsPort
from aegis_sdk.ports.service_discovery import ServiceDiscoveryPort
from aegis_sdk.ports.service_registry import ServiceRegistryPort

from domain.gateway.connection_manager import ConnectionManager
from domain.gateway.models import Gateway
from domain.gateway.ports import EventPublisher, GatewayPort
from domain.gateway.value_objects import (
    GatewayConfig,
    GatewayId,
)


class GatewayService(SingleActiveService):
    """
    High-availability gateway service properly using SDK's SingleActiveService
    Inherits leader election, heartbeat, and failover from SDK
    """

    def __init__(
        self,
        gateway_adapter: GatewayPort,
        gateway_config: GatewayConfig,
        single_active_config: SingleActiveConfig,
        message_bus: MessageBusPort,
        event_publisher: EventPublisher | None = None,
        service_registry: ServiceRegistryPort | None = None,
        service_discovery: ServiceDiscoveryPort | None = None,
        logger: LoggerPort | None = None,
        metrics: MetricsPort | None = None,
        kv_store: KVStorePort | None = None,
    ):
        """
        Initialize Gateway Service using SDK's SingleActiveService

        Args:
            gateway_adapter: Port implementation for specific gateway (CTP, SOPT, etc.)
            gateway_config: Gateway-specific configuration
            single_active_config: Configuration for SingleActiveService
            message_bus: Message bus implementation (required by SDK)
            event_publisher: Optional event publisher for domain events
            service_registry: Optional service registry
            service_discovery: Optional service discovery
            logger: Optional logger
            metrics: Optional metrics
        """
        # Initialize parent SingleActiveService with SDK config
        super().__init__(
            config=single_active_config,
            message_bus=message_bus,
            service_registry=service_registry,
            service_discovery=service_discovery,
            logger=logger,
            metrics=metrics,
        )

        # Gateway-specific dependencies
        self.gateway_adapter = gateway_adapter
        self.gateway_config = gateway_config
        self.event_publisher = event_publisher
        self.kv_store = kv_store

        # Create domain model
        self.gateway = Gateway(
            gateway_id=GatewayId(gateway_config.gateway_id),
            gateway_type=gateway_config.gateway_type,
            config=gateway_config,
        )

        # Initialize connection manager with KV store for state persistence
        self.connection_manager = ConnectionManager(
            adapter=gateway_adapter,
            config=gateway_config.to_connection_config(),
            kv_store=kv_store,
            gateway_id=gateway_config.gateway_id,
        )

        # Tasks
        self._connection_task: asyncio.Task | None = None

    async def on_active(self) -> None:
        """
        Called by SDK when this instance becomes the active leader
        Override from SingleActiveService
        """
        self.logger.info(f"Gateway {self.gateway_config.gateway_id} becoming active leader")

        # Update domain model
        events = self.gateway.acquire_leadership()
        await self._publish_events(events)

        # Restore connection state from KV store if available
        if await self.connection_manager.restore_state():
            self.logger.info("Restored previous connection state from KV store")

        # Start gateway connection asynchronously (non-blocking)
        self._connection_task = asyncio.create_task(self._connect_gateway())
        self.logger.info(f"Gateway {self.gateway_config.gateway_id} connection task started")

    async def on_standby(self) -> None:
        """
        Called by SDK when this instance loses leadership
        Override from SingleActiveService
        """
        self.logger.info(f"Gateway {self.gateway_config.gateway_id} becoming standby")

        # Update domain model
        events = self.gateway.lose_leadership()
        await self._publish_events(events)

        # Cancel connection task
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
            self._connection_task = None

        # Gracefully disconnect
        try:
            await self.connection_manager.disconnect()
            self.gateway.mark_disconnected()

            # Publish disconnected event
            events = self.gateway.disconnect()
            await self._publish_events(events)

        except Exception as e:
            self.logger.error(f"Error during standby transition: {e}")

    async def on_start(self) -> None:
        """
        Called when service starts, register RPC handlers
        Override from SingleActiveService
        """
        await super().on_start()

        # Register exclusive RPC for gateway operations
        @self.exclusive_rpc("get_connection_status")
        async def get_connection_status(params: dict) -> dict:
            """Get gateway connection status - only active instance responds"""
            return {
                "gateway_id": str(self.gateway.gateway_id),
                "is_connected": self.gateway.is_connected(),
                "connection_state": self.gateway.connection_state.value,
                "last_heartbeat": (
                    self.gateway.last_heartbeat.isoformat() if self.gateway.last_heartbeat else None
                ),
                "connection_attempts": self.gateway.connection_attempts,
            }

        @self.exclusive_rpc("subscribe_symbols")
        async def subscribe_symbols(params: dict) -> dict:
            """Subscribe to market data symbols - only active instance processes"""
            symbols = params.get("symbols", [])
            if not self.gateway.is_connected():
                return {"success": False, "error": "Gateway not connected"}

            try:
                await self.gateway_adapter.subscribe(symbols)
                return {"success": True, "subscribed": symbols}
            except Exception as e:
                return {"success": False, "error": str(e)}

        # Regular RPC for health checks (all instances respond)
        @self.rpc("health_check")
        async def health_check(params: dict) -> dict:
            """Health check - all instances respond"""
            return {
                "instance_id": self.instance_id,
                "is_active": self.is_active,
                "gateway_id": str(self.gateway.gateway_id),
                "connection_state": self.gateway.connection_state.value,
            }

    async def _connect_gateway(self) -> None:
        """Connect to gateway asynchronously without blocking leader election"""
        try:
            # Try to connect with a short initial timeout
            await asyncio.sleep(0.1)  # Small delay to let election complete

            # Attempt connection with timeout to avoid blocking
            try:
                await asyncio.wait_for(
                    self.connection_manager.connect(),
                    timeout=5.0,  # 5 second timeout for initial connection
                )
                self.gateway.mark_connected()
            except TimeoutError:
                self.logger.warning("Gateway initial connection timed out, will retry")
                # Continue with retry logic
                return

            # Start heartbeat maintenance
            await self.connection_manager.maintain_heartbeat()

            # Publish connected event
            events = self.gateway.connect()
            await self._publish_events(events)

            self.logger.info(f"Gateway {self.gateway_config.gateway_id} connected successfully")

        except asyncio.CancelledError:
            self.logger.info("Gateway connection task cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Failed to connect gateway: {e}")
            # Connection manager will handle retries

    async def _publish_events(self, events: list) -> None:
        """Publish domain events"""
        if not self.event_publisher:
            return

        for event in events:
            await self.event_publisher.publish(event)

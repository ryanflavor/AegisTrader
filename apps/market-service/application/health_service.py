"""
Health Check Service for Market Service.

Provides health check endpoint for monitoring service status and dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel


class HealthCheckRequest(BaseModel):
    """Request model for health check."""

    timestamp: datetime | None = None


class HealthCheckResponse(BaseModel):
    """Response model for health check."""

    status: str
    timestamp: datetime
    service_name: str
    version: str
    gateway_ready: bool | None = None
    message_bus_connected: bool | None = None
    database_connected: bool | None = None


class HealthCheckService:
    """Service providing health check functionality."""

    def __init__(self) -> None:
        """Initialize health check service."""
        self.service_name = "market-service"
        self.version = "0.1.0"

    async def health_check(self, request: HealthCheckRequest) -> HealthCheckResponse:
        """
        Handle health check RPC request.

        Args:
            request: Health check request

        Returns:
            Health check response with service status
        """
        # Check various health indicators
        gateway_ready = await self._check_gateway_health()
        message_bus_connected = await self._check_message_bus_health()
        database_connected = await self._check_database_health()

        # Aggregate health status
        status = self._aggregate_health_status(
            gateway_ready, message_bus_connected, database_connected
        )

        return HealthCheckResponse(
            status=status,
            timestamp=datetime.now(UTC),
            service_name=self.service_name,
            version=self.version,
            gateway_ready=gateway_ready,
            message_bus_connected=message_bus_connected,
            database_connected=database_connected,
        )

    async def _check_gateway_health(self) -> bool:
        """
        Check if gateway connections are healthy.

        Returns:
            True if gateways are ready, False otherwise
        """
        # TODO: Implement actual gateway health check
        # For now, return True as placeholder
        return True

    async def _check_message_bus_health(self) -> bool:
        """
        Check if message bus (NATS) connection is healthy.

        Returns:
            True if message bus is connected, False otherwise
        """
        # TODO: Implement actual NATS health check
        # For now, return True as placeholder
        return True

    async def _check_database_health(self) -> bool:
        """
        Check if database (ClickHouse) connection is healthy.

        Returns:
            True if database is connected, False otherwise
        """
        # TODO: Implement actual ClickHouse health check
        # For now, return True as placeholder
        return True

    def _aggregate_health_status(
        self,
        gateway_ready: bool,
        message_bus_connected: bool,
        database_connected: bool,
    ) -> str:
        """
        Aggregate individual health indicators into overall status.

        Args:
            gateway_ready: Gateway health status
            message_bus_connected: Message bus health status
            database_connected: Database health status

        Returns:
            Overall health status: "healthy", "degraded", or "unhealthy"
        """
        # All healthy
        if all([gateway_ready, message_bus_connected, database_connected]):
            return "healthy"

        # At least one critical component down
        if not message_bus_connected:
            return "unhealthy"

        # Some components down but service can function
        if not gateway_ready or not database_connected:
            return "degraded"

        return "healthy"

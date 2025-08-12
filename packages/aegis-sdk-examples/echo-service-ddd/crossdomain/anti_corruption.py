"""Anti-corruption layer for echo-service-ddd."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field

from domain.entities import ServiceMetrics
from domain.value_objects import ServiceDefinitionInfo


class ExternalService(Protocol):
    """External service interface."""

    async def fetch_data(self, id: str) -> dict: ...


class MonitorAPIServiceInfo(BaseModel):
    """External monitor-api service info model."""

    name: str
    version: str
    instance_id: str
    status: str
    endpoints: list[str]
    capabilities: list[str]
    registered_at: str
    last_health_check: str | None = None
    metadata: dict = Field(default_factory=dict)


class MonitorAPIAdapter:
    """Anti-corruption adapter for monitor-api integration."""

    def __init__(self, base_url: str = "http://monitor-api:8000"):
        """Initialize with monitor-api base URL."""
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)
        self.client = httpx.AsyncClient(timeout=5.0)

    async def register_service(self, service_info: ServiceDefinitionInfo) -> bool:
        """Register service with monitor-api."""
        try:
            # Transform domain model to external API format
            external_data = {
                "name": service_info.service_name,
                "version": service_info.version,
                "owner": service_info.owner,
                "status": "ACTIVE",
                "endpoints": ["echo", "batch_echo", "metrics", "health", "ping"],
                "capabilities": [],
                "registered_at": datetime.now(UTC).isoformat(),
                "metadata": {
                    "description": service_info.description,
                    "ddd_example": True,
                    "sdk_version": "1.0.0",
                },
            }

            # Send registration request
            response = await self.client.post(
                f"{self.base_url}/api/services/register", json=external_data
            )

            if response.status_code == 200:
                self.logger.info(
                    f"Successfully registered with monitor-api: {service_info.service_name}"
                )
                return True
            else:
                self.logger.error(f"Failed to register with monitor-api: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error registering with monitor-api: {e}")
            return False

    async def update_health_status(
        self, service_name: str, instance_id: str, health_data: dict
    ) -> bool:
        """Update health status with monitor-api."""
        try:
            # Transform health data for external API
            external_data = {
                "instance_id": instance_id,
                "status": health_data.get("status", "HEALTHY"),
                "components": health_data.get("components", {}),
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Send health update
            response = await self.client.put(
                f"{self.base_url}/api/services/{service_name}/health", json=external_data
            )

            return response.status_code == 200

        except Exception as e:
            self.logger.error(f"Error updating health status: {e}")
            return False

    async def report_metrics(self, service_name: str, metrics: ServiceMetrics) -> bool:
        """Report metrics to monitor-api."""
        try:
            # Transform domain metrics to external format
            external_data = {
                "service_name": service_name,
                "timestamp": datetime.now(UTC).isoformat(),
                "metrics": {
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "average_latency_ms": metrics.average_latency_ms,
                    "mode_distribution": metrics.mode_distribution,
                },
            }

            # Send metrics
            response = await self.client.post(f"{self.base_url}/api/metrics", json=external_data)

            return response.status_code == 200

        except Exception as e:
            self.logger.error(f"Error reporting metrics: {e}")
            return False

    async def get_service_status(self, service_name: str) -> dict | None:
        """Get service status from monitor-api."""
        try:
            response = await self.client.get(f"{self.base_url}/api/services/{service_name}/status")

            if response.status_code == 200:
                return response.json()

            return None

        except Exception as e:
            self.logger.error(f"Error getting service status: {e}")
            return None

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


class AntiCorruptionLayer:
    """Protects domain from external systems."""

    def __init__(self, translator, external_service: ExternalService = None):
        self._translator = translator
        self._external_service = external_service
        self.monitor_adapter = MonitorAPIAdapter()

    async def fetch_and_translate(self, external_id: str) -> Any | None:
        """Fetch from external system and translate to domain model."""
        if not self._external_service:
            # Mock data for demonstration
            raw_data = {
                "external_id": external_id,
                "display_name": "Test User",
                "email_address": "test@example.com",
                "registration_date": "2024-01-01",
            }
        else:
            raw_data = await self._external_service.fetch_data(external_id)

        # Translate to domain model
        return self._translator.translate(raw_data)

    async def save_to_external(self, domain_model: Any) -> bool:
        """Save domain model to external system."""
        # Translate to external format
        external_data = self._translator.reverse_translate(domain_model)

        # Send to external system (using the translated data)
        # Implementation would use external_data here
        _ = external_data  # Acknowledge variable until implementation is complete

        return True

    async def register_with_monitor(self, service_info: ServiceDefinitionInfo) -> bool:
        """Register service with monitor-api through anti-corruption layer."""
        return await self.monitor_adapter.register_service(service_info)

    async def update_monitor_health(
        self, service_name: str, instance_id: str, health_data: dict
    ) -> bool:
        """Update health status in monitor-api."""
        return await self.monitor_adapter.update_health_status(
            service_name, instance_id, health_data
        )

    async def report_monitor_metrics(self, service_name: str, metrics: ServiceMetrics) -> bool:
        """Report metrics to monitor-api."""
        return await self.monitor_adapter.report_metrics(service_name, metrics)

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.monitor_adapter:
            await self.monitor_adapter.close()


class BoundedContextAdapter:
    """Adapter for communication between bounded contexts."""

    def __init__(self, context_name: str):
        self._context_name = context_name
        self.logger = logging.getLogger(__name__)

    async def send_to_context(self, message: Any) -> None:
        """Send message to another bounded context."""
        # Transform message for target context
        # Send via appropriate channel
        self.logger.debug(f"Sending message to {self._context_name}: {message}")
        pass

    async def receive_from_context(self) -> Any | None:
        """Receive message from another bounded context."""
        # Receive and transform message
        return None

    async def transform_for_context(self, data: Any, target_context: str) -> dict:
        """Transform data for a specific bounded context."""
        # Apply context-specific transformations
        if target_context == "trading":
            return self._transform_for_trading(data)
        elif target_context == "analytics":
            return self._transform_for_analytics(data)
        else:
            return data if isinstance(data, dict) else {"data": data}

    def _transform_for_trading(self, data: Any) -> dict:
        """Transform data for trading context."""
        # Trading context specific transformation
        return {"trading_data": data, "timestamp": datetime.now(UTC).isoformat()}

    def _transform_for_analytics(self, data: Any) -> dict:
        """Transform data for analytics context."""
        # Analytics context specific transformation
        return {"analytics_payload": data, "processed_at": datetime.now(UTC).isoformat()}

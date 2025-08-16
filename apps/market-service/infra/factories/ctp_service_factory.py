"""Factory for creating CTP Gateway Service instances.

This module follows the Factory pattern to encapsulate the complex
creation logic for CTP Gateway services.
"""

import logging
import os
from datetime import UTC, datetime

from aegis_sdk.application.dependency_provider import DependencyProvider
from aegis_sdk.application.single_active_dtos import SingleActiveConfig
from aegis_sdk.infrastructure import DefaultUseCaseFactory, InMemoryMetrics
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger
from pydantic import BaseModel, ConfigDict, Field

from application.gateway_service import GatewayService
from domain.gateway.value_objects import GatewayConfig, GatewayType
from infra.adapters.gateway.ctp_adapter import CtpConfig, CtpGatewayAdapter
from infra.election_factory import ElectionFactory

logger = logging.getLogger(__name__)


class CTPServiceConfig(BaseModel):
    """Configuration for CTP service creation."""

    model_config = ConfigDict(strict=True)

    gateway_id: str = Field(default="ctp-gateway", description="Unique identifier for the gateway")
    heartbeat_interval: int = Field(default=1, description="Heartbeat interval in seconds", ge=1)
    leader_ttl_seconds: int = Field(
        default=5, description="Leader TTL in seconds (must be > heartbeat_interval)", gt=1
    )
    registry_ttl: int = Field(default=10, description="Registry TTL in seconds", gt=0)
    reconnect_delay: int = Field(
        default=5, description="Delay between reconnection attempts in seconds", gt=0
    )
    max_reconnect_attempts: int = Field(
        default=10, description="Maximum number of reconnection attempts", gt=0
    )


class CTPServiceFactory:
    """Factory for creating CTP Gateway Service instances."""

    @staticmethod
    async def create_gateway_service(
        nats_adapter: NATSAdapter,
        service_registry: KVServiceRegistry | None = None,
        service_discovery=None,
        config: CTPServiceConfig | None = None,
        instance_id: str | None = None,
    ) -> GatewayService:
        """Create and initialize CTP gateway service with proper DDD architecture.

        Args:
            nats_adapter: NATS adapter for messaging
            service_registry: Service registry for leader election
            service_discovery: Service discovery for high availability
            config: CTP service configuration

        Returns:
            GatewayService instance properly configured
        """
        config = config or CTPServiceConfig()

        # Load CTP configuration from environment
        ctp_config = CtpConfig.from_env()

        # Create CTP adapter
        adapter = CtpGatewayAdapter(ctp_config)

        # Create gateway configuration
        gateway_config = GatewayConfig(
            gateway_id=config.gateway_id,
            gateway_type=GatewayType.CTP,
            credentials={
                "user_id": ctp_config.user_id,
                "password": ctp_config.password,
                "broker_id": ctp_config.broker_id,
                "app_id": ctp_config.app_id,
                "auth_code": ctp_config.auth_code,
            },
            connection_params={
                "td_address": ctp_config.td_address,
                "md_address": ctp_config.md_address,
            },
            heartbeat_interval=30,
            reconnect_delay=config.reconnect_delay,
            max_reconnect_attempts=config.max_reconnect_attempts,
        )

        # Create single active config for HA with optimized failover < 2s
        # Use provided instance_id or generate one based on environment/timestamp
        if instance_id is None:
            instance_id = (
                os.getenv("SERVICE_INSTANCE_ID")
                or f"ctp-gateway-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
            )

        single_active_config = SingleActiveConfig(
            service_name="ctp-gateway-service",
            instance_id=instance_id,
            heartbeat_interval=config.heartbeat_interval,
            leader_ttl_seconds=config.leader_ttl_seconds,
            registry_ttl=config.registry_ttl,
            group_id="default",
        )

        # Create gateway service
        gateway_service = GatewayService(
            gateway_adapter=adapter,
            gateway_config=gateway_config,
            single_active_config=single_active_config,
            message_bus=nats_adapter,
            service_registry=service_registry,
            service_discovery=service_discovery,
            logger=SimpleLogger("CTP-Gateway"),
        )

        logger.info(f"CTP Gateway Service initialized for broker {ctp_config.broker_id}")

        return gateway_service

    @staticmethod
    async def setup_dependencies() -> None:
        """Register dependencies required for CTP service."""
        # Register all required dependencies for SingleActiveService
        DependencyProvider.register_defaults(
            election_factory=ElectionFactory(),
            use_case_factory=DefaultUseCaseFactory(),
            metrics_class=InMemoryMetrics,
        )
        logger.info("CTP service dependencies registered")

    @staticmethod
    async def create_service_registry(nats_adapter: NATSAdapter) -> KVServiceRegistry:
        """Create service registry for leader election.

        Args:
            nats_adapter: NATS adapter for KV store

        Returns:
            KVServiceRegistry instance
        """
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("gateway_registry")
        registry = KVServiceRegistry(kv_store=kv_store)
        logger.info("Service registry created for gateway_registry")
        return registry

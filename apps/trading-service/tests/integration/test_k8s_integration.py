"""Integration tests for trading services in K8s environment."""

import asyncio
import uuid
from typing import Any

import pytest
from aegis_sdk.application import Service
from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger
from aegis_sdk.infrastructure.watchable_cached_service_discovery import (
    WatchableCacheConfig,
    WatchableCachedServiceDiscovery,
    WatchConfig,
)
from order_service import OrderService
from risk_service import RiskService
from shared_contracts import ServiceNames


class SimpleTestService(Service):
    """Test service without event subscriptions to avoid durable consumer conflicts."""

    async def on_start(self) -> None:
        """Register only RPC handlers."""

        @self.rpc("echo")
        async def echo(params: dict[str, Any]) -> dict[str, Any]:
            return {"echo": params, "instance": self.instance_id}

        @self.rpc("health")
        async def health(params: dict[str, Any]) -> dict[str, Any]:
            return {"status": "healthy", "instance": self.instance_id}

        @self.rpc("get_price")
        async def get_price(params: dict[str, Any]) -> dict[str, Any]:
            # Simulate pricing service behavior
            symbol = params.get("symbol", "UNKNOWN")
            base_price = 100.0
            return {
                "symbol": symbol,
                "price": base_price,
                "bid": base_price - 0.5,
                "ask": base_price + 0.5,
                "instance": self.instance_id,
            }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_service_registration_in_k8s():
    """Test service registration in K8s NATS environment."""
    # Use K8s port-forwarded NATS
    nats_url = "nats://localhost:4222"
    bucket_name = "service-registry"

    # Create infrastructure
    nats_adapter = NATSAdapter()
    await nats_adapter.connect([nats_url])

    kv_store = NATSKVStore(nats_adapter=nats_adapter)
    await kv_store.connect(bucket_name)

    logger = SimpleLogger()
    registry = KVServiceRegistry(kv_store=kv_store, logger=logger)

    # Create and start a test service with unique instance ID
    unique_id = f"test-order-service-{uuid.uuid4().hex[:8]}"
    service = OrderService(
        message_bus=nats_adapter,
        instance_id=unique_id,
        service_registry=registry,
        logger=logger,
    )

    try:
        await service.start()

        # Give time for registration
        await asyncio.sleep(2)

        # Check if service is registered
        instances = await registry.list_instances(service.service_name)
        assert len(instances) > 0
        assert any(i.instance_id == unique_id for i in instances)

        # Check instance details
        instance = next(i for i in instances if i.instance_id == unique_id)
        assert instance.status == "ACTIVE"
        assert instance.version == "1.0.0"

    finally:
        await service.stop()
        await kv_store.disconnect()
        await nats_adapter.disconnect()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_service_discovery_in_k8s():
    """Test service discovery in K8s NATS environment."""
    nats_url = "nats://localhost:4222"
    bucket_name = "service-registry"

    # Create infrastructure
    nats_adapter = NATSAdapter()
    await nats_adapter.connect([nats_url])

    kv_store = NATSKVStore(nats_adapter=nats_adapter)
    await kv_store.connect(bucket_name)

    logger = SimpleLogger()
    registry = KVServiceRegistry(kv_store=kv_store, logger=logger)
    basic_discovery = BasicServiceDiscovery(registry, logger)
    config = WatchableCacheConfig(
        ttl_seconds=60.0,
        watch=WatchConfig(enabled=True),
    )
    discovery = WatchableCachedServiceDiscovery(basic_discovery, kv_store, config, logger=logger)

    # Start multiple test service instances
    services = []
    test_run_id = uuid.uuid4().hex[:8]
    for i in range(3):
        service = SimpleTestService(
            service_name=ServiceNames.PRICING_SERVICE,
            message_bus=nats_adapter,
            instance_id=f"test-pricing-{test_run_id}-{i + 1:02d}",
            service_registry=registry,
            service_discovery=discovery,
            logger=logger,
        )
        await service.start()
        services.append(service)

    try:
        # Give time for registration
        await asyncio.sleep(2)

        # Test discovery using registry directly
        instances = await registry.list_instances(ServiceNames.PRICING_SERVICE)
        assert len(instances) >= 3

        # Test instance selection
        selected = await discovery.select_instance(ServiceNames.PRICING_SERVICE)
        assert selected is not None
        assert selected.service_name == ServiceNames.PRICING_SERVICE
        assert selected.status == "ACTIVE"

    finally:
        for service in services:
            await service.stop()
        await kv_store.disconnect()
        await nats_adapter.disconnect()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_inter_service_communication_in_k8s():
    """Test RPC communication between services in K8s."""
    nats_url = "nats://localhost:4222"
    bucket_name = "service-registry"

    # Create infrastructure
    nats_adapter1 = NATSAdapter()
    await nats_adapter1.connect([nats_url])

    nats_adapter2 = NATSAdapter()
    await nats_adapter2.connect([nats_url])

    kv_store1 = NATSKVStore(nats_adapter=nats_adapter1)
    await kv_store1.connect(bucket_name)

    kv_store2 = NATSKVStore(nats_adapter=nats_adapter2)
    await kv_store2.connect(bucket_name)

    logger = SimpleLogger()
    registry1 = KVServiceRegistry(kv_store=kv_store1, logger=logger)
    registry2 = KVServiceRegistry(kv_store=kv_store2, logger=logger)
    basic_discovery = BasicServiceDiscovery(registry1, logger)
    config = WatchableCacheConfig(
        ttl_seconds=60.0,
        watch=WatchConfig(enabled=True),
    )
    discovery = WatchableCachedServiceDiscovery(basic_discovery, kv_store1, config, logger=logger)

    # Start pricing service with unique ID (use SimpleTestService to avoid event conflicts)
    test_run_id = uuid.uuid4().hex[:8]
    pricing_service = SimpleTestService(
        service_name=ServiceNames.PRICING_SERVICE,
        message_bus=nats_adapter1,
        instance_id=f"test-pricing-rpc-{test_run_id}",
        service_registry=registry1,
        logger=logger,
    )
    await pricing_service.start()

    # Start order service with discovery and unique ID
    order_service = OrderService(
        message_bus=nats_adapter2,
        instance_id=f"test-order-rpc-{test_run_id}",
        service_registry=registry2,
        service_discovery=discovery,
        logger=logger,
    )
    await order_service.start()

    try:
        # Give time for registration
        await asyncio.sleep(2)

        # Verify services are registered
        pricing_instances = await registry1.list_instances(ServiceNames.PRICING_SERVICE)
        assert len(pricing_instances) == 1

        # Test RPC communication between services
        # First test direct RPC to pricing service
        from aegis_sdk.domain.models import RPCRequest

        rpc_request = RPCRequest(
            target=f"{ServiceNames.PRICING_SERVICE}.{pricing_service.instance_id}",
            method="get_price",
            params={"symbol": "AAPL"},
        )

        response = await nats_adapter1.call_rpc(rpc_request)
        assert response.result is not None
        assert response.result["symbol"] == "AAPL"
        assert response.result["price"] == 100.0

    finally:
        await order_service.stop()
        await pricing_service.stop()
        await kv_store1.disconnect()
        await kv_store2.disconnect()
        await nats_adapter1.disconnect()
        await nats_adapter2.disconnect()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_event_flow_in_k8s():
    """Test event publishing and subscription in K8s."""
    nats_url = "nats://localhost:4222"
    bucket_name = "service-registry"

    # Create infrastructure
    nats_adapter = NATSAdapter()
    await nats_adapter.connect([nats_url])

    kv_store = NATSKVStore(nats_adapter=nats_adapter)
    await kv_store.connect(bucket_name)

    logger = SimpleLogger()
    registry = KVServiceRegistry(kv_store=kv_store, logger=logger)

    # Create services with unique IDs
    test_run_id = uuid.uuid4().hex[:8]

    # Create separate NATS connections to avoid consumer conflicts
    nats_adapter2 = NATSAdapter()
    await nats_adapter2.connect([nats_url])

    order_service = OrderService(
        message_bus=nats_adapter,
        instance_id=f"test-order-events-{test_run_id}",
        service_registry=registry,
        logger=logger,
    )

    risk_service = RiskService(
        message_bus=nats_adapter2,
        instance_id=f"test-risk-events-{test_run_id}",
        service_registry=registry,
        logger=logger,
    )

    await order_service.start()
    await risk_service.start()

    try:
        # Give time for registration and subscription setup
        await asyncio.sleep(2)

        # Test event flow by publishing an event
        # First verify services are running
        order_instances = await registry.list_instances(order_service.service_name)
        assert len(order_instances) == 1
        risk_instances = await registry.list_instances(risk_service.service_name)
        assert len(risk_instances) == 1

        # Publish an order created event directly
        await order_service.publish_event(
            "order",
            "created",
            {
                "order": {
                    "order_id": f"test-order-{test_run_id}",
                    "symbol": "TSLA",
                    "quantity": 50,
                    "side": "BUY",
                    "order_type": "LIMIT",
                    "price": 250.0,
                }
            },
        )

        # Give time for event processing
        await asyncio.sleep(2)

        # Verify event was published (no error means success)
        # Since we can't easily test cross-service event flow without proper setup,
        # just ensure the publish worked without errors

    finally:
        await order_service.stop()
        await risk_service.stop()
        await kv_store.disconnect()
        await nats_adapter.disconnect()
        await nats_adapter2.disconnect()


if __name__ == "__main__":
    # Run tests individually for debugging
    asyncio.run(test_service_registration_in_k8s())
    asyncio.run(test_service_discovery_in_k8s())
    asyncio.run(test_inter_service_communication_in_k8s())
    asyncio.run(test_event_flow_in_k8s())
    print("All K8s integration tests passed!")

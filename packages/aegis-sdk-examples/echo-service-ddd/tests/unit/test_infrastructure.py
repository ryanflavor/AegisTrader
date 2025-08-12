"""Unit tests for infrastructure layer."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crossdomain.anti_corruption import (
    BoundedContextAdapter,
    MonitorAPIAdapter,
)
from domain.entities import ServiceMetrics
from domain.value_objects import ServiceDefinitionInfo
from infra.adapters import (
    AegisServiceBusAdapter,
    EnvironmentConfigurationAdapter,
    KVRegistryAdapter,
    LoggingAdapter,
    SimpleCacheAdapter,
    SimpleMetricsAdapter,
)
from infra.factory import ServiceFactory, cleanup_factory, get_factory


class TestEnvironmentConfigurationAdapter:
    """Test environment configuration adapter."""

    def test_get_config_from_environment(self):
        """Test getting configuration from environment variables."""
        # Arrange
        os.environ["ECHO_SERVICE_TEST_KEY"] = "test_value"
        config = EnvironmentConfigurationAdapter()

        # Act
        value = config.get("test_key")

        # Assert
        assert value == "test_value"

        # Cleanup
        del os.environ["ECHO_SERVICE_TEST_KEY"]

    def test_get_int_config(self):
        """Test getting integer configuration value."""
        # Arrange
        os.environ["ECHO_SERVICE_PORT"] = "8080"
        config = EnvironmentConfigurationAdapter()

        # Act
        port = config.get_int("port")

        # Assert
        assert port == 8080
        assert isinstance(port, int)

        # Cleanup
        del os.environ["ECHO_SERVICE_PORT"]

    def test_get_bool_config(self):
        """Test getting boolean configuration value."""
        # Arrange
        os.environ["ECHO_SERVICE_DEBUG"] = "true"
        os.environ["ECHO_SERVICE_VERBOSE"] = "false"
        config = EnvironmentConfigurationAdapter()

        # Act
        debug = config.get_bool("debug")
        verbose = config.get_bool("verbose")

        # Assert
        assert debug is True
        assert verbose is False

        # Cleanup
        del os.environ["ECHO_SERVICE_DEBUG"]
        del os.environ["ECHO_SERVICE_VERBOSE"]

    def test_get_str_config(self):
        """Test getting string configuration value."""
        # Arrange
        os.environ["ECHO_SERVICE_NAME"] = "test-service"
        config = EnvironmentConfigurationAdapter()

        # Act
        name = config.get_str("name")

        # Assert
        assert name == "test-service"
        assert isinstance(name, str)

        # Cleanup
        del os.environ["ECHO_SERVICE_NAME"]

    def test_get_config_with_default(self):
        """Test getting configuration with default value."""
        # Arrange
        config = EnvironmentConfigurationAdapter()

        # Act
        value = config.get("non_existent", "default_value")
        int_value = config.get_int("non_existent", 42)
        bool_value = config.get_bool("non_existent", True)
        str_value = config.get_str("non_existent", "default")

        # Assert
        assert value == "default_value"
        assert int_value == 42
        assert bool_value is True
        assert str_value == "default"


class TestSimpleCacheAdapter:
    """Test simple cache adapter."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Test setting and getting cache values."""
        # Arrange
        cache = SimpleCacheAdapter()

        # Act
        await cache.set("key1", "value1")
        await cache.set("key2", {"data": "value2"})

        result1 = await cache.get("key1")
        result2 = await cache.get("key2")
        result3 = await cache.get("non_existent")

        # Assert
        assert result1 == "value1"
        assert result2 == {"data": "value2"}
        assert result3 is None

    @pytest.mark.asyncio
    async def test_cache_delete(self):
        """Test deleting cache values."""
        # Arrange
        cache = SimpleCacheAdapter()
        await cache.set("key1", "value1")

        # Act
        await cache.delete("key1")
        result = await cache.get("key1")

        # Assert
        assert result is None


class TestLoggingAdapter:
    """Test logging adapter."""

    def test_logging_methods(self):
        """Test all logging methods."""
        # Arrange
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            adapter = LoggingAdapter("test")

            # Act
            adapter.debug("debug message", extra_data="value")
            adapter.info("info message", extra_data="value")
            adapter.warning("warning message", extra_data="value")
            adapter.error("error message", extra_data="value")

            # Assert
            mock_logger.debug.assert_called_once_with(
                "debug message", extra={"extra_data": "value"}
            )
            mock_logger.info.assert_called_once_with("info message", extra={"extra_data": "value"})
            mock_logger.warning.assert_called_once_with(
                "warning message", extra={"extra_data": "value"}
            )
            mock_logger.error.assert_called_once_with(
                "error message", extra={"extra_data": "value"}
            )


class TestSimpleMetricsAdapter:
    """Test simple metrics adapter."""

    def test_increment_counter(self):
        """Test incrementing counter metrics."""
        # Arrange
        metrics = SimpleMetricsAdapter()

        # Act
        metrics.increment("requests", 1)
        metrics.increment("requests", 2)
        metrics.increment("errors", 1, tags={"type": "timeout"})

        # Assert
        assert metrics.counters["requests"] == 3
        assert metrics.counters["errors:{'type': 'timeout'}"] == 1

    def test_set_gauge(self):
        """Test setting gauge metrics."""
        # Arrange
        metrics = SimpleMetricsAdapter()

        # Act
        metrics.gauge("memory_usage", 75.5)
        metrics.gauge("cpu_usage", 30.2, tags={"core": "1"})

        # Assert
        assert metrics.gauges["memory_usage"] == 75.5
        assert metrics.gauges["cpu_usage:{'core': '1'}"] == 30.2

    def test_record_histogram(self):
        """Test recording histogram metrics."""
        # Arrange
        metrics = SimpleMetricsAdapter()

        # Act
        metrics.histogram("latency", 100.5)
        metrics.histogram("latency", 150.2)
        metrics.histogram("latency", 120.8)

        # Assert
        assert len(metrics.histograms["latency"]) == 3
        assert 100.5 in metrics.histograms["latency"]
        assert 150.2 in metrics.histograms["latency"]
        assert 120.8 in metrics.histograms["latency"]

    def test_get_metrics(self):
        """Test getting all metrics."""
        # Arrange
        metrics = SimpleMetricsAdapter()
        metrics.increment("counter1", 5)
        metrics.gauge("gauge1", 10.5)
        metrics.histogram("hist1", 20.3)

        # Act
        all_metrics = metrics.get_metrics()

        # Assert
        assert "counters" in all_metrics
        assert "gauges" in all_metrics
        assert "histograms" in all_metrics
        assert all_metrics["counters"]["counter1"] == 5
        assert all_metrics["gauges"]["gauge1"] == 10.5
        assert 20.3 in all_metrics["histograms"]["hist1"]


class TestAegisServiceBusAdapter:
    """Test Aegis service bus adapter."""

    @pytest.mark.asyncio
    async def test_register_handler(self):
        """Test registering RPC handler."""
        # Arrange
        mock_adapter = MagicMock()
        mock_adapter.client = AsyncMock()
        adapter = AegisServiceBusAdapter(mock_adapter)

        async def test_handler(data):
            return {"echo": data}

        # Act
        await adapter.register_handler("test.subject", test_handler)

        # Assert
        mock_adapter.client.subscribe.assert_called_once()
        assert "test.subject" in adapter.handlers

    @pytest.mark.asyncio
    async def test_call_rpc(self):
        """Test making RPC call."""
        # Arrange
        mock_adapter = MagicMock()
        mock_response = MagicMock()
        mock_response.data = b'{"result": "success"}'
        mock_adapter.client.request = AsyncMock(return_value=mock_response)

        adapter = AegisServiceBusAdapter(mock_adapter)

        # Act
        result = await adapter.call("test.subject", {"data": "test"})

        # Assert
        assert result == {"result": "success"}
        mock_adapter.client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_event(self):
        """Test publishing event."""
        # Arrange
        mock_adapter = MagicMock()
        mock_adapter.client.publish = AsyncMock()
        adapter = AegisServiceBusAdapter(mock_adapter)

        # Act
        await adapter.publish_event("test.event", {"event": "data"})

        # Assert
        mock_adapter.client.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_event(self):
        """Test subscribing to events."""
        # Arrange
        mock_adapter = MagicMock()
        mock_adapter.client.subscribe = AsyncMock()
        adapter = AegisServiceBusAdapter(mock_adapter)

        async def event_handler(data):
            pass

        # Act
        await adapter.subscribe_event("test.event", event_handler)

        # Assert
        mock_adapter.client.subscribe.assert_called_once()


class TestKVRegistryAdapter:
    """Test KV registry adapter."""

    @pytest.mark.asyncio
    async def test_register_service(self):
        """Test registering service instance."""
        # Arrange
        mock_adapter = MagicMock()
        mock_js = MagicMock()
        mock_kv = AsyncMock()
        mock_adapter.client.jetstream.return_value = mock_js
        mock_js.key_value = AsyncMock(return_value=mock_kv)

        adapter = KVRegistryAdapter(mock_adapter)

        # Act
        await adapter.register("test-service", {"version": "1.0.0"})

        # Assert
        mock_kv.put.assert_called_once()
        args = mock_kv.put.call_args[0]
        assert args[0].startswith("test-service.")

    @pytest.mark.asyncio
    async def test_deregister_service(self):
        """Test deregistering service instance."""
        # Arrange
        mock_adapter = MagicMock()
        mock_js = MagicMock()
        mock_kv = AsyncMock()
        mock_adapter.client.jetstream.return_value = mock_js
        mock_js.key_value = AsyncMock(return_value=mock_kv)

        adapter = KVRegistryAdapter(mock_adapter)

        # Act
        await adapter.deregister("test-service", "instance-123")

        # Assert
        mock_kv.delete.assert_called_once_with("test-service.instance-123")

    @pytest.mark.asyncio
    async def test_get_instances(self):
        """Test getting service instances."""
        # Arrange
        mock_adapter = MagicMock()
        mock_js = MagicMock()
        mock_kv = AsyncMock()
        mock_adapter.client.jetstream.return_value = mock_js
        mock_js.key_value = AsyncMock(return_value=mock_kv)

        # Mock keys and entries
        mock_kv.keys = AsyncMock(return_value=["test-service.1", "test-service.2"])
        mock_entry = MagicMock()
        mock_entry.value = b'{"instance_id": "1", "status": "ACTIVE"}'
        mock_kv.get = AsyncMock(return_value=mock_entry)

        adapter = KVRegistryAdapter(mock_adapter)

        # Act
        instances = await adapter.get_instances("test-service")

        # Assert
        assert len(instances) == 2
        assert instances[0]["instance_id"] == "1"
        assert instances[0]["status"] == "ACTIVE"


class TestMonitorAPIAdapter:
    """Test monitor API adapter."""

    @pytest.mark.asyncio
    async def test_register_service_with_monitor(self):
        """Test registering service with monitor-api."""
        # Arrange
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            adapter = MonitorAPIAdapter()
            service_info = ServiceDefinitionInfo(
                service_name="test-service",
                owner="test-team",
                description="Test service",
                version="1.0.0",
            )

            # Act
            result = await adapter.register_service(service_info)

            # Assert
            assert result is True
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_health_status(self):
        """Test updating health status with monitor-api."""
        # Arrange
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.put = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            adapter = MonitorAPIAdapter()

            # Act
            result = await adapter.update_health_status(
                "test-service", "instance-123", {"status": "HEALTHY", "components": {}}
            )

            # Assert
            assert result is True
            mock_client.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_report_metrics(self):
        """Test reporting metrics to monitor-api."""
        # Arrange
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            adapter = MonitorAPIAdapter()
            metrics = ServiceMetrics(
                instance_id="test-instance-123",
                total_requests=100,
                successful_requests=95,
                failed_requests=5,
                average_latency_ms=50.5,
            )

            # Act
            result = await adapter.report_metrics("test-service", metrics)

            # Assert
            assert result is True
            mock_client.post.assert_called_once()


class TestBoundedContextAdapter:
    """Test bounded context adapter."""

    @pytest.mark.asyncio
    async def test_transform_for_trading_context(self):
        """Test transforming data for trading context."""
        # Arrange
        adapter = BoundedContextAdapter("trading")
        test_data = {"symbol": "AAPL", "price": 150.0}

        # Act
        result = await adapter.transform_for_context(test_data, "trading")

        # Assert
        assert "trading_data" in result
        assert result["trading_data"] == test_data
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_transform_for_analytics_context(self):
        """Test transforming data for analytics context."""
        # Arrange
        adapter = BoundedContextAdapter("analytics")
        test_data = {"metric": "revenue", "value": 1000000}

        # Act
        result = await adapter.transform_for_context(test_data, "analytics")

        # Assert
        assert "analytics_payload" in result
        assert result["analytics_payload"] == test_data
        assert "processed_at" in result


class TestServiceFactory:
    """Test service factory."""

    @pytest.mark.asyncio
    async def test_factory_initialization(self):
        """Test factory initialization."""
        # Arrange
        with patch("infra.factory.NATSAdapter") as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            factory = ServiceFactory()

            # Act
            await factory.initialize()

            # Assert
            assert factory.config is not None
            assert factory.logger is not None
            assert factory.metrics is not None
            assert factory.cache is not None
            assert factory.service_bus is not None
            assert factory.registry is not None
            assert factory.echo_use_case is not None
            assert factory.metrics_use_case is not None
            assert factory.health_use_case is not None

    @pytest.mark.asyncio
    async def test_register_rpc_handlers(self):
        """Test registering RPC handlers."""
        # Arrange
        with patch("infra.factory.NATSAdapter") as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            factory = ServiceFactory()
            await factory.initialize()

            # Mock service bus
            factory.service_bus = AsyncMock()
            factory.config = MagicMock()
            factory.config.get_str = MagicMock(return_value="test-service")

            # Act
            await factory.register_rpc_handlers()

            # Assert
            assert factory.service_bus.register_handler.call_count == 5  # 5 handlers

    @pytest.mark.asyncio
    async def test_factory_singleton(self):
        """Test factory singleton pattern."""
        # Arrange
        with patch("infra.factory.ServiceFactory.initialize") as mock_init:
            mock_init.return_value = None

            # Act
            factory1 = await get_factory()
            factory2 = await get_factory()

            # Assert
            assert factory1 is factory2
            mock_init.assert_called_once()

            # Cleanup
            await cleanup_factory()

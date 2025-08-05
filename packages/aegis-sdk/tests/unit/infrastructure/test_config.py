"""Unit tests for infrastructure configuration objects."""

import pytest
from pydantic import ValidationError

from aegis_sdk.domain.value_objects import InstanceId, ServiceName
from aegis_sdk.infrastructure.config import (
    KVStoreConfig,
    LogContext,
    NATSConnectionConfig,
)


class TestNATSConnectionConfig:
    """Tests for NATS connection configuration."""

    def test_defaults(self):
        """Test default configuration values."""
        config = NATSConnectionConfig()
        assert config.servers == ["nats://localhost:4222"]
        assert config.pool_size == 1
        assert config.max_reconnect_attempts == 10
        assert config.reconnect_time_wait == 2.0
        assert config.js_domain is None
        assert config.enable_jetstream is True
        assert config.service_name is None
        assert config.instance_id is None
        assert config.use_msgpack is True

    def test_custom_values(self):
        """Test configuration with custom values."""
        config = NATSConnectionConfig(
            servers=["nats://server1:4222", "nats://server2:4222"],
            pool_size=5,
            max_reconnect_attempts=20,
            reconnect_time_wait=5.0,
            js_domain="test-domain",
            enable_jetstream=False,
            service_name="test-service",
            instance_id="test-instance",
            use_msgpack=False,
        )
        assert config.servers == ["nats://server1:4222", "nats://server2:4222"]
        assert config.pool_size == 5
        assert config.max_reconnect_attempts == 20
        assert config.reconnect_time_wait == 5.0
        assert config.js_domain == "test-domain"
        assert config.enable_jetstream is False
        assert config.service_name == ServiceName(value="test-service")
        assert config.instance_id == InstanceId(value="test-instance")
        assert config.use_msgpack is False

    def test_server_validation(self):
        """Test server URL validation."""
        # Valid URLs
        config = NATSConnectionConfig(
            servers=[
                "nats://localhost:4222",
                "tls://secure.nats:4222",
                "ws://websocket.nats:80",
                "wss://secure-ws.nats:443",
            ]
        )
        assert len(config.servers) == 4

        # Invalid URL
        with pytest.raises(ValidationError) as exc_info:
            NATSConnectionConfig(servers=["http://invalid:4222"])
        assert "Invalid server URL" in str(exc_info.value)

    def test_pool_size_validation(self):
        """Test pool size validation."""
        # Valid range
        config = NATSConnectionConfig(pool_size=10)
        assert config.pool_size == 10

        # Too small
        with pytest.raises(ValidationError):
            NATSConnectionConfig(pool_size=0)

        # Too large
        with pytest.raises(ValidationError):
            NATSConnectionConfig(pool_size=11)

    def test_service_name_parsing(self):
        """Test service name parsing from string."""
        # From string
        config = NATSConnectionConfig(service_name="test-service")
        assert isinstance(config.service_name, ServiceName)
        assert str(config.service_name) == "test-service"

        # From ServiceName object
        service_name = ServiceName(value="another-service")
        config = NATSConnectionConfig(service_name=service_name)
        assert config.service_name == service_name

        # From None
        config = NATSConnectionConfig(service_name=None)
        assert config.service_name is None

        # Invalid type
        with pytest.raises(ValidationError):
            NATSConnectionConfig(service_name=123)

    def test_instance_id_parsing(self):
        """Test instance ID parsing from string."""
        # From string
        config = NATSConnectionConfig(instance_id="instance-123")
        assert isinstance(config.instance_id, InstanceId)
        assert str(config.instance_id) == "instance-123"

        # From InstanceId object
        instance_id = InstanceId(value="instance-456")
        config = NATSConnectionConfig(instance_id=instance_id)
        assert config.instance_id == instance_id

        # From None
        config = NATSConnectionConfig(instance_id=None)
        assert config.instance_id is None

        # Invalid type
        with pytest.raises(ValidationError):
            NATSConnectionConfig(instance_id=123)

    def test_to_connection_params(self):
        """Test conversion to NATS connection parameters."""
        config = NATSConnectionConfig(
            servers=["nats://server1:4222"],
            max_reconnect_attempts=15,
            reconnect_time_wait=3.0,
        )
        params = config.to_connection_params()
        assert params == {
            "servers": ["nats://server1:4222"],
            "max_reconnect_attempts": 15,
            "reconnect_time_wait": 3.0,
        }

    def test_validation_strictness(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError) as exc_info:
            NATSConnectionConfig(extra_field="not allowed")
        assert "Extra inputs are not permitted" in str(exc_info.value)


class TestKVStoreConfig:
    """Tests for KV store configuration."""

    def test_defaults(self):
        """Test default configuration values."""
        config = KVStoreConfig(bucket="test_bucket")
        assert config.bucket == "test_bucket"
        assert config.enable_ttl is True
        assert config.sanitize_keys is True
        assert config.max_value_size == 1024 * 1024  # 1MB
        assert config.history_size == 10

    def test_custom_values(self):
        """Test configuration with custom values."""
        config = KVStoreConfig(
            bucket="custom_bucket",
            enable_ttl=False,
            sanitize_keys=False,
            max_value_size=2048 * 1024,  # 2MB
            history_size=50,
        )
        assert config.bucket == "custom_bucket"
        assert config.enable_ttl is False
        assert config.sanitize_keys is False
        assert config.max_value_size == 2048 * 1024
        assert config.history_size == 50

    def test_bucket_name_validation(self):
        """Test bucket name validation."""
        # Valid names
        config = KVStoreConfig(bucket="valid_bucket_123")
        assert config.bucket == "valid_bucket_123"

        # Invalid names with hyphen
        with pytest.raises(ValidationError) as exc_info:
            KVStoreConfig(bucket="invalid-bucket")
        assert "Invalid bucket name" in str(exc_info.value)

        with pytest.raises(ValidationError):
            KVStoreConfig(bucket="invalid.bucket")

        with pytest.raises(ValidationError):
            KVStoreConfig(bucket="invalid bucket")

    def test_history_size_validation(self):
        """Test history size validation."""
        # Valid range
        config = KVStoreConfig(bucket="test", history_size=100)
        assert config.history_size == 100

        # Too small
        with pytest.raises(ValidationError):
            KVStoreConfig(bucket="test", history_size=0)

        # Too large
        with pytest.raises(ValidationError):
            KVStoreConfig(bucket="test", history_size=101)

    def test_max_value_size_validation(self):
        """Test max value size validation."""
        # Valid size
        config = KVStoreConfig(bucket="test", max_value_size=1024)
        assert config.max_value_size == 1024

        # Too small
        with pytest.raises(ValidationError):
            KVStoreConfig(bucket="test", max_value_size=0)

    def test_bucket_required(self):
        """Test that bucket is required."""
        with pytest.raises(ValidationError):
            KVStoreConfig()  # type: ignore


class TestLogContext:
    """Tests for log context."""

    def test_defaults(self):
        """Test default values."""
        ctx = LogContext()
        assert ctx.service_name is None
        assert ctx.instance_id is None
        assert ctx.trace_id is None
        assert ctx.correlation_id is None
        assert ctx.operation is None
        assert ctx.component is None
        assert ctx.error_code is None
        assert ctx.error_type is None
        assert ctx.duration_ms is None

    def test_custom_values(self):
        """Test context with custom values."""
        ctx = LogContext(
            service_name="test-service",
            instance_id="instance-123",
            trace_id="trace-456",
            correlation_id="corr-789",
            operation="process_order",
            component="OrderProcessor",
            duration_ms=123.45,
        )
        assert ctx.service_name == "test-service"
        assert ctx.instance_id == "instance-123"
        assert ctx.trace_id == "trace-456"
        assert ctx.correlation_id == "corr-789"
        assert ctx.operation == "process_order"
        assert ctx.component == "OrderProcessor"
        assert ctx.duration_ms == 123.45

    def test_to_dict(self):
        """Test conversion to dictionary."""
        ctx = LogContext(
            service_name="test-service",
            operation="test-op",
        )
        result = ctx.to_dict()
        assert result == {
            "service_name": "test-service",
            "operation": "test-op",
        }
        # None values should be filtered out
        assert "instance_id" not in result
        assert "trace_id" not in result

    def test_with_error(self):
        """Test adding error context."""
        ctx = LogContext(service_name="test-service")

        # Create test exception
        try:
            raise ValueError("Test error")
        except ValueError as e:
            error_ctx = ctx.with_error(e)

        assert error_ctx.error_code == "ValueError"
        assert error_ctx.error_type == "builtins.ValueError"
        # Original context preserved
        assert error_ctx.service_name == "test-service"

    def test_with_operation(self):
        """Test adding operation context."""
        ctx = LogContext(service_name="test-service")

        # Add operation
        op_ctx = ctx.with_operation("process_order")
        assert op_ctx.operation == "process_order"
        assert op_ctx.service_name == "test-service"

        # Add operation with component
        op_ctx2 = ctx.with_operation("validate_order", "OrderValidator")
        assert op_ctx2.operation == "validate_order"
        assert op_ctx2.component == "OrderValidator"

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed for flexibility."""
        ctx = LogContext(
            service_name="test-service",
            custom_field="custom_value",  # type: ignore
            another_field=123,  # type: ignore
        )
        result = ctx.to_dict()
        assert result["custom_field"] == "custom_value"
        assert result["another_field"] == 123

    def test_duration_validation(self):
        """Test duration must be non-negative."""
        # Valid duration
        ctx = LogContext(duration_ms=100.5)
        assert ctx.duration_ms == 100.5

        # Invalid duration
        with pytest.raises(ValidationError):
            LogContext(duration_ms=-1.0)

    def test_immutability(self):
        """Test that context operations create new instances."""
        ctx1 = LogContext(service_name="service1")
        ctx2 = ctx1.with_operation("op1")
        ctx3 = ctx2.with_error(ValueError("test"))

        # Original contexts unchanged
        assert ctx1.operation is None
        assert ctx1.error_code is None
        assert ctx2.error_code is None

        # New context has all values
        assert ctx3.service_name == "service1"
        assert ctx3.operation == "op1"
        assert ctx3.error_code == "ValueError"

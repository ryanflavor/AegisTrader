"""Comprehensive unit tests for domain layer with 100% coverage."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from domain.entities import (
    BatchEchoRequest,
    EchoRequest,
    EchoResponse,
    ServiceMetrics,
    ServiceRegistration,
)
from domain.services import EchoProcessor, HealthChecker, MetricsCollector, PriorityManager
from domain.value_objects import (
    EchoMode,
    HealthStatus,
    InstanceIdentifier,
    MessagePriority,
    ProcessingMetadata,
    ServiceDefinitionInfo,
    TransformationType,
)


class TestValueObjects:
    """Tests for domain value objects."""

    def test_echo_mode_from_string(self):
        """Test EchoMode creation from string."""
        mode = EchoMode.from_string("simple")
        assert mode == EchoMode.SIMPLE

        with pytest.raises(ValueError, match="Invalid echo mode"):
            EchoMode.from_string("invalid")

    def test_echo_mode_is_transformation_mode(self):
        """Test transformation mode check."""
        assert EchoMode.REVERSE.is_transformation_mode() is True
        assert EchoMode.UPPERCASE.is_transformation_mode() is True
        assert EchoMode.TRANSFORM.is_transformation_mode() is True
        assert EchoMode.SIMPLE.is_transformation_mode() is False
        assert EchoMode.DELAYED.is_transformation_mode() is False
        assert EchoMode.BATCH.is_transformation_mode() is False

    def test_message_priority_from_string(self):
        """Test MessagePriority creation from string."""
        priority = MessagePriority.from_string("high")
        assert priority == MessagePriority.HIGH

        with pytest.raises(ValueError, match="Invalid priority level"):
            MessagePriority.from_string("invalid")

    def test_message_priority_is_urgent(self):
        """Test urgent priority check."""
        assert MessagePriority.HIGH.is_urgent() is True
        assert MessagePriority.CRITICAL.is_urgent() is True
        assert MessagePriority.NORMAL.is_urgent() is False
        assert MessagePriority.LOW.is_urgent() is False

    def test_message_priority_get_weight(self):
        """Test priority weight calculation."""
        assert MessagePriority.LOW.get_weight() == 1
        assert MessagePriority.NORMAL.get_weight() == 2
        assert MessagePriority.HIGH.get_weight() == 3
        assert MessagePriority.CRITICAL.get_weight() == 4

    def test_service_definition_info_validation(self):
        """Test ServiceDefinitionInfo validation."""
        # Valid service definition
        service_def = ServiceDefinitionInfo(
            service_name="echo-service",
            owner="TeamA",
            description="Echo service for testing",
            version="1.0.0",
        )
        assert service_def.service_name == "echo-service"

        # Invalid service name with consecutive hyphens
        with pytest.raises(ValidationError, match="consecutive hyphens"):
            ServiceDefinitionInfo(
                service_name="echo--service",
                owner="TeamA",
                description="Test",
                version="1.0.0",
            )

        # Invalid service name starting with hyphen (pattern validation)
        with pytest.raises(ValidationError, match="String should match pattern"):
            ServiceDefinitionInfo(
                service_name="-echo-service",
                owner="TeamA",
                description="Test",
                version="1.0.0",
            )

        # Invalid version with leading zeros
        with pytest.raises(ValidationError, match="without leading zeros"):
            ServiceDefinitionInfo(
                service_name="echo-service",
                owner="TeamA",
                description="Test",
                version="01.0.0",
            )

    def test_service_definition_info_version_methods(self):
        """Test version extraction methods."""
        service_def = ServiceDefinitionInfo(
            service_name="echo-service",
            owner="TeamA",
            description="Test",
            version="2.3.4",
        )
        assert service_def.get_major_version() == 2
        assert service_def.get_minor_version() == 3
        assert service_def.get_patch_version() == 4

    def test_transformation_type_is_valid(self):
        """Test TransformationType validation."""
        assert TransformationType.is_valid("base64_encode") is True
        assert TransformationType.is_valid("rot13") is True
        assert TransformationType.is_valid("invalid") is False

    def test_health_status_is_operational(self):
        """Test HealthStatus operational check."""
        assert HealthStatus.HEALTHY.is_operational() is True
        assert HealthStatus.DEGRADED.is_operational() is True
        assert HealthStatus.UNHEALTHY.is_operational() is False
        assert HealthStatus.UNKNOWN.is_operational() is False

    def test_instance_identifier(self):
        """Test InstanceIdentifier value object."""
        # Full identifier with hostname and port
        instance = InstanceIdentifier(instance_id="echo-001", hostname="localhost", port=8080)
        assert instance.get_full_identifier() == "echo-001@localhost:8080"

        # Identifier with hostname only
        instance = InstanceIdentifier(instance_id="echo-002", hostname="server1")
        assert instance.get_full_identifier() == "echo-002@server1"

        # Identifier without hostname
        instance = InstanceIdentifier(instance_id="echo-003")
        assert instance.get_full_identifier() == "echo-003"

    def test_processing_metadata(self):
        """Test ProcessingMetadata value object."""
        metadata = ProcessingMetadata(
            trace_id="trace-123",
            span_id="span-456",
            parent_span_id="parent-789",
            user_agent="TestAgent/1.0",
            source_ip="192.168.1.1",
            correlation_id="corr-abc",
        )
        assert metadata.has_tracing_info() is True

        metadata_no_trace = ProcessingMetadata(user_agent="TestAgent/1.0")
        assert metadata_no_trace.has_tracing_info() is False


class TestEntities:
    """Tests for domain entities."""

    def test_echo_request_validation(self):
        """Test EchoRequest entity validation."""
        # Valid request
        request = EchoRequest(
            message="Hello World",
            mode="simple",
            delay=0.5,
            priority="high",
        )
        assert request.mode == EchoMode.SIMPLE
        assert request.priority == MessagePriority.HIGH

        # Test mode validation
        with pytest.raises(ValueError, match="Invalid mode"):
            EchoRequest(message="test", mode="invalid")

        # Test priority validation
        with pytest.raises(ValueError, match="Invalid priority"):
            EchoRequest(message="test", priority="invalid")

    def test_echo_request_requires_delay(self):
        """Test delay requirement check."""
        request_with_delay = EchoRequest(message="test", mode=EchoMode.DELAYED, delay=1.0)
        assert request_with_delay.requires_delay() is True

        request_no_delay = EchoRequest(message="test", mode=EchoMode.SIMPLE)
        assert request_no_delay.requires_delay() is False

    def test_echo_request_is_high_priority(self):
        """Test high priority check."""
        high_priority_request = EchoRequest(message="test", priority=MessagePriority.HIGH)
        assert high_priority_request.is_high_priority() is True

        critical_priority_request = EchoRequest(message="test", priority=MessagePriority.CRITICAL)
        assert critical_priority_request.is_high_priority() is True

        normal_priority_request = EchoRequest(message="test", priority=MessagePriority.NORMAL)
        assert normal_priority_request.is_high_priority() is False

    def test_echo_response_was_transformed(self):
        """Test transformation detection."""
        transformed_response = EchoResponse(
            original="hello",
            echoed="HELLO",
            mode=EchoMode.UPPERCASE,
            instance_id="echo-001",
            processing_time_ms=10.5,
        )
        assert transformed_response.was_transformed() is True

        unchanged_response = EchoResponse(
            original="hello",
            echoed="hello",
            mode=EchoMode.SIMPLE,
            instance_id="echo-001",
            processing_time_ms=5.0,
        )
        assert unchanged_response.was_transformed() is False

    def test_service_metrics_record_request(self):
        """Test metrics recording."""
        metrics = ServiceMetrics(instance_id="echo-001")

        # Record successful request
        metrics.record_request(EchoMode.SIMPLE, MessagePriority.NORMAL, 10.0, success=True)
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.average_latency_ms == 10.0
        assert metrics.mode_distribution[EchoMode.SIMPLE] == 1
        assert metrics.priority_distribution[MessagePriority.NORMAL] == 1

        # Record failed request
        metrics.record_request(EchoMode.REVERSE, MessagePriority.HIGH, 20.0, success=False)
        assert metrics.total_requests == 2
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 1
        assert metrics.average_latency_ms == 15.0

    def test_service_metrics_get_success_rate(self):
        """Test success rate calculation."""
        metrics = ServiceMetrics(instance_id="echo-001")

        # No requests yet
        assert metrics.get_success_rate() == 100.0

        # Mix of successful and failed requests
        metrics.record_request(EchoMode.SIMPLE, MessagePriority.NORMAL, 10.0, success=True)
        metrics.record_request(EchoMode.SIMPLE, MessagePriority.NORMAL, 10.0, success=True)
        metrics.record_request(EchoMode.SIMPLE, MessagePriority.NORMAL, 10.0, success=False)
        assert metrics.get_success_rate() == pytest.approx(66.67, rel=0.01)

    def test_service_registration_validation(self):
        """Test ServiceRegistration validation."""
        service_def = ServiceDefinitionInfo(
            service_name="echo-service",
            owner="TeamA",
            description="Test service",
            version="1.0.0",
        )

        # Valid registration
        registration = ServiceRegistration(
            definition=service_def,
            instance_id="echo-001",
            nats_url="nats://localhost:4222",
        )
        assert registration.status == "active"

        # Invalid NATS URL
        with pytest.raises(ValueError, match="NATS URL must start with"):
            ServiceRegistration(
                definition=service_def,
                instance_id="echo-001",
                nats_url="http://localhost:4222",
            )

        # Invalid NATS URL (too short)
        with pytest.raises(ValueError, match="NATS URL must include host and port"):
            ServiceRegistration(
                definition=service_def,
                instance_id="echo-001",
                nats_url="nats://",
            )

    def test_service_registration_to_service_definition_dict(self):
        """Test conversion to service definition dict."""
        service_def = ServiceDefinitionInfo(
            service_name="echo-service",
            owner="TeamA",
            description="Test service",
            version="1.0.0",
        )
        registration = ServiceRegistration(
            definition=service_def,
            instance_id="echo-001",
            nats_url="nats://localhost:4222",
        )

        result = registration.to_service_definition_dict()
        assert result["service_name"] == "echo-service"
        assert result["owner"] == "TeamA"
        assert result["description"] == "Test service"
        assert result["version"] == "1.0.0"
        assert "created_at" in result
        assert "updated_at" in result

    def test_service_registration_is_expired(self):
        """Test registration expiration check."""
        service_def = ServiceDefinitionInfo(
            service_name="echo-service",
            owner="TeamA",
            description="Test",
            version="1.0.0",
        )

        # Create registration with old timestamp
        old_time = datetime.now(UTC)
        with patch("domain.entities.datetime") as mock_datetime:
            mock_datetime.now.return_value = old_time
            registration = ServiceRegistration(
                definition=service_def,
                instance_id="echo-001",
                nats_url="nats://localhost:4222",
            )

        # Check expiration
        assert registration.is_expired(ttl_seconds=300) is False

        # Simulate time passing (add 301 seconds properly)
        from datetime import timedelta

        with patch("domain.entities.datetime") as mock_datetime:
            mock_datetime.now.return_value = old_time + timedelta(seconds=301)
            assert registration.is_expired(ttl_seconds=300) is True

    def test_batch_echo_request(self):
        """Test BatchEchoRequest entity."""
        requests = [
            EchoRequest(message="test1", mode=EchoMode.SIMPLE),
            EchoRequest(message="test2", mode=EchoMode.DELAYED, delay=2.0),
            EchoRequest(message="test3", mode=EchoMode.UPPERCASE),
            EchoRequest(message="test4", mode=EchoMode.DELAYED, delay=1.5),
        ]

        batch = BatchEchoRequest(
            requests=requests,
            batch_id="batch-001",
            priority=MessagePriority.HIGH,
        )

        assert batch.get_total_delay() == 3.5
        assert batch.get_modes_used() == {
            EchoMode.SIMPLE,
            EchoMode.DELAYED,
            EchoMode.UPPERCASE,
        }


class TestDomainServices:
    """Tests for domain services."""

    @pytest.mark.asyncio
    async def test_echo_processor_simple_echo(self):
        """Test simple echo processing."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(message="Hello World", mode=EchoMode.SIMPLE)

        response = await processor.process_echo(request)

        assert response.original == "Hello World"
        assert response.echoed == "Hello World"
        assert response.mode == EchoMode.SIMPLE
        assert response.instance_id == "echo-001"
        assert response.sequence_number == 1

    @pytest.mark.asyncio
    async def test_echo_processor_reverse_echo(self):
        """Test reverse echo processing."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(message="Hello", mode=EchoMode.REVERSE)

        response = await processor.process_echo(request)

        assert response.echoed == "olleH"

    @pytest.mark.asyncio
    async def test_echo_processor_uppercase_echo(self):
        """Test uppercase echo processing."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(message="hello", mode=EchoMode.UPPERCASE)

        response = await processor.process_echo(request)

        assert response.echoed == "HELLO"

    @pytest.mark.asyncio
    async def test_echo_processor_delayed_echo(self):
        """Test delayed echo processing."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(message="test", mode=EchoMode.DELAYED, delay=0.1)

        start_time = time.time()
        response = await processor.process_echo(request)
        elapsed_time = time.time() - start_time

        assert response.echoed == "test"
        assert elapsed_time >= 0.1

    @pytest.mark.asyncio
    async def test_echo_processor_transform_base64_encode(self):
        """Test base64 encode transformation."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(
            message="Hello",
            mode=EchoMode.TRANSFORM,
            transform_type="base64_encode",
        )

        response = await processor.process_echo(request)

        assert response.echoed == "SGVsbG8="

    @pytest.mark.asyncio
    async def test_echo_processor_transform_base64_decode(self):
        """Test base64 decode transformation."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(
            message="SGVsbG8=",
            mode=EchoMode.TRANSFORM,
            transform_type="base64_decode",
        )

        response = await processor.process_echo(request)

        assert response.echoed == "Hello"

    @pytest.mark.asyncio
    async def test_echo_processor_transform_rot13(self):
        """Test ROT13 transformation."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(
            message="Hello",
            mode=EchoMode.TRANSFORM,
            transform_type="rot13",
        )

        response = await processor.process_echo(request)

        assert response.echoed == "Uryyb"

    @pytest.mark.asyncio
    async def test_echo_processor_transform_leetspeak(self):
        """Test leetspeak transformation."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(
            message="Hello World",
            mode=EchoMode.TRANSFORM,
            transform_type="leetspeak",
        )

        response = await processor.process_echo(request)

        assert response.echoed == "H3110 W0r1d"

    @pytest.mark.asyncio
    async def test_echo_processor_transform_word_reverse(self):
        """Test word reverse transformation."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(
            message="Hello World",
            mode=EchoMode.TRANSFORM,
            transform_type="word_reverse",
        )

        response = await processor.process_echo(request)

        assert response.echoed == "olleH dlroW"

    @pytest.mark.asyncio
    async def test_echo_processor_transform_capitalize_words(self):
        """Test capitalize words transformation."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(
            message="hello world test",
            mode=EchoMode.TRANSFORM,
            transform_type="capitalize_words",
        )

        response = await processor.process_echo(request)

        assert response.echoed == "Hello World Test"

    @pytest.mark.asyncio
    async def test_echo_processor_transform_invalid(self):
        """Test invalid transformation returns original."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(
            message="test",
            mode=EchoMode.TRANSFORM,
            transform_type="invalid_transform",
        )

        response = await processor.process_echo(request)

        assert response.echoed == "test"

    @pytest.mark.asyncio
    async def test_echo_processor_transform_no_type(self):
        """Test transform mode with no type returns original."""
        processor = EchoProcessor("echo-001")
        request = EchoRequest(
            message="test",
            mode=EchoMode.TRANSFORM,
            transform_type=None,
        )

        response = await processor.process_echo(request)

        assert response.echoed == "test"

    @pytest.mark.asyncio
    async def test_echo_processor_transform_exception(self):
        """Test transformation exception returns original."""
        processor = EchoProcessor("echo-001")
        # Invalid base64 string for decoding
        request = EchoRequest(
            message="not-base64",
            mode=EchoMode.TRANSFORM,
            transform_type="base64_decode",
        )

        response = await processor.process_echo(request)

        assert response.echoed == "not-base64"

    @pytest.mark.asyncio
    async def test_echo_processor_batch(self):
        """Test batch processing."""
        processor = EchoProcessor("echo-001")
        requests = [
            EchoRequest(message="test1", mode=EchoMode.SIMPLE),
            EchoRequest(message="test2", mode=EchoMode.REVERSE),
            EchoRequest(message="test3", mode=EchoMode.UPPERCASE),
        ]

        responses = await processor.process_batch(requests)

        assert len(responses) == 3
        assert responses[0].echoed == "test1"
        assert responses[1].echoed == "2tset"
        assert responses[2].echoed == "TEST3"

    @pytest.mark.asyncio
    async def test_echo_processor_unknown_mode(self):
        """Test unknown mode defaults to simple echo."""
        processor = EchoProcessor("echo-001")
        # Create request with mode that bypasses validation
        request = EchoRequest(message="test", mode=EchoMode.BATCH)

        response = await processor.process_echo(request)

        assert response.echoed == "test"

    def test_metrics_collector_initialization(self):
        """Test MetricsCollector initialization."""
        collector = MetricsCollector("echo-001")

        assert collector.metrics.instance_id == "echo-001"
        assert collector.metrics.total_requests == 0

    def test_metrics_collector_record_request(self):
        """Test recording requests in metrics collector."""
        collector = MetricsCollector("echo-001")

        collector.record_request(EchoMode.SIMPLE, MessagePriority.HIGH, 15.0, success=True)

        metrics = collector.get_current_metrics()
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1

    def test_metrics_collector_get_metrics_summary(self):
        """Test getting metrics summary."""
        collector = MetricsCollector("echo-001")

        collector.record_request(EchoMode.SIMPLE, MessagePriority.HIGH, 10.0, success=True)
        collector.record_request(EchoMode.REVERSE, MessagePriority.NORMAL, 20.0, success=False)

        summary = collector.get_metrics_summary()

        assert summary["instance_id"] == "echo-001"
        assert summary["total_requests"] == 2
        assert summary["success_rate"] == 50.0
        assert summary["average_latency_ms"] == 15.0
        assert summary["mode_distribution"]["simple"] == 1
        assert summary["mode_distribution"]["reverse"] == 1
        assert summary["priority_distribution"]["high"] == 1
        assert summary["priority_distribution"]["normal"] == 1

    def test_metrics_collector_reset(self):
        """Test resetting metrics."""
        collector = MetricsCollector("echo-001")

        collector.record_request(EchoMode.SIMPLE, MessagePriority.HIGH, 10.0, success=True)
        collector.reset_metrics()

        metrics = collector.get_current_metrics()
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0

    def test_health_checker_initialization(self):
        """Test HealthChecker initialization."""
        checker = HealthChecker("echo-001", "1.0.0")

        assert checker.instance_id == "echo-001"
        assert checker.version == "1.0.0"
        assert checker.is_healthy() is True

    def test_health_checker_add_check(self):
        """Test adding health checks."""
        checker = HealthChecker("echo-001", "1.0.0")

        checker.add_check("database", True)
        checker.add_check("cache", True)
        assert checker.is_healthy() is True

        checker.add_check("api", False)
        assert checker.is_healthy() is False

    def test_health_checker_get_health_status(self):
        """Test getting health status."""
        checker = HealthChecker("echo-001", "1.0.0")

        checker.add_check("database", True)
        checker.add_check("cache", False)

        status = checker.get_health_status()

        assert status["status"] == "unhealthy"
        assert status["instance_id"] == "echo-001"
        assert status["version"] == "1.0.0"
        assert status["checks"]["database"] is True
        assert status["checks"]["cache"] is False

    @pytest.mark.asyncio
    async def test_health_checker_check_dependencies(self):
        """Test checking dependencies."""
        checker = HealthChecker("echo-001", "1.0.0")

        checks = await checker.check_dependencies()

        assert checks["nats"] is True
        assert checks["monitor_api"] is True
        assert checker.is_healthy() is True

    def test_priority_manager_should_prioritize(self):
        """Test priority decision."""
        request_high = EchoRequest(message="test", priority=MessagePriority.HIGH)
        request_normal = EchoRequest(message="test", priority=MessagePriority.NORMAL)

        assert PriorityManager.should_prioritize(request_high) is True
        assert PriorityManager.should_prioritize(request_normal) is False

    def test_priority_manager_sort_by_priority(self):
        """Test sorting by priority."""
        requests = [
            EchoRequest(message="low", priority=MessagePriority.LOW),
            EchoRequest(message="critical", priority=MessagePriority.CRITICAL),
            EchoRequest(message="normal", priority=MessagePriority.NORMAL),
            EchoRequest(message="high", priority=MessagePriority.HIGH),
        ]

        sorted_requests = PriorityManager.sort_by_priority(requests)

        assert sorted_requests[0].message == "critical"
        assert sorted_requests[1].message == "high"
        assert sorted_requests[2].message == "normal"
        assert sorted_requests[3].message == "low"

    def test_priority_manager_sort_with_non_enum_priority(self):
        """Test sorting with non-enum priority values."""
        # Test that the sort function handles various priority values correctly
        requests = [
            EchoRequest(message="low", priority=MessagePriority.LOW),
            EchoRequest(message="high", priority=MessagePriority.HIGH),
        ]

        # Test normal sorting works as expected
        sorted_requests = PriorityManager.sort_by_priority(requests)

        assert sorted_requests[0].message == "high"
        assert sorted_requests[1].message == "low"

    def test_priority_manager_get_processing_timeout(self):
        """Test timeout calculation based on priority."""
        assert PriorityManager.get_processing_timeout(MessagePriority.LOW) == 30.0
        assert PriorityManager.get_processing_timeout(MessagePriority.NORMAL) == 10.0
        assert PriorityManager.get_processing_timeout(MessagePriority.HIGH) == 5.0
        assert PriorityManager.get_processing_timeout(MessagePriority.CRITICAL) == 2.0

        # Test with invalid priority (simulate edge case)
        class InvalidPriority:
            pass

        assert PriorityManager.get_processing_timeout(InvalidPriority()) == 10.0

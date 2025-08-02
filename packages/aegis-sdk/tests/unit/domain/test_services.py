"""Comprehensive tests for domain services following TDD principles."""

import pytest
from aegis_sdk.domain.services import (
    HealthCheckService,
    MessageRoutingService,
    MetricsNamingService,
)
from aegis_sdk.domain.value_objects import MethodName, ServiceName

from tests.builders import CommandBuilder, EventBuilder, RPCRequestBuilder


class TestMessageRoutingService:
    """Test cases for MessageRoutingService domain service."""

    def test_extract_service_and_method_with_full_target(self):
        """Test extracting service and method from RPC request with full target."""
        request = (
            RPCRequestBuilder().with_target("user-service.get_user").with_method("get_user").build()
        )

        service, method = MessageRoutingService.extract_service_and_method(request)

        assert isinstance(service, ServiceName)
        assert service.value == "user-service"
        assert isinstance(method, MethodName)
        assert method.value == "get_user"

    def test_extract_service_and_method_with_simple_target(self):
        """Test extracting service and method from RPC request with simple target."""
        request = RPCRequestBuilder().with_target("user-service").with_method("get_user").build()

        service, method = MessageRoutingService.extract_service_and_method(request)

        assert service.value == "user-service"
        assert method.value == "get_user"

    def test_extract_service_and_method_with_no_target(self):
        """Test extracting service and method when no target is specified."""
        request = RPCRequestBuilder().with_target(None).with_method("get_user").build()
        request.target = None  # Explicitly set to None

        service, method = MessageRoutingService.extract_service_and_method(request)

        assert service.value == "unknown"
        assert method.value == "get_user"

    def test_extract_service_and_method_with_complex_target(self):
        """Test extracting service from target with multiple dots."""
        request = (
            RPCRequestBuilder().with_target("api.v2.user-service").with_method("get_user").build()
        )

        service, method = MessageRoutingService.extract_service_and_method(request)

        # Should take the first part as service name
        assert service.value == "api"
        assert method.value == "get_user"

    def test_extract_command_target_with_target(self):
        """Test extracting target service from command."""
        command = CommandBuilder().with_target("worker-service").build()

        service = MessageRoutingService.extract_command_target(command)

        assert isinstance(service, ServiceName)
        assert service.value == "worker-service"

    def test_extract_command_target_without_target(self):
        """Test extracting target when command has no target."""
        command = CommandBuilder().build()
        command.target = None

        service = MessageRoutingService.extract_command_target(command)

        assert service.value == "unknown"

    def test_create_event_subject(self):
        """Test creating event subject for routing."""
        subject = MessageRoutingService.create_event_subject("order", "created")

        assert subject == "events.order.created"

    def test_create_event_subject_validates_format(self):
        """Test that create_event_subject validates the event type format."""
        # Valid event subject
        subject = MessageRoutingService.create_event_subject("user_profile", "updated")
        assert subject == "events.user_profile.updated"

        # Invalid format should raise ValidationError
        with pytest.raises(ValueError) as exc_info:
            MessageRoutingService.create_event_subject("order@", "created")
        assert "Invalid event type" in str(exc_info.value)


class TestMetricsNamingService:
    """Test cases for MetricsNamingService domain service."""

    def test_rpc_metric_name(self):
        """Test generating RPC metric names."""
        service = ServiceName(value="user-service")
        method = MethodName(value="get_user")

        # Success metric
        metric = MetricsNamingService.rpc_metric_name(service, method, "success")
        assert metric == "rpc.user-service.get_user.success"

        # Error metric
        metric = MetricsNamingService.rpc_metric_name(service, method, "error")
        assert metric == "rpc.user-service.get_user.error"

        # Timeout metric
        metric = MetricsNamingService.rpc_metric_name(service, method, "timeout")
        assert metric == "rpc.user-service.get_user.timeout"

    def test_rpc_client_metric_name(self):
        """Test generating RPC client metric names."""
        service = ServiceName(value="payment-service")
        method = MethodName(value="process_payment")

        metric = MetricsNamingService.rpc_client_metric_name(service, method, "latency")
        assert metric == "rpc.client.payment-service.process_payment.latency"

    def test_event_metric_name(self):
        """Test generating event metric names."""
        event = EventBuilder().with_domain("order").with_type("created").build()

        # Published metric
        metric = MetricsNamingService.event_metric_name(event, "published")
        assert metric == "events.published.order.created"

        # Processed metric
        metric = MetricsNamingService.event_metric_name(event, "processed")
        assert metric == "events.processed.order.created"

    def test_command_metric_name(self):
        """Test generating command metric names."""
        service = ServiceName(value="worker-service")

        # Processed metric
        metric = MetricsNamingService.command_metric_name(service, "resize_image", "processed")
        assert metric == "commands.processed.worker-service.resize_image"

        # Send metric
        metric = MetricsNamingService.command_metric_name(service, "generate_report", "send")
        assert metric == "commands.send.worker-service.generate_report"

    def test_metric_names_are_consistent(self):
        """Test that metric names follow consistent patterns."""
        service = ServiceName(value="test-service")
        method = MethodName(value="test_method")

        # All RPC metrics should start with "rpc."
        assert MetricsNamingService.rpc_metric_name(service, method, "test").startswith("rpc.")
        assert MetricsNamingService.rpc_client_metric_name(service, method, "test").startswith(
            "rpc.client."
        )

        # Event metrics should start with "events."
        event = EventBuilder().build()
        assert MetricsNamingService.event_metric_name(event, "test").startswith("events.")

        # Command metrics should start with "commands."
        assert MetricsNamingService.command_metric_name(service, "cmd", "test").startswith(
            "commands."
        )


class TestHealthCheckService:
    """Test cases for HealthCheckService domain service."""

    def test_is_healthy_with_recent_heartbeat(self):
        """Test that service is healthy when heartbeat is recent."""
        service = HealthCheckService(heartbeat_timeout_seconds=30.0)

        current_time = 1000.0
        last_heartbeat = 995.0  # 5 seconds ago

        assert service.is_healthy(last_heartbeat, current_time) is True

    def test_is_unhealthy_with_old_heartbeat(self):
        """Test that service is unhealthy when heartbeat is too old."""
        service = HealthCheckService(heartbeat_timeout_seconds=30.0)

        current_time = 1000.0
        last_heartbeat = 960.0  # 40 seconds ago

        assert service.is_healthy(last_heartbeat, current_time) is False

    def test_is_healthy_at_boundary(self):
        """Test health check at the timeout boundary."""
        service = HealthCheckService(heartbeat_timeout_seconds=30.0)

        current_time = 1000.0
        last_heartbeat = 970.1  # Just under 30 seconds

        assert service.is_healthy(last_heartbeat, current_time) is True

        last_heartbeat = 970.0  # Exactly 30 seconds
        assert service.is_healthy(last_heartbeat, current_time) is False

    def test_custom_timeout(self):
        """Test health check with custom timeout."""
        service = HealthCheckService(heartbeat_timeout_seconds=10.0)

        current_time = 1000.0
        last_heartbeat = 992.0  # 8 seconds ago

        assert service.is_healthy(last_heartbeat, current_time) is True

        last_heartbeat = 989.0  # 11 seconds ago
        assert service.is_healthy(last_heartbeat, current_time) is False

    def test_calculate_health_score_perfect(self):
        """Test health score calculation with perfect metrics."""
        service = HealthCheckService()

        metrics = {
            "counters": {
                "rpc.service.method.success": 100,
                "rpc.service.method.error": 0,
                "events.processed": 50,
                "events.errors": 0,
            },
            "summaries": {"rpc.latency": {"p99": 100}},  # Low latency
        }

        score = service.calculate_health_score(metrics)
        assert score == 1.0

    def test_calculate_health_score_with_errors(self):
        """Test health score calculation with some errors."""
        service = HealthCheckService()

        metrics = {
            "counters": {
                "rpc.service.method.success": 90,
                "rpc.service.method.error": 10,  # 10% error rate
                "events.processed": 100,
                "events.errors": 0,
            }
        }

        score = service.calculate_health_score(metrics)
        # Score should be reduced by error rate: 1.0 * 0.9 = 0.9
        assert score == pytest.approx(0.9, rel=1e-2)

    def test_calculate_health_score_with_event_errors(self):
        """Test health score calculation with event processing errors."""
        service = HealthCheckService()

        metrics = {
            "counters": {
                "rpc.service.method.success": 100,
                "rpc.service.method.error": 0,
                "events.processed": 80,
                "events.errors": 20,  # 20% error rate
            }
        }

        score = service.calculate_health_score(metrics)
        # Score should be reduced by event error rate: 1.0 * 0.8 = 0.8
        assert score == pytest.approx(0.8, rel=1e-2)

    def test_calculate_health_score_with_high_latency(self):
        """Test health score calculation with high latency."""
        service = HealthCheckService()

        metrics = {
            "counters": {},
            "summaries": {"rpc.service.method": {"p99": 1500}},  # Very high latency
        }

        score = service.calculate_health_score(metrics)
        # Score should be reduced by 20% for >1000ms latency
        assert score == pytest.approx(0.8, rel=1e-2)

    def test_calculate_health_score_with_moderate_latency(self):
        """Test health score calculation with moderate latency."""
        service = HealthCheckService()

        metrics = {
            "counters": {},
            "summaries": {"rpc.service.method": {"p99": 750}},  # Moderate latency
        }

        score = service.calculate_health_score(metrics)
        # Score should be reduced by 10% for >500ms latency
        assert score == pytest.approx(0.9, rel=1e-2)

    def test_calculate_health_score_with_combined_issues(self):
        """Test health score calculation with multiple issues."""
        service = HealthCheckService()

        metrics = {
            "counters": {
                "rpc.service.method.success": 90,
                "rpc.service.method.error": 10,  # 10% error rate
                "events.processed": 90,
                "events.errors": 10,  # 10% error rate
            },
            "summaries": {"rpc.service.method": {"p99": 1200}},  # High latency
        }

        score = service.calculate_health_score(metrics)
        # Combined effect: 1.0 * 0.9 (RPC errors) * 0.9 (event errors) * 0.8 (latency)
        assert score == pytest.approx(0.648, rel=1e-2)

    def test_calculate_health_score_empty_metrics(self):
        """Test health score calculation with empty metrics."""
        service = HealthCheckService()

        score = service.calculate_health_score({})
        assert score == 1.0  # Perfect score when no metrics

    def test_calculate_health_score_bounds(self):
        """Test that health score is always between 0 and 1."""
        service = HealthCheckService()

        # All failures
        metrics = {
            "counters": {
                "rpc.service.method.success": 0,
                "rpc.service.method.error": 100,
                "events.processed": 0,
                "events.errors": 100,
            }
        }

        score = service.calculate_health_score(metrics)
        assert 0.0 <= score <= 1.0

    def test_health_check_service_initialization(self):
        """Test HealthCheckService initialization with different timeouts."""
        # Default timeout
        service1 = HealthCheckService()
        assert service1.heartbeat_timeout == 30.0

        # Custom timeout
        service2 = HealthCheckService(heartbeat_timeout_seconds=60.0)
        assert service2.heartbeat_timeout == 60.0

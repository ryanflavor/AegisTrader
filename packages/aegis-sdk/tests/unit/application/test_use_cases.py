"""Comprehensive tests for application use cases following TDD principles."""

from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from aegis_sdk.application.use_cases import (
    CommandProcessingRequest,
    CommandProcessingUseCase,
    RPCCallRequest,
    RPCCallUseCase,
    ServiceHeartbeatRequest,
    ServiceHeartbeatUseCase,
    ServiceRegistrationRequest,
    ServiceRegistrationResponse,
    ServiceRegistrationUseCase,
)
from aegis_sdk.domain.aggregates import ServiceAggregate, ServiceStatus
from aegis_sdk.domain.models import Command, RPCResponse
from aegis_sdk.domain.services import (
    HealthCheckService,
    MessageRoutingService,
    MetricsNamingService,
)
from aegis_sdk.domain.value_objects import InstanceId, ServiceName
from aegis_sdk.infrastructure.in_memory_repository import InMemoryServiceRepository
from aegis_sdk.ports.message_bus import MessageBusPort
from aegis_sdk.ports.metrics import MetricsPort


@pytest.fixture
def mock_message_bus():
    """Create a mock message bus."""
    bus = Mock(spec=MessageBusPort)
    bus.register_service = AsyncMock()
    bus.unregister_service = AsyncMock()
    bus.send_heartbeat = AsyncMock()
    bus.publish_event = AsyncMock()
    bus.call_rpc = AsyncMock()
    return bus


@pytest.fixture
def mock_metrics():
    """Create a mock metrics port."""
    metrics = Mock(spec=MetricsPort)
    metrics.increment = Mock()
    metrics.gauge = Mock()
    metrics.timer = Mock(return_value=Mock(__enter__=Mock(), __exit__=Mock()))
    return metrics


@pytest.fixture
def in_memory_repository():
    """Create an in-memory repository."""
    return InMemoryServiceRepository()


@pytest.fixture
def health_service():
    """Create a health check service."""
    return HealthCheckService()


@pytest.fixture
def routing_service():
    """Create a message routing service."""
    return MessageRoutingService()


@pytest.fixture
def naming_service():
    """Create a metrics naming service."""
    return MetricsNamingService()


class TestServiceRegistrationUseCase:
    """Test cases for service registration use case."""

    @pytest.mark.asyncio
    async def test_successful_registration(
        self, mock_message_bus, mock_metrics, in_memory_repository
    ):
        """Test successful service registration."""
        # Arrange
        use_case = ServiceRegistrationUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            service_repository=in_memory_repository,
        )

        request = ServiceRegistrationRequest(
            service_name="user-service",
            instance_id="instance-123",
            version="2.0.0",
            metadata={"region": "us-east-1"},
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert isinstance(response, ServiceRegistrationResponse)
        assert response.service_name == "user-service"
        assert response.instance_id == "instance-123"
        assert response.status == "ACTIVE"
        assert response.aggregate_id == "user-service/instance-123"

        # Verify message bus called
        mock_message_bus.register_service.assert_called_once_with("user-service", "instance-123")

        # Verify metrics tracked
        mock_metrics.increment.assert_any_call("services.registered")
        mock_metrics.increment.assert_any_call("services.user-service.instances")

        # Verify domain event published
        mock_message_bus.publish_event.assert_called_once()
        event_call = mock_message_bus.publish_event.call_args[0][0]
        assert event_call.domain == "service"
        assert event_call.event_type == "service.registered"
        assert event_call.payload["service_name"] == "user-service"

        # Verify aggregate saved
        saved = await in_memory_repository.get(
            ServiceName(value="user-service"),
            InstanceId(value="instance-123"),
        )
        assert saved is not None
        assert saved.version == "2.0.0"

    @pytest.mark.asyncio
    async def test_registration_with_invalid_service_name(
        self, mock_message_bus, mock_metrics, in_memory_repository
    ):
        """Test registration fails with invalid service name."""
        use_case = ServiceRegistrationUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            service_repository=in_memory_repository,
        )

        request = ServiceRegistrationRequest(
            service_name="123-invalid",  # Invalid: starts with number
            instance_id="instance-123",
        )

        # Act & Assert
        with pytest.raises(ValidationError):
            await use_case.execute(request)

        # Verify nothing was saved or published
        assert len(in_memory_repository.get_all()) == 0
        mock_message_bus.register_service.assert_not_called()
        mock_message_bus.publish_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_registration_tracks_multiple_events(
        self, mock_message_bus, mock_metrics, in_memory_repository
    ):
        """Test registration publishes all domain events."""
        use_case = ServiceRegistrationUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            service_repository=in_memory_repository,
        )

        # Create request with metadata
        request = ServiceRegistrationRequest(
            service_name="api-gateway",
            instance_id="gw-001",
            metadata={"port": 8080, "protocols": ["http", "grpc"]},
        )

        # Act
        await use_case.execute(request)

        # The aggregate creation should generate one event
        assert mock_message_bus.publish_event.call_count == 1


class TestServiceHeartbeatUseCase:
    """Test cases for service heartbeat use case."""

    @pytest.mark.asyncio
    async def test_heartbeat_healthy_service(
        self, mock_message_bus, mock_metrics, in_memory_repository, health_service
    ):
        """Test heartbeat processing for healthy service."""
        # First register a service
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="test-123"),
        )
        await in_memory_repository.save(aggregate)
        aggregate.mark_events_committed()  # Clear registration event

        # Create use case
        use_case = ServiceHeartbeatUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            service_repository=in_memory_repository,
            health_service=health_service,
        )

        request = ServiceHeartbeatRequest(
            service_name="test-service",
            instance_id="test-123",
            metrics={"cpu_usage": 45.0, "memory_usage": 60.0},
        )

        # Act
        await use_case.execute(request)

        # Assert
        mock_message_bus.send_heartbeat.assert_called_once_with("test-service", "test-123")

        mock_metrics.increment.assert_any_call("heartbeats.processed")
        mock_metrics.increment.assert_any_call("heartbeats.test-service")

        # Verify aggregate updated
        old_heartbeat = aggregate.last_heartbeat

        # Small sleep to ensure time passes
        import asyncio

        await asyncio.sleep(0.01)

        # Execute again to get a different heartbeat time
        await use_case.execute(request)

        updated = await in_memory_repository.get(
            ServiceName(value="test-service"),
            InstanceId(value="test-123"),
        )
        assert updated.last_heartbeat > old_heartbeat

    @pytest.mark.asyncio
    async def test_heartbeat_marks_unhealthy(
        self, mock_message_bus, mock_metrics, in_memory_repository, health_service
    ):
        """Test heartbeat marks service unhealthy when metrics exceed thresholds."""
        # Register healthy service
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="test-123"),
        )
        await in_memory_repository.save(aggregate)
        aggregate.mark_events_committed()

        use_case = ServiceHeartbeatUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            service_repository=in_memory_repository,
            health_service=health_service,
        )

        # Provide metrics that will result in low health score
        # The health score calculation looks for error counters
        request = ServiceHeartbeatRequest(
            service_name="test-service",
            instance_id="test-123",
            metrics={
                "counters": {
                    "rpc.test.success": 10,
                    "rpc.test.error": 90,  # 90% error rate
                }
            },
        )

        # Act
        await use_case.execute(request)

        # Assert
        updated = await in_memory_repository.get(
            ServiceName(value="test-service"),
            InstanceId(value="test-123"),
        )
        assert updated.status == ServiceStatus.UNHEALTHY

        # Verify unhealthy event published
        event_calls = mock_message_bus.publish_event.call_args_list
        assert any(call[0][0].event_type == "service.unhealthy" for call in event_calls)

    @pytest.mark.asyncio
    async def test_heartbeat_recovers_unhealthy_service(
        self, mock_message_bus, mock_metrics, in_memory_repository, health_service
    ):
        """Test heartbeat recovers unhealthy service when metrics improve."""
        # Create unhealthy service
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="test-123"),
        )
        aggregate.mark_unhealthy("High CPU")
        await in_memory_repository.save(aggregate)
        aggregate.mark_events_committed()

        use_case = ServiceHeartbeatUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            service_repository=in_memory_repository,
            health_service=health_service,
        )

        # Good metrics
        request = ServiceHeartbeatRequest(
            service_name="test-service",
            instance_id="test-123",
            metrics={"cpu_usage": 30.0, "memory_usage": 40.0},
        )

        # Act
        await use_case.execute(request)

        # Assert
        updated = await in_memory_repository.get(
            ServiceName(value="test-service"),
            InstanceId(value="test-123"),
        )
        assert updated.status == ServiceStatus.ACTIVE

        # Verify recovery event
        event_calls = mock_message_bus.publish_event.call_args_list
        assert any(call[0][0].event_type == "service.recovered" for call in event_calls)

    @pytest.mark.asyncio
    async def test_heartbeat_service_not_found(
        self, mock_message_bus, mock_metrics, in_memory_repository, health_service
    ):
        """Test heartbeat fails when service not found."""
        use_case = ServiceHeartbeatUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            service_repository=in_memory_repository,
            health_service=health_service,
        )

        request = ServiceHeartbeatRequest(
            service_name="unknown-service",
            instance_id="unknown-123",
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Service not found"):
            await use_case.execute(request)


class TestRPCCallUseCase:
    """Test cases for RPC call use case."""

    @pytest.mark.asyncio
    async def test_successful_rpc_call(
        self, mock_message_bus, mock_metrics, routing_service, naming_service
    ):
        """Test successful RPC call execution."""
        # Setup mock response
        mock_message_bus.call_rpc = AsyncMock(
            return_value=RPCResponse(
                correlation_id="123",
                success=True,
                result={"user_id": 42, "name": "John"},
            )
        )

        use_case = RPCCallUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            routing_service=routing_service,
            naming_service=naming_service,
        )

        request = RPCCallRequest(
            caller_service="api-gateway",
            caller_instance="gw-001",
            target_service="user-service",
            method="get_user",
            params={"user_id": 42},
            timeout=10.0,
        )

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result == {"user_id": 42, "name": "John"}

        # Verify RPC request made
        mock_message_bus.call_rpc.assert_called_once()
        rpc_request = mock_message_bus.call_rpc.call_args[0][0]
        assert rpc_request.target == "user-service"
        assert rpc_request.method == "get_user"
        assert rpc_request.params == {"user_id": 42}

        # Verify metrics
        mock_metrics.timer.assert_called_with("rpc.client.user-service.get_user")
        mock_metrics.increment.assert_called_with("rpc.client.user-service.get_user.success")

    @pytest.mark.asyncio
    async def test_rpc_call_failure(
        self, mock_message_bus, mock_metrics, routing_service, naming_service
    ):
        """Test RPC call handles failures properly."""
        # Setup mock error response
        mock_message_bus.call_rpc = AsyncMock(
            return_value=RPCResponse(
                correlation_id="123",
                success=False,
                error="User not found",
            )
        )

        use_case = RPCCallUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            routing_service=routing_service,
            naming_service=naming_service,
        )

        request = RPCCallRequest(
            caller_service="api-gateway",
            caller_instance="gw-001",
            target_service="user-service",
            method="get_user",
            params={"user_id": 999},
        )

        # Act & Assert
        with pytest.raises(Exception, match="RPC call failed: User not found"):
            await use_case.execute(request)

        # Verify metrics
        mock_metrics.increment.assert_called_with("rpc.client.user-service.get_user.error")

    @pytest.mark.asyncio
    async def test_rpc_call_timeout(
        self, mock_message_bus, mock_metrics, routing_service, naming_service
    ):
        """Test RPC call handles timeouts."""
        # Setup mock timeout
        mock_message_bus.call_rpc = AsyncMock(side_effect=TimeoutError("Request timed out"))

        use_case = RPCCallUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            routing_service=routing_service,
            naming_service=naming_service,
        )

        request = RPCCallRequest(
            caller_service="api-gateway",
            caller_instance="gw-001",
            target_service="slow-service",
            method="slow_method",
            timeout=1.0,
        )

        # Act & Assert
        with pytest.raises(TimeoutError):
            await use_case.execute(request)

        # Verify metrics
        mock_metrics.increment.assert_called_with("rpc.client.slow-service.slow_method.timeout")


class TestCommandProcessingUseCase:
    """Test cases for command processing use case."""

    @pytest.mark.asyncio
    async def test_successful_command_processing(
        self, mock_message_bus, mock_metrics, in_memory_repository
    ):
        """Test successful command processing with progress."""
        use_case = CommandProcessingUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            repository=in_memory_repository,
        )

        command = Command(
            command="process_batch",
            payload={"batch_id": "batch-123", "size": 100},
            source="scheduler",
            target="worker-service",
        )

        request = CommandProcessingRequest(
            command=command,
            handler_service="worker-service",
            handler_instance="worker-001",
        )

        # Mock handler
        async def mock_handler(cmd: Command, progress: callable):
            await progress(25, "Starting")
            await progress(50, "Processing")
            await progress(75, "Finalizing")
            await progress(100, "Complete")
            return {"processed": 100, "failed": 0}

        # Act
        result = await use_case.execute(request, mock_handler)

        # Assert
        assert result == {"processed": 100, "failed": 0}

        # Verify progress events
        progress_calls = [
            call
            for call in mock_message_bus.publish_event.call_args_list
            if call[0][0].event_type == "progress"
        ]
        assert len(progress_calls) == 4

        # Verify completion event
        completion_calls = [
            call
            for call in mock_message_bus.publish_event.call_args_list
            if call[0][0].event_type == "completed"
        ]
        assert len(completion_calls) == 1
        completion_event = completion_calls[0][0][0]
        assert completion_event.payload["result"] == {"processed": 100, "failed": 0}

        # Verify metrics
        mock_metrics.timer.assert_called_with("commands.worker-service.process_batch")
        mock_metrics.increment.assert_called_with("commands.worker-service.process_batch.success")

    @pytest.mark.asyncio
    async def test_command_processing_failure(
        self, mock_message_bus, mock_metrics, in_memory_repository
    ):
        """Test command processing handles failures properly."""
        use_case = CommandProcessingUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            repository=in_memory_repository,
        )

        command = Command(
            command="failing_command",
            payload={"will": "fail"},
            source="scheduler",
            target="worker-service",
        )

        request = CommandProcessingRequest(
            command=command,
            handler_service="worker-service",
            handler_instance="worker-001",
        )

        # Mock failing handler
        async def failing_handler(cmd: Command, progress: callable):
            await progress(25, "Starting")
            raise ValueError("Processing failed")

        # Act & Assert
        with pytest.raises(ValueError, match="Processing failed"):
            await use_case.execute(request, failing_handler)

        # Verify failure event
        failure_calls = [
            call
            for call in mock_message_bus.publish_event.call_args_list
            if call[0][0].event_type == "failed"
        ]
        assert len(failure_calls) == 1
        failure_event = failure_calls[0][0][0]
        assert "Processing failed" in failure_event.payload["error"]

        # Verify metrics
        mock_metrics.increment.assert_called_with("commands.worker-service.failing_command.error")

    @pytest.mark.asyncio
    async def test_command_progress_tracking(
        self, mock_message_bus, mock_metrics, in_memory_repository
    ):
        """Test command progress is properly tracked."""
        use_case = CommandProcessingUseCase(
            message_bus=mock_message_bus,
            metrics=mock_metrics,
            repository=in_memory_repository,
        )

        command = Command(
            command="track_progress",
            payload={},
            source="test",
            target="worker",
        )

        request = CommandProcessingRequest(
            command=command,
            handler_service="worker",
            handler_instance="w-001",
        )

        progress_values = []

        async def tracking_handler(cmd: Command, progress: callable):
            for i in range(0, 101, 10):
                await progress(i, f"Step {i // 10}")
                progress_values.append(i)
            return {"steps": 11}

        # Act
        await use_case.execute(request, tracking_handler)

        # Assert progress was tracked
        assert progress_values == list(range(0, 101, 10))

        # Verify gauge calls
        gauge_calls = [
            call for call in mock_metrics.gauge.call_args_list if "progress" in call[0][0]
        ]
        assert len(gauge_calls) == 11  # 0, 10, 20, ..., 100

"""
Comprehensive unit tests for Gateway port interfaces
Testing interface contracts and implementation requirements
"""

from __future__ import annotations

import inspect
from abc import ABC
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from domain.gateway.models import Gateway
from domain.gateway.ports import EventPublisher, GatewayPort, GatewayRepository
from domain.gateway.value_objects import (
    AuthenticationCredentials,
    ConnectionState,
    GatewayConfig,
    GatewayId,
    GatewayType,
)
from domain.shared.events import DomainEvent


class TestGatewayPortInterface:
    """Test suite for GatewayPort interface contract"""

    def test_gateway_port_is_abstract(self):
        """Test that GatewayPort is an abstract base class"""
        assert issubclass(GatewayPort, ABC)

        # Cannot instantiate abstract class
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            GatewayPort()

    def test_gateway_port_abstract_methods(self):
        """Test that GatewayPort defines all required abstract methods"""
        abstract_methods = {
            "connect",
            "disconnect",
            "subscribe",
            "unsubscribe",
            "is_connected",
            "send_heartbeat",
            "get_connection_status",
        }

        # Get actual abstract methods
        actual_abstract = {
            name
            for name, method in inspect.getmembers(GatewayPort)
            if getattr(method, "__isabstractmethod__", False)
        }

        assert actual_abstract == abstract_methods

    def test_gateway_port_method_signatures(self):
        """Test that GatewayPort methods have correct signatures"""
        # Test connect method signature
        connect_sig = inspect.signature(GatewayPort.connect)
        assert "credentials" in connect_sig.parameters
        assert (
            connect_sig.parameters["credentials"].annotation == "AuthenticationCredentials | None"
        )

        # Test subscribe/unsubscribe signature
        subscribe_sig = inspect.signature(GatewayPort.subscribe)
        assert "symbols" in subscribe_sig.parameters
        assert subscribe_sig.parameters["symbols"].annotation == "list[str]"

        unsubscribe_sig = inspect.signature(GatewayPort.unsubscribe)
        assert "symbols" in unsubscribe_sig.parameters
        assert unsubscribe_sig.parameters["symbols"].annotation == "list[str]"

        # Test is_connected return type
        is_connected_sig = inspect.signature(GatewayPort.is_connected)
        assert is_connected_sig.return_annotation == "bool"

        # Test get_connection_status return type
        status_sig = inspect.signature(GatewayPort.get_connection_status)
        assert status_sig.return_annotation == "dict"

    def test_concrete_implementation_must_implement_all_methods(self):
        """Test that concrete implementations must implement all abstract methods"""

        # Create incomplete implementation
        class IncompleteGateway(GatewayPort):
            async def connect(self, credentials=None):
                pass

            async def disconnect(self):
                pass

            # Missing other required methods

        # Should not be able to instantiate
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteGateway()

    def test_complete_implementation_can_be_instantiated(self):
        """Test that complete implementations can be instantiated"""

        class CompleteGateway(GatewayPort):
            async def connect(self, credentials=None):
                return None

            async def disconnect(self):
                return None

            async def subscribe(self, symbols):
                return None

            async def unsubscribe(self, symbols):
                return None

            def is_connected(self):
                return True

            async def send_heartbeat(self):
                return None

            async def get_connection_status(self):
                return {}

        # Should be able to instantiate
        gateway = CompleteGateway()
        assert isinstance(gateway, GatewayPort)
        assert gateway.is_connected() is True

    @pytest.mark.asyncio
    async def test_mock_gateway_port(self):
        """Test creating a mock GatewayPort for testing"""
        mock_gateway = Mock(spec=GatewayPort)
        mock_gateway.connect = AsyncMock()
        mock_gateway.disconnect = AsyncMock()
        mock_gateway.subscribe = AsyncMock()
        mock_gateway.unsubscribe = AsyncMock()
        mock_gateway.is_connected = Mock(return_value=True)
        mock_gateway.send_heartbeat = AsyncMock()
        mock_gateway.get_connection_status = AsyncMock(return_value={"status": "connected"})

        # Test mock usage
        await mock_gateway.connect(
            AuthenticationCredentials(
                user_id="test_user",
                password="test_pass",
                broker_id="test_broker",
            )
        )
        mock_gateway.connect.assert_called_once()

        assert mock_gateway.is_connected() is True

        await mock_gateway.subscribe(["IF2401", "IC2401"])
        mock_gateway.subscribe.assert_called_once_with(["IF2401", "IC2401"])

        status = await mock_gateway.get_connection_status()
        assert status == {"status": "connected"}


class TestGatewayRepositoryInterface:
    """Test suite for GatewayRepository interface contract"""

    def test_gateway_repository_is_abstract(self):
        """Test that GatewayRepository is an abstract base class"""
        assert issubclass(GatewayRepository, ABC)

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            GatewayRepository()

    def test_gateway_repository_abstract_methods(self):
        """Test that GatewayRepository defines all required abstract methods"""
        abstract_methods = {
            "save",
            "get",
            "list_active",
            "update_heartbeat",
        }

        actual_abstract = {
            name
            for name, method in inspect.getmembers(GatewayRepository)
            if getattr(method, "__isabstractmethod__", False)
        }

        assert actual_abstract == abstract_methods

    def test_gateway_repository_method_signatures(self):
        """Test that GatewayRepository methods have correct signatures"""
        # Test save method
        save_sig = inspect.signature(GatewayRepository.save)
        assert "gateway" in save_sig.parameters

        # Test get method
        get_sig = inspect.signature(GatewayRepository.get)
        assert "gateway_id" in get_sig.parameters
        assert get_sig.return_annotation == "Gateway | None"

        # Test list_active return type
        list_sig = inspect.signature(GatewayRepository.list_active)
        assert list_sig.return_annotation == "list[Gateway]"

        # Test update_heartbeat parameters
        update_sig = inspect.signature(GatewayRepository.update_heartbeat)
        assert "gateway_id" in update_sig.parameters
        assert "timestamp" in update_sig.parameters

    def test_complete_repository_implementation(self):
        """Test that complete repository implementations work correctly"""

        class InMemoryRepository(GatewayRepository):
            def __init__(self):
                self.gateways = {}

            async def save(self, gateway):
                self.gateways[str(gateway.gateway_id)] = gateway

            async def get(self, gateway_id):
                return self.gateways.get(gateway_id)

            async def list_active(self):
                return [
                    g
                    for g in self.gateways.values()
                    if g.connection_state == ConnectionState.CONNECTED
                ]

            async def update_heartbeat(self, gateway_id, timestamp):
                if gateway_id in self.gateways:
                    self.gateways[gateway_id].last_heartbeat = timestamp

        # Should be able to instantiate
        repo = InMemoryRepository()
        assert isinstance(repo, GatewayRepository)

    @pytest.mark.asyncio
    async def test_mock_gateway_repository(self):
        """Test creating a mock GatewayRepository for testing"""
        mock_repo = Mock(spec=GatewayRepository)
        mock_repo.save = AsyncMock()
        mock_repo.get = AsyncMock()
        mock_repo.list_active = AsyncMock(return_value=[])
        mock_repo.update_heartbeat = AsyncMock()

        # Create test gateway
        gateway = Gateway(
            gateway_id=GatewayId(value="test-01"),
            gateway_type=GatewayType.CTP,
            config=GatewayConfig(
                gateway_id="test-01",
                gateway_type=GatewayType.CTP,
                heartbeat_interval=30,
            ),
        )

        # Test mock usage
        await mock_repo.save(gateway)
        mock_repo.save.assert_called_once_with(gateway)

        mock_repo.get.return_value = gateway
        result = await mock_repo.get("test-01")
        assert result == gateway

        await mock_repo.update_heartbeat("test-01", datetime.now())
        mock_repo.update_heartbeat.assert_called_once()


class TestEventPublisherInterface:
    """Test suite for EventPublisher interface contract"""

    def test_event_publisher_is_abstract(self):
        """Test that EventPublisher is an abstract base class"""
        assert issubclass(EventPublisher, ABC)

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            EventPublisher()

    def test_event_publisher_abstract_methods(self):
        """Test that EventPublisher defines all required abstract methods"""
        abstract_methods = {
            "publish",
            "publish_batch",
        }

        actual_abstract = {
            name
            for name, method in inspect.getmembers(EventPublisher)
            if getattr(method, "__isabstractmethod__", False)
        }

        assert actual_abstract == abstract_methods

    def test_event_publisher_method_signatures(self):
        """Test that EventPublisher methods have correct signatures"""
        # Test publish method
        publish_sig = inspect.signature(EventPublisher.publish)
        assert "event" in publish_sig.parameters

        # Test publish_batch method
        batch_sig = inspect.signature(EventPublisher.publish_batch)
        assert "events" in batch_sig.parameters

    def test_complete_event_publisher_implementation(self):
        """Test that complete EventPublisher implementations work correctly"""

        class InMemoryEventPublisher(EventPublisher):
            def __init__(self):
                self.events = []

            async def publish(self, event):
                self.events.append(event)

            async def publish_batch(self, events):
                self.events.extend(events)

        # Should be able to instantiate
        publisher = InMemoryEventPublisher()
        assert isinstance(publisher, EventPublisher)

    @pytest.mark.asyncio
    async def test_mock_event_publisher(self):
        """Test creating a mock EventPublisher for testing"""
        mock_publisher = Mock(spec=EventPublisher)
        mock_publisher.publish = AsyncMock()
        mock_publisher.publish_batch = AsyncMock()

        # Create test event
        test_event = Mock(spec=DomainEvent)
        test_event.event_type = "test_event"
        test_event.occurred_at = datetime.now()

        # Test mock usage
        await mock_publisher.publish(test_event)
        mock_publisher.publish.assert_called_once_with(test_event)

        events = [test_event, test_event]
        await mock_publisher.publish_batch(events)
        mock_publisher.publish_batch.assert_called_once_with(events)


class TestInterfaceIntegration:
    """Test integration between different port interfaces"""

    @pytest.mark.asyncio
    async def test_gateway_port_and_repository_integration(self):
        """Test that GatewayPort and GatewayRepository work together"""
        # Create mocks
        mock_port = Mock(spec=GatewayPort)
        mock_port.connect = AsyncMock()
        mock_port.is_connected = Mock(return_value=True)

        mock_repo = Mock(spec=GatewayRepository)
        mock_repo.save = AsyncMock()
        mock_repo.get = AsyncMock()

        # Create gateway
        gateway = Gateway(
            gateway_id=GatewayId(value="test-01"),
            gateway_type=GatewayType.CTP,
            config=GatewayConfig(
                gateway_id="test-01",
                gateway_type=GatewayType.CTP,
                heartbeat_interval=30,
            ),
        )

        # Simulate workflow
        await mock_port.connect()
        gateway.mark_connected()
        await mock_repo.save(gateway)

        # Verify calls
        mock_port.connect.assert_called_once()
        mock_repo.save.assert_called_once_with(gateway)

    @pytest.mark.asyncio
    async def test_gateway_and_event_publisher_integration(self):
        """Test that Gateway events can be published via EventPublisher"""
        mock_publisher = Mock(spec=EventPublisher)
        mock_publisher.publish = AsyncMock()
        mock_publisher.publish_batch = AsyncMock()

        # Create gateway and generate events
        gateway = Gateway(
            gateway_id=GatewayId(value="test-01"),
            gateway_type=GatewayType.CTP,
            config=GatewayConfig(
                gateway_id="test-01",
                gateway_type=GatewayType.CTP,
                heartbeat_interval=30,
            ),
        )

        # Generate events
        gateway.connect()
        gateway.acquire_leadership()

        # Get and publish events
        events = gateway.get_events()
        await mock_publisher.publish_batch(events)

        # Verify
        mock_publisher.publish_batch.assert_called_once()
        assert len(events) == 2

    def test_port_interface_documentation(self):
        """Test that port interfaces are properly documented"""
        # Check GatewayPort documentation
        assert GatewayPort.__doc__ is not None
        assert "Port interface" in GatewayPort.__doc__

        # Check method documentation
        assert GatewayPort.connect.__doc__ is not None
        assert "Establish connection" in GatewayPort.connect.__doc__

        assert GatewayPort.subscribe.__doc__ is not None
        assert "Subscribe to market data" in GatewayPort.subscribe.__doc__

        # Check GatewayRepository documentation
        assert GatewayRepository.__doc__ is not None
        assert "Repository interface" in GatewayRepository.__doc__

        # Check EventPublisher documentation
        assert EventPublisher.__doc__ is not None
        assert "publishing domain events" in EventPublisher.__doc__

    def test_interface_inheritance_hierarchy(self):
        """Test that interfaces maintain proper inheritance hierarchy"""
        # All should inherit from ABC
        assert issubclass(GatewayPort, ABC)
        assert issubclass(GatewayRepository, ABC)
        assert issubclass(EventPublisher, ABC)

        # Should not inherit from each other
        assert not issubclass(GatewayPort, GatewayRepository)
        assert not issubclass(GatewayRepository, EventPublisher)
        assert not issubclass(EventPublisher, GatewayPort)

    def test_interface_method_consistency(self):
        """Test that interface methods follow consistent patterns"""
        # All async methods should be properly marked
        for method_name in [
            "connect",
            "disconnect",
            "subscribe",
            "unsubscribe",
            "send_heartbeat",
            "get_connection_status",
        ]:
            method = getattr(GatewayPort, method_name)
            assert inspect.iscoroutinefunction(method)

        # is_connected should be synchronous
        assert not inspect.iscoroutinefunction(GatewayPort.is_connected)

        # Repository methods should all be async
        for method_name in ["save", "get", "list_active", "update_heartbeat"]:
            method = getattr(GatewayRepository, method_name)
            assert inspect.iscoroutinefunction(method)

        # Publisher methods should all be async
        for method_name in ["publish", "publish_batch"]:
            method = getattr(EventPublisher, method_name)
            assert inspect.iscoroutinefunction(method)

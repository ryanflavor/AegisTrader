"""Comprehensive unit tests for Service Registry adapter.

Testing service definition, instance registration, heartbeat mechanism,
and KV store operations following TDD principles.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.infrastructure.service_registry_adapter import (
    ServiceDefinition,
    ServiceInstance,
    ServiceRegistryAdapter,
)
from app.ports.service_registry import RegistrationError


class TestServiceDefinition:
    """Test ServiceDefinition model validation."""

    def test_valid_definition(self):
        """Test creating valid service definition."""
        now = datetime.now(UTC).isoformat()
        definition = ServiceDefinition(
            service_name="echo-service",
            owner="platform-team",
            description="Echo service for testing",
            version="1.0.0",
            created_at=now,
            updated_at=now,
        )
        assert definition.service_name == "echo-service"
        assert definition.owner == "platform-team"
        assert definition.version == "1.0.0"

    def test_invalid_service_name(self):
        """Test validation of service name pattern."""
        now = datetime.now(UTC).isoformat()

        # Invalid patterns
        invalid_names = [
            "Echo-Service",  # Capital letters
            "-echo-service",  # Starts with dash
            "echo-service-",  # Ends with dash
            "e",  # Too short
            "echo_service",  # Underscore not allowed
            "123-service",  # Starts with number
        ]

        for name in invalid_names:
            with pytest.raises(ValueError):
                ServiceDefinition(
                    service_name=name,
                    owner="team",
                    description="test",
                    version="1.0.0",
                    created_at=now,
                    updated_at=now,
                )

    def test_invalid_version(self):
        """Test validation of version pattern."""
        now = datetime.now(UTC).isoformat()

        invalid_versions = [
            "1.0",  # Missing patch version
            "v1.0.0",  # Has prefix
            "1.0.0-beta",  # Has suffix
            "1",  # Only major
        ]

        for version in invalid_versions:
            with pytest.raises(ValueError):
                ServiceDefinition(
                    service_name="test-service",
                    owner="team",
                    description="test",
                    version=version,
                    created_at=now,
                    updated_at=now,
                )


class TestServiceInstance:
    """Test ServiceInstance model validation."""

    def test_valid_instance(self):
        """Test creating valid service instance."""
        now = datetime.now(UTC).isoformat()
        instance = ServiceInstance(
            serviceName="echo-service",
            instanceId="echo-123",
            version="1.0.0",
            status="ACTIVE",
            lastHeartbeat=now,
            stickyActiveGroup="group-1",
            metadata={"region": "us-east"},
        )
        assert instance.service_name == "echo-service"
        assert instance.instance_id == "echo-123"
        assert instance.status == "ACTIVE"

    def test_alias_fields(self):
        """Test field aliases work correctly."""
        now = datetime.now(UTC).isoformat()
        # Test with aliases
        instance = ServiceInstance(
            serviceName="test-service",
            instanceId="test-456",
            version="2.0.0",
            status="STANDBY",
            lastHeartbeat=now,
        )

        # Check internal names
        assert instance.service_name == "test-service"
        assert instance.instance_id == "test-456"
        assert instance.last_heartbeat == now

        # Check serialization uses aliases
        data = instance.model_dump(by_alias=True)
        assert data["serviceName"] == "test-service"
        assert data["instanceId"] == "test-456"
        assert data["lastHeartbeat"] == now

    def test_invalid_status(self):
        """Test validation of status values."""
        now = datetime.now(UTC).isoformat()

        with pytest.raises(ValueError):
            ServiceInstance(
                serviceName="test-service",
                instanceId="test-123",
                version="1.0.0",
                status="RUNNING",  # Invalid status
                lastHeartbeat=now,
            )

    def test_optional_fields(self):
        """Test optional fields have correct defaults."""
        now = datetime.now(UTC).isoformat()
        instance = ServiceInstance(
            serviceName="test-service",
            instanceId="test-789",
            version="1.0.0",
            status="ACTIVE",
            lastHeartbeat=now,
        )
        assert instance.sticky_active_group is None
        assert instance.metadata == {}


@pytest.fixture
def mock_nats_adapter():
    """Create mock NATS adapter."""
    adapter = AsyncMock()
    adapter.get_kv_bucket = AsyncMock()
    adapter.create_kv_bucket = AsyncMock()
    return adapter


@pytest.fixture
def mock_kv_bucket():
    """Create mock KV bucket."""
    bucket = AsyncMock()
    bucket.put = AsyncMock()
    bucket.get = AsyncMock()
    bucket.delete = AsyncMock()
    bucket.keys = AsyncMock(return_value=[])
    return bucket


@pytest.fixture
def registry(mock_nats_adapter):
    """Create service registry adapter."""
    return ServiceRegistryAdapter(mock_nats_adapter)


class TestServiceRegistryAdapter:
    """Test service registry adapter functionality."""

    @pytest.mark.asyncio
    async def test_connect_existing_bucket(self, registry, mock_nats_adapter, mock_kv_bucket):
        """Test connecting to existing KV bucket."""
        mock_nats_adapter.get_kv_bucket.return_value = mock_kv_bucket

        await registry.connect()

        assert registry._kv_bucket == mock_kv_bucket
        mock_nats_adapter.get_kv_bucket.assert_called_once_with("service_registry")
        mock_nats_adapter.create_kv_bucket.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_create_bucket(self, registry, mock_nats_adapter, mock_kv_bucket):
        """Test creating KV bucket when it doesn't exist."""
        mock_nats_adapter.get_kv_bucket.side_effect = Exception("Bucket not found")
        mock_nats_adapter.create_kv_bucket.return_value = mock_kv_bucket

        await registry.connect()

        assert registry._kv_bucket == mock_kv_bucket
        mock_nats_adapter.create_kv_bucket.assert_called_once_with("service_registry")

    @pytest.mark.asyncio
    async def test_connect_error(self, registry, mock_nats_adapter):
        """Test error handling during connect."""
        mock_nats_adapter.get_kv_bucket.side_effect = Exception("Connection failed")
        mock_nats_adapter.create_kv_bucket.side_effect = Exception("Connection failed")

        with pytest.raises(Exception) as exc_info:
            await registry.connect()

        assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_register_service_definition_success(self, registry, mock_kv_bucket):
        """Test successful service definition registration."""
        registry._kv_bucket = mock_kv_bucket

        result = await registry.register_service_definition(
            service_name="test-service",
            owner="test-team",
            description="Test service",
            version="1.2.3",
        )

        assert result is True
        assert registry._service_name == "test-service"

        # Verify KV put was called
        mock_kv_bucket.put.assert_called_once()
        call_args = mock_kv_bucket.put.call_args
        assert call_args[0][0] == "test-service"  # Key

        # Verify data structure
        data = json.loads(call_args[0][1].decode())
        assert data["service_name"] == "test-service"
        assert data["owner"] == "test-team"
        assert data["version"] == "1.2.3"

    @pytest.mark.asyncio
    async def test_register_service_definition_auto_connect(
        self, registry, mock_nats_adapter, mock_kv_bucket
    ):
        """Test auto-connect when bucket not initialized."""
        mock_nats_adapter.get_kv_bucket.return_value = mock_kv_bucket

        result = await registry.register_service_definition(
            service_name="auto-service",
            owner="auto-team",
            description="Auto connect test",
            version="2.0.0",
        )

        assert result is True
        mock_nats_adapter.get_kv_bucket.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_service_definition_error(self, registry, mock_kv_bucket):
        """Test error handling in service definition registration."""
        registry._kv_bucket = mock_kv_bucket
        mock_kv_bucket.put.side_effect = Exception("KV put failed")

        result = await registry.register_service_definition(
            service_name="fail-service",
            owner="fail-team",
            description="Fail test",
            version="1.0.0",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_register_service_instance_success(self, registry, mock_kv_bucket):
        """Test successful service instance registration."""
        registry._kv_bucket = mock_kv_bucket

        result = await registry.register_service_instance(
            service_name="echo-service",
            instance_id="echo-abc123",
            version="1.0.0",
            status="ACTIVE",
            sticky_active_group="group-1",
            metadata={"host": "server1"},
        )

        assert result is True
        assert registry._instance_id == "echo-abc123"
        assert registry._service_name == "echo-service"

        # Verify KV put
        mock_kv_bucket.put.assert_called_once()
        call_args = mock_kv_bucket.put.call_args
        assert call_args[0][0] == "service-instances__echo-service__echo-abc123"

        # Verify data
        data = json.loads(call_args[0][1].decode())
        assert data["instanceId"] == "echo-abc123"
        assert data["status"] == "ACTIVE"
        assert data["stickyActiveGroup"] == "group-1"

    @pytest.mark.asyncio
    async def test_register_service_instance_starts_heartbeat(self, registry, mock_kv_bucket):
        """Test that registering instance starts heartbeat task."""
        registry._kv_bucket = mock_kv_bucket

        with patch.object(registry, "_heartbeat_loop") as mock_heartbeat:
            mock_heartbeat.return_value = asyncio.create_task(asyncio.sleep(0))

            result = await registry.register_service_instance(
                service_name="heartbeat-service",
                instance_id="hb-123",
                version="1.0.0",
            )

            assert result is True
            assert registry._heartbeat_task is not None

    @pytest.mark.asyncio
    async def test_register_service_instance_cancels_old_heartbeat(self, registry, mock_kv_bucket):
        """Test that re-registering cancels old heartbeat."""
        registry._kv_bucket = mock_kv_bucket

        # Create mock old task
        old_task = AsyncMock()
        old_task.cancel = Mock()
        registry._heartbeat_task = old_task

        result = await registry.register_service_instance(
            service_name="new-service",
            instance_id="new-123",
            version="2.0.0",
        )

        assert result is True
        old_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_heartbeat_success(self, registry, mock_kv_bucket):
        """Test successful heartbeat update."""
        registry._kv_bucket = mock_kv_bucket
        registry._instance_id = "test-123"
        registry._service_name = "test-service"

        # Mock existing entry
        mock_entry = Mock()
        mock_entry.value = json.dumps(
            {
                "instanceId": "test-123",
                "serviceName": "test-service",
                "status": "ACTIVE",
                "lastHeartbeat": "2024-01-01T00:00:00",
            }
        ).encode()
        mock_kv_bucket.get.return_value = mock_entry

        result = await registry.update_heartbeat()

        assert result is True

        # Verify get and put were called
        mock_kv_bucket.get.assert_called_once_with("service-instances__test-service__test-123")
        mock_kv_bucket.put.assert_called_once()

        # Verify timestamp was updated
        put_data = json.loads(mock_kv_bucket.put.call_args[0][1].decode())
        assert "lastHeartbeat" in put_data
        assert put_data["lastHeartbeat"] != "2024-01-01T00:00:00"

    @pytest.mark.asyncio
    async def test_update_heartbeat_no_instance(self, registry):
        """Test heartbeat update with no registered instance."""
        result = await registry.update_heartbeat()
        assert result is False

    @pytest.mark.asyncio
    async def test_update_heartbeat_instance_not_found(self, registry, mock_kv_bucket):
        """Test heartbeat update when instance not in KV."""
        registry._kv_bucket = mock_kv_bucket
        registry._instance_id = "missing-123"
        registry._service_name = "test-service"

        mock_kv_bucket.get.return_value = None

        result = await registry.update_heartbeat()

        assert result is False

    @pytest.mark.asyncio
    async def test_update_heartbeat_error(self, registry, mock_kv_bucket):
        """Test error handling in heartbeat update."""
        registry._kv_bucket = mock_kv_bucket
        registry._instance_id = "test-123"
        registry._service_name = "test-service"

        mock_kv_bucket.get.side_effect = Exception("KV error")

        result = await registry.update_heartbeat()

        assert result is False

    @pytest.mark.asyncio
    async def test_heartbeat_loop(self, registry, mock_kv_bucket):
        """Test heartbeat loop functionality."""
        registry._kv_bucket = mock_kv_bucket
        registry._instance_id = "loop-123"
        registry._service_name = "loop-service"

        # Mock successful heartbeat
        mock_entry = Mock()
        mock_entry.value = json.dumps(
            {
                "instanceId": "loop-123",
                "lastHeartbeat": "2024-01-01T00:00:00",
            }
        ).encode()
        mock_kv_bucket.get.return_value = mock_entry

        # Run heartbeat loop for a short time
        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.side_effect = [asyncio.CancelledError()]

            try:
                await registry._heartbeat_loop()
            except asyncio.CancelledError:
                pass

            mock_sleep.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_heartbeat_loop_error_handling(self, registry):
        """Test heartbeat loop handles errors gracefully."""
        registry._instance_id = "error-123"
        registry._service_name = "error-service"

        with patch.object(registry, "update_heartbeat") as mock_update:
            mock_update.side_effect = [Exception("Update failed"), asyncio.CancelledError()]

            with patch("asyncio.sleep") as mock_sleep:
                mock_sleep.side_effect = [None, asyncio.CancelledError()]

                try:
                    await registry._heartbeat_loop()
                except asyncio.CancelledError:
                    pass

    @pytest.mark.asyncio
    async def test_deregister_instance_success(self, registry, mock_kv_bucket):
        """Test successful instance deregistration."""
        registry._kv_bucket = mock_kv_bucket
        registry._instance_id = "dereg-123"
        registry._service_name = "dereg-service"

        # Create mock heartbeat task
        heartbeat_task = AsyncMock()
        heartbeat_task.cancel = Mock()
        registry._heartbeat_task = heartbeat_task

        result = await registry._deregister_instance_internal()

        assert result is True
        heartbeat_task.cancel.assert_called_once()
        assert registry._heartbeat_task is None

        mock_kv_bucket.delete.assert_called_once_with("service-instances__dereg-service__dereg-123")

    @pytest.mark.asyncio
    async def test_deregister_instance_no_instance(self, registry):
        """Test deregistering when no instance registered."""
        result = await registry._deregister_instance_internal()
        assert result is False

    @pytest.mark.asyncio
    async def test_deregister_instance_error(self, registry, mock_kv_bucket):
        """Test error handling in deregistration."""
        registry._kv_bucket = mock_kv_bucket
        registry._instance_id = "fail-123"
        registry._service_name = "fail-service"

        mock_kv_bucket.delete.side_effect = Exception("Delete failed")

        result = await registry._deregister_instance_internal()

        assert result is False

    @pytest.mark.asyncio
    async def test_get_service_definition_found(self, registry, mock_kv_bucket):
        """Test getting existing service definition."""
        registry._kv_bucket = mock_kv_bucket

        mock_entry = Mock()
        mock_entry.value = json.dumps(
            {
                "service_name": "found-service",
                "owner": "team",
                "version": "1.0.0",
            }
        ).encode()
        mock_kv_bucket.get.return_value = mock_entry

        result = await registry.get_service_definition("found-service")

        assert result is not None
        assert result["service_name"] == "found-service"
        mock_kv_bucket.get.assert_called_once_with("found-service")

    @pytest.mark.asyncio
    async def test_get_service_definition_not_found(self, registry, mock_kv_bucket):
        """Test getting non-existent service definition."""
        registry._kv_bucket = mock_kv_bucket
        mock_kv_bucket.get.return_value = None

        result = await registry.get_service_definition("missing-service")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_service_definition_error(self, registry, mock_kv_bucket):
        """Test error handling when getting definition."""
        registry._kv_bucket = mock_kv_bucket
        mock_kv_bucket.get.side_effect = Exception("KV error")

        result = await registry.get_service_definition("error-service")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_service_instances_multiple(self, registry, mock_kv_bucket):
        """Test getting multiple service instances."""
        registry._kv_bucket = mock_kv_bucket

        # Mock keys
        mock_kv_bucket.keys.return_value = [
            "service-instances__test-service__inst1",
            "service-instances__test-service__inst2",
            "service-instances__other-service__inst3",
            "test-service",  # Service definition, not instance
        ]

        # Mock get responses
        def get_side_effect(key):
            if "inst1" in key:
                entry = Mock()
                entry.value = json.dumps({"instanceId": "inst1"}).encode()
                return entry
            elif "inst2" in key:
                entry = Mock()
                entry.value = json.dumps({"instanceId": "inst2"}).encode()
                return entry
            return None

        mock_kv_bucket.get.side_effect = get_side_effect

        result = await registry.get_service_instances("test-service")

        assert len(result) == 2
        assert result[0]["instanceId"] == "inst1"
        assert result[1]["instanceId"] == "inst2"

    @pytest.mark.asyncio
    async def test_get_service_instances_empty(self, registry, mock_kv_bucket):
        """Test getting instances when none exist."""
        registry._kv_bucket = mock_kv_bucket
        mock_kv_bucket.keys.return_value = []

        result = await registry.get_service_instances("empty-service")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_service_instances_error(self, registry, mock_kv_bucket):
        """Test error handling when getting instances."""
        registry._kv_bucket = mock_kv_bucket
        mock_kv_bucket.keys.side_effect = Exception("KV error")

        result = await registry.get_service_instances("error-service")

        assert result == []

    @pytest.mark.asyncio
    async def test_update_service_definition(self, registry):
        """Test updating service definition."""
        from app.domain.models import ServiceRegistrationData

        # Mock register method
        with patch.object(registry, "register_service_definition") as mock_register:
            mock_register.return_value = True

            registration = ServiceRegistrationData(
                definition={
                    "service_name": "update-service",
                    "owner": "update-team",
                    "description": "Updated",
                    "version": "2.0.0",
                },
                instance={
                    "instance_id": "update-123",
                    "status": "ACTIVE",
                },
            )

            await registry.update_service_definition(registration)

            mock_register.assert_called_once_with(
                service_name="update-service",
                owner="update-team",
                description="Updated",
                version="2.0.0",
            )

    @pytest.mark.asyncio
    async def test_update_service_definition_failure(self, registry):
        """Test update service definition failure raises error."""
        from app.domain.models import ServiceRegistrationData

        with patch.object(registry, "register_service_definition") as mock_register:
            mock_register.return_value = False

            registration = ServiceRegistrationData(
                definition={
                    "service_name": "fail-service",
                    "owner": "fail-team",
                    "description": "Fail",
                    "version": "1.0.0",
                },
                instance={
                    "instance_id": "fail-123",
                    "status": "ACTIVE",
                },
            )

            with pytest.raises(RegistrationError) as exc_info:
                await registry.update_service_definition(registration)

            assert "Failed to update service definition" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_service_exists_true(self, registry):
        """Test checking if service exists (true case)."""
        with patch.object(registry, "get_service_definition") as mock_get:
            mock_get.return_value = {"service_name": "exists"}

            result = await registry.check_service_exists("exists")

            assert result is True

    @pytest.mark.asyncio
    async def test_check_service_exists_false(self, registry):
        """Test checking if service exists (false case)."""
        with patch.object(registry, "get_service_definition") as mock_get:
            mock_get.return_value = None

            result = await registry.check_service_exists("missing")

            assert result is False

    @pytest.mark.asyncio
    async def test_register_instance_port_method(self, registry):
        """Test register_instance port interface method."""
        with patch.object(registry, "register_service_instance") as mock_register:
            mock_register.return_value = True

            await registry.register_instance(
                service_name="port-service",
                instance_id="port-123",
                instance_data={
                    "version": "3.0.0",
                    "status": "STANDBY",
                    "metadata": {"zone": "us-west"},
                },
                ttl_seconds=60,
            )

            mock_register.assert_called_once_with(
                service_name="port-service",
                instance_id="port-123",
                version="3.0.0",
                status="STANDBY",
                metadata={"zone": "us-west"},
            )

    @pytest.mark.asyncio
    async def test_register_instance_port_method_failure(self, registry):
        """Test register_instance failure raises error."""
        with patch.object(registry, "register_service_instance") as mock_register:
            mock_register.return_value = False

            with pytest.raises(RegistrationError) as exc_info:
                await registry.register_instance(
                    service_name="fail-service",
                    instance_id="fail-123",
                    instance_data={},
                    ttl_seconds=60,
                )

            assert "Failed to register instance" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_instance_heartbeat_port_method(self, registry):
        """Test update_instance_heartbeat port interface method."""
        with patch.object(registry, "update_heartbeat") as mock_update:
            mock_update.return_value = True

            await registry.update_instance_heartbeat(
                service_name="hb-service",
                instance_id="hb-123",
                instance_data={"status": "ACTIVE"},
                ttl_seconds=30,
            )

            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_instance_heartbeat_failure(self, registry):
        """Test heartbeat update failure raises error."""
        with patch.object(registry, "update_heartbeat") as mock_update:
            mock_update.return_value = False

            with pytest.raises(RegistrationError) as exc_info:
                await registry.update_instance_heartbeat(
                    service_name="fail-service",
                    instance_id="fail-123",
                    instance_data={},
                    ttl_seconds=30,
                )

            assert "Failed to update heartbeat" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_deregister_instance_port_method(self, registry):
        """Test deregister_instance port interface method with parameters."""
        registry._service_name = "existing-service"
        registry._instance_id = "existing-123"

        with patch.object(registry, "_deregister_instance_internal") as mock_dereg:
            mock_dereg.return_value = True

            # Test with provided parameters
            await registry.deregister_instance("new-service", "new-123")

            # Should call internal method with new values
            mock_dereg.assert_called_once()

    @pytest.mark.asyncio
    async def test_deregister_instance_no_params(self, registry):
        """Test deregister_instance without parameters."""
        # No instance registered
        await registry.deregister_instance()
        # Should return without error

    @pytest.mark.asyncio
    async def test_deregister_instance_port_failure(self, registry):
        """Test deregister failure raises error."""
        registry._service_name = "fail-service"
        registry._instance_id = "fail-123"

        with patch.object(registry, "_deregister_instance_internal") as mock_dereg:
            mock_dereg.return_value = False

            with pytest.raises(RegistrationError) as exc_info:
                await registry.deregister_instance()

            assert "Failed to deregister instance" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect(self, registry):
        """Test disconnect cleans up resources."""
        # Setup state
        heartbeat_task = AsyncMock()
        heartbeat_task.cancel = Mock()
        registry._heartbeat_task = heartbeat_task
        registry._instance_id = "disc-123"
        registry._kv_bucket = Mock()

        with patch.object(registry, "deregister_instance") as mock_dereg:
            await registry.disconnect()

            heartbeat_task.cancel.assert_called_once()
            assert registry._heartbeat_task is None
            mock_dereg.assert_called_once()
            assert registry._kv_bucket is None

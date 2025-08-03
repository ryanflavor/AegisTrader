"""Comprehensive tests for InMemoryServiceRepository following TDD principles."""

import pytest

from aegis_sdk.domain.aggregates import ServiceAggregate, ServiceStatus
from aegis_sdk.domain.value_objects import InstanceId, ServiceName
from aegis_sdk.infrastructure.in_memory_repository import InMemoryServiceRepository
from aegis_sdk.ports.repository import ServiceRepository


class TestInMemoryServiceRepository:
    """Test cases for InMemoryServiceRepository implementation."""

    @pytest.fixture
    def repository(self):
        """Create a fresh repository for each test."""
        return InMemoryServiceRepository()

    @pytest.fixture
    def sample_aggregate(self):
        """Create a sample service aggregate."""
        return ServiceAggregate(
            service_name=ServiceName(value="test-service"),
            instance_id=InstanceId(value="test-instance-123"),
            version="1.0.0",
            status=ServiceStatus.ACTIVE,
        )

    def test_implements_repository_port(self, repository):
        """Test that InMemoryServiceRepository implements ServiceRepository."""
        assert isinstance(repository, ServiceRepository)

    @pytest.mark.asyncio
    async def test_save_and_get_aggregate(self, repository, sample_aggregate):
        """Test saving and retrieving an aggregate."""
        # Save aggregate
        await repository.save(sample_aggregate)

        # Retrieve aggregate
        retrieved = await repository.get(
            sample_aggregate.service_name, sample_aggregate.instance_id
        )

        assert retrieved is not None
        assert retrieved.service_name == sample_aggregate.service_name
        assert retrieved.instance_id == sample_aggregate.instance_id
        assert retrieved.version == sample_aggregate.version
        assert retrieved.status == sample_aggregate.status

    @pytest.mark.asyncio
    async def test_get_nonexistent_aggregate(self, repository):
        """Test getting an aggregate that doesn't exist."""
        result = await repository.get(
            ServiceName(value="nonexistent"), InstanceId(value="nonexistent-123")
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_update_existing_aggregate(self, repository, sample_aggregate):
        """Test updating an existing aggregate."""
        # Save initial aggregate
        await repository.save(sample_aggregate)

        # Create updated aggregate with same identity
        updated_aggregate = ServiceAggregate(
            service_name=sample_aggregate.service_name,
            instance_id=sample_aggregate.instance_id,
            version="2.0.0",
            status=ServiceStatus.STANDBY,
        )

        # Save updated aggregate
        await repository.save(updated_aggregate)

        # Retrieve and verify
        retrieved = await repository.get(
            sample_aggregate.service_name, sample_aggregate.instance_id
        )

        assert retrieved is not None
        assert retrieved.status == ServiceStatus.STANDBY
        assert retrieved.version == "2.0.0"

    @pytest.mark.asyncio
    async def test_list_by_service_empty(self, repository):
        """Test listing instances when none exist - covers lines 34-35."""
        result = await repository.list_by_service(ServiceName(value="empty-service"))

        assert result == []
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_list_by_service_single_instance(self, repository):
        """Test listing instances with one instance."""
        service_name = ServiceName(value="single-service")
        aggregate = ServiceAggregate(
            service_name=service_name,
            instance_id=InstanceId(value="instance-1"),
            version="1.0.0",
        )

        await repository.save(aggregate)

        result = await repository.list_by_service(service_name)

        assert len(result) == 1
        assert result[0].instance_id == aggregate.instance_id

    @pytest.mark.asyncio
    async def test_list_by_service_multiple_instances(self, repository):
        """Test listing instances with multiple instances - fully covers lines 34-35."""
        service_name = ServiceName(value="multi-service")

        # Create multiple instances
        instances = []
        for i in range(3):
            aggregate = ServiceAggregate(
                service_name=service_name,
                instance_id=InstanceId(value=f"instance-{i}"),
                version="1.0.0",
            )
            await repository.save(aggregate)
            instances.append(aggregate)

        # Add instances for a different service
        other_service = ServiceAggregate(
            service_name=ServiceName(value="other-service"),
            instance_id=InstanceId(value="other-instance"),
            version="1.0.0",
        )
        await repository.save(other_service)

        # List instances for the target service
        result = await repository.list_by_service(service_name)

        assert len(result) == 3
        instance_ids = {agg.instance_id.value for agg in result}
        assert instance_ids == {"instance-0", "instance-1", "instance-2"}

    @pytest.mark.asyncio
    async def test_delete_existing_aggregate(self, repository, sample_aggregate):
        """Test deleting an existing aggregate - covers lines 43-44."""
        # Save aggregate
        await repository.save(sample_aggregate)

        # Verify it exists
        exists = await repository.get(sample_aggregate.service_name, sample_aggregate.instance_id)
        assert exists is not None

        # Delete aggregate
        await repository.delete(sample_aggregate.service_name, sample_aggregate.instance_id)

        # Verify it's gone
        result = await repository.get(sample_aggregate.service_name, sample_aggregate.instance_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_aggregate(self, repository):
        """Test deleting an aggregate that doesn't exist - covers line 44."""
        # Delete non-existent aggregate (should not raise)
        await repository.delete(
            ServiceName(value="nonexistent"), InstanceId(value="nonexistent-123")
        )

        # Verify repository is still functional
        aggregate = ServiceAggregate(
            service_name=ServiceName(value="test"),
            instance_id=InstanceId(value="test-123"),
        )
        await repository.save(aggregate)
        result = await repository.get(aggregate.service_name, aggregate.instance_id)
        assert result is not None

    def test_clear_empty_repository(self, repository):
        """Test clearing an empty repository - covers line 48."""
        # Clear empty repository (should not raise)
        repository.clear()

        # Verify it's still empty
        assert repository.get_all() == []

    @pytest.mark.asyncio
    async def test_clear_populated_repository(self, repository):
        """Test clearing a populated repository - fully covers line 48."""
        # Add multiple aggregates
        for i in range(5):
            aggregate = ServiceAggregate(
                service_name=ServiceName(value=f"service-{i}"),
                instance_id=InstanceId(value=f"instance-{i}"),
            )
            await repository.save(aggregate)

        # Verify they exist
        assert len(repository.get_all()) == 5

        # Clear repository
        repository.clear()

        # Verify all are gone
        assert repository.get_all() == []
        assert len(repository._storage) == 0

    def test_get_all_empty(self, repository):
        """Test get_all on empty repository."""
        result = repository.get_all()

        assert result == []
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_all_populated(self, repository):
        """Test get_all with multiple aggregates."""
        # Add aggregates
        aggregates = []
        for i in range(3):
            aggregate = ServiceAggregate(
                service_name=ServiceName(value=f"service-{i}"),
                instance_id=InstanceId(value=f"instance-{i}"),
            )
            await repository.save(aggregate)
            aggregates.append(aggregate)

        # Get all
        result = repository.get_all()

        assert len(result) == 3
        # Verify all aggregates are present
        result_ids = {(agg.service_name.value, agg.instance_id.value) for agg in result}
        expected_ids = {(f"service-{i}", f"instance-{i}") for i in range(3)}
        assert result_ids == expected_ids

    @pytest.mark.asyncio
    async def test_storage_key_format(self, repository):
        """Test that storage uses correct key format."""
        service_name = ServiceName(value="key-test-service")
        instance_id = InstanceId(value="key-test-instance")

        aggregate = ServiceAggregate(
            service_name=service_name,
            instance_id=instance_id,
        )

        await repository.save(aggregate)

        # Check internal storage key format
        expected_key = ("key-test-service", "key-test-instance")
        assert expected_key in repository._storage
        assert repository._storage[expected_key] == aggregate

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, repository):
        """Test repository handles concurrent-like operations correctly."""
        service_name = ServiceName(value="concurrent-service")

        # Simulate multiple instances being registered
        instances = []
        for i in range(10):
            aggregate = ServiceAggregate(
                service_name=service_name,
                instance_id=InstanceId(value=f"instance-{i}"),
                version=f"1.0.{i}",
            )
            await repository.save(aggregate)
            instances.append(aggregate)

        # Verify all were saved
        result = await repository.list_by_service(service_name)
        assert len(result) == 10

        # Delete some instances
        for i in [2, 5, 7]:
            await repository.delete(service_name, InstanceId(value=f"instance-{i}"))

        # Verify correct instances remain
        result = await repository.list_by_service(service_name)
        assert len(result) == 7
        remaining_ids = {agg.instance_id.value for agg in result}
        expected_remaining = {f"instance-{i}" for i in [0, 1, 3, 4, 6, 8, 9]}
        assert remaining_ids == expected_remaining

    @pytest.mark.asyncio
    async def test_aggregate_independence(self, repository):
        """Test that stored aggregates are independent."""
        # Create and save aggregate
        original = ServiceAggregate(
            service_name=ServiceName(value="independent"),
            instance_id=InstanceId(value="instance-1"),
            status=ServiceStatus.ACTIVE,
        )
        await repository.save(original)

        # Retrieve aggregate
        retrieved = await repository.get(original.service_name, original.instance_id)

        # Verify we get the same object reference
        assert retrieved is repository._storage[("independent", "instance-1")]

        # Create a new aggregate with same ID but different status
        modified = ServiceAggregate(
            service_name=ServiceName(value="independent"),
            instance_id=InstanceId(value="instance-1"),
            status=ServiceStatus.UNHEALTHY,
        )
        await repository.save(modified)

        # Retrieve again
        retrieved2 = await repository.get(original.service_name, original.instance_id)

        # Should have the new status
        assert retrieved2.status == ServiceStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_edge_cases(self, repository):
        """Test edge cases and boundary conditions."""
        # Service name with special characters
        service_name = ServiceName(value="test-service_123")
        instance_id = InstanceId(value="inst-ABC-123_456-xyz")

        aggregate = ServiceAggregate(
            service_name=service_name,
            instance_id=instance_id,
            metadata={"key": "value", "number": 123, "nested": {"data": True}},
        )

        await repository.save(aggregate)
        retrieved = await repository.get(service_name, instance_id)

        assert retrieved is not None
        assert retrieved.metadata == aggregate.metadata

        # Very long version string
        aggregate._version = "1.0.0-alpha.1+build.123.sha.abcdef1234567890"
        await repository.save(aggregate)

        retrieved = await repository.get(service_name, instance_id)
        assert retrieved.version == aggregate.version

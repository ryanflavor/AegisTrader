"""Integration tests for NATS KV Store-based election repository."""

from __future__ import annotations

import asyncio

import pytest

from aegis_sdk.domain.aggregates import StickyActiveElection, StickyActiveElectionState
from aegis_sdk.domain.value_objects import InstanceId, ServiceName
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_election_repository import NatsKvElectionRepository
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


@pytest.mark.integration
@pytest.mark.asyncio
class TestNatsKvElectionRepository:
    """Integration tests for NATS KV election repository."""

    async def test_attempt_leadership_success(self, nats_adapter: NATSAdapter):
        """Test successful leadership acquisition."""
        # Setup
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("test_election", enable_ttl=True)

        repo = NatsKvElectionRepository(kv_store)

        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-1")

        # Attempt leadership
        acquired = await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance_id,
            group_id="default",
            ttl_seconds=5,
            metadata={"zone": "us-east-1"},
        )

        assert acquired is True

        # Verify leader
        leader_id, metadata = await repo.get_current_leader(service_name, "default")
        assert leader_id == instance_id
        assert metadata["zone"] == "us-east-1"

        # Cleanup
        await kv_store.disconnect()

    async def test_attempt_leadership_conflict(self, nats_adapter: NATSAdapter):
        """Test leadership acquisition when another leader exists."""
        # Setup
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("test_election", enable_ttl=True)

        repo = NatsKvElectionRepository(kv_store)

        service_name = ServiceName(value="test-service")
        instance1 = InstanceId(value="instance-1")
        instance2 = InstanceId(value="instance-2")

        # First instance acquires leadership
        acquired1 = await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance1,
            group_id="default",
            ttl_seconds=5,
        )
        assert acquired1 is True

        # Second instance attempts and fails
        acquired2 = await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance2,
            group_id="default",
            ttl_seconds=5,
        )
        assert acquired2 is False

        # Verify leader is still instance1
        leader_id, _ = await repo.get_current_leader(service_name, "default")
        assert leader_id == instance1

        # Cleanup
        await kv_store.disconnect()

    async def test_update_leadership_heartbeat(self, nats_adapter: NATSAdapter):
        """Test updating leadership heartbeat."""
        # Setup
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("test_election", enable_ttl=True)

        repo = NatsKvElectionRepository(kv_store)

        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-1")

        # Acquire leadership
        await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance_id,
            group_id="default",
            ttl_seconds=2,  # Short TTL for testing
        )

        # Wait briefly
        await asyncio.sleep(0.5)

        # Update heartbeat
        updated = await repo.update_leadership(
            service_name=service_name,
            instance_id=instance_id,
            group_id="default",
            ttl_seconds=2,
            metadata={"updated": True},
        )
        assert updated is True

        # Verify metadata was updated
        leader_id, metadata = await repo.get_current_leader(service_name, "default")
        assert leader_id == instance_id
        assert metadata.get("updated") is True

        # Cleanup
        await kv_store.disconnect()

    async def test_update_leadership_not_leader(self, nats_adapter: NATSAdapter):
        """Test updating leadership when not the leader."""
        # Setup
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("test_election", enable_ttl=True)

        repo = NatsKvElectionRepository(kv_store)

        service_name = ServiceName(value="test-service")
        instance1 = InstanceId(value="instance-1")
        instance2 = InstanceId(value="instance-2")

        # Instance1 acquires leadership
        await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance1,
            group_id="default",
            ttl_seconds=5,
        )

        # Instance2 tries to update (should fail)
        updated = await repo.update_leadership(
            service_name=service_name,
            instance_id=instance2,
            group_id="default",
            ttl_seconds=5,
        )
        assert updated is False

        # Cleanup
        await kv_store.disconnect()

    async def test_release_leadership(self, nats_adapter: NATSAdapter):
        """Test voluntary leadership release."""
        # Setup
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("test_election", enable_ttl=True)

        repo = NatsKvElectionRepository(kv_store)

        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-1")

        # Acquire leadership
        await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance_id,
            group_id="default",
            ttl_seconds=5,
        )

        # Release leadership
        released = await repo.release_leadership(
            service_name=service_name,
            instance_id=instance_id,
            group_id="default",
        )
        assert released is True

        # Verify no leader exists
        leader_id, _ = await repo.get_current_leader(service_name, "default")
        assert leader_id is None

        # Cleanup
        await kv_store.disconnect()

    async def test_leader_expiration_detection(self, nats_adapter: NATSAdapter):
        """Test detection of expired leader."""
        # Setup
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("test_election", enable_ttl=True)

        repo = NatsKvElectionRepository(kv_store)

        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-1")

        # Override election service to have very short TTL for testing
        repo._election_service.leader_ttl = 1  # 1 second TTL

        # Acquire leadership
        await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance_id,
            group_id="default",
            ttl_seconds=1,
        )

        # Verify leader exists
        leader_id, _ = await repo.get_current_leader(service_name, "default")
        assert leader_id == instance_id

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Check leader - should be expired
        leader_id, _ = await repo.get_current_leader(service_name, "default")
        assert leader_id is None

        # Cleanup
        await kv_store.disconnect()

    async def test_watch_leadership_changes(self, nats_adapter: NATSAdapter):
        """Test watching for leadership changes."""
        # Setup
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("test_election", enable_ttl=True)

        repo = NatsKvElectionRepository(kv_store)

        service_name = ServiceName(value="test-service")
        instance1 = InstanceId(value="instance-1")
        instance2 = InstanceId(value="instance-2")

        # Collect events
        events = []

        async def watch_events():
            """Watch for leadership events."""
            async for event in repo.watch_leadership(service_name, "default"):
                events.append(event)
                if len(events) >= 3:  # Expect 3 events
                    break

        # Start watching in background
        watch_task = asyncio.create_task(watch_events())
        await asyncio.sleep(0.1)  # Let watcher start

        # Instance1 acquires leadership
        await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance1,
            group_id="default",
            ttl_seconds=5,
        )
        await asyncio.sleep(0.1)

        # Instance1 releases leadership
        await repo.release_leadership(
            service_name=service_name,
            instance_id=instance1,
            group_id="default",
        )
        await asyncio.sleep(0.1)

        # Instance2 acquires leadership
        await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance2,
            group_id="default",
            ttl_seconds=5,
        )

        # Wait for events
        try:
            await asyncio.wait_for(watch_task, timeout=2.0)
        except asyncio.TimeoutError:
            watch_task.cancel()

        # Verify events
        assert len(events) >= 3
        assert events[0]["type"] == "elected"
        assert events[0]["leader_id"] == str(instance1)
        assert events[1]["type"] in ["lost", "expired"]
        assert events[2]["type"] == "elected"
        assert events[2]["leader_id"] == str(instance2)

        # Cleanup
        await kv_store.disconnect()

    async def test_save_and_restore_election_state(self, nats_adapter: NATSAdapter):
        """Test saving and restoring election aggregate state."""
        # Setup
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("test_election", enable_ttl=True)

        repo = NatsKvElectionRepository(kv_store)

        service_name = ServiceName(value="test-service")
        instance_id = InstanceId(value="instance-1")

        # Create election aggregate
        election = StickyActiveElection(
            service_name=service_name,
            instance_id=instance_id,
            group_id="production",
            leader_ttl_seconds=10,
            heartbeat_interval_seconds=3,
        )

        # Start election and win
        election.start_election()
        election.win_election()

        # Save state
        await repo.save_election_state(election)

        # Restore state
        restored = await repo.get_election_state(service_name, instance_id, "production")

        assert restored is not None
        assert restored.service_name == service_name
        assert restored.instance_id == instance_id
        assert restored.group_id == "production"
        assert restored.status == StickyActiveElectionState.ACTIVE
        assert restored.is_leader
        assert restored.leader_ttl_seconds == 10
        assert restored.heartbeat_interval_seconds == 3

        # Delete state
        await repo.delete_election_state(service_name, instance_id, "production")

        # Verify deleted
        restored = await repo.get_election_state(service_name, instance_id, "production")
        assert restored is None

        # Cleanup
        await kv_store.disconnect()

    async def test_concurrent_election_attempts(self, nats_adapter: NATSAdapter):
        """Test multiple instances attempting election concurrently."""
        # Setup
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("test_election", enable_ttl=True)

        repo = NatsKvElectionRepository(kv_store)

        service_name = ServiceName(value="test-service")
        instances = [InstanceId(value=f"instance-{i}") for i in range(5)]

        # All instances attempt leadership concurrently
        tasks = []
        for instance in instances:
            task = repo.attempt_leadership(
                service_name=service_name,
                instance_id=instance,
                group_id="default",
                ttl_seconds=5,
            )
            tasks.append(task)

        # Wait for all attempts
        results = await asyncio.gather(*tasks)

        # Only one should succeed
        successful_count = sum(1 for result in results if result)
        assert successful_count == 1

        # Verify single leader
        leader_id, _ = await repo.get_current_leader(service_name, "default")
        assert leader_id is not None
        assert leader_id in instances

        # Cleanup
        await kv_store.disconnect()

    async def test_multiple_service_groups(self, nats_adapter: NATSAdapter):
        """Test elections in different service groups."""
        # Setup
        kv_store = NATSKVStore(nats_adapter)
        await kv_store.connect("test_election", enable_ttl=True)

        repo = NatsKvElectionRepository(kv_store)

        service_name = ServiceName(value="test-service")
        instance1 = InstanceId(value="instance-1")
        instance2 = InstanceId(value="instance-2")

        # Instance1 leads group1
        acquired1 = await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance1,
            group_id="group1",
            ttl_seconds=5,
        )
        assert acquired1 is True

        # Instance2 leads group2
        acquired2 = await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance2,
            group_id="group2",
            ttl_seconds=5,
        )
        assert acquired2 is True

        # Verify separate leaders
        leader1, _ = await repo.get_current_leader(service_name, "group1")
        leader2, _ = await repo.get_current_leader(service_name, "group2")

        assert leader1 == instance1
        assert leader2 == instance2

        # Instance2 cannot take over group1
        acquired3 = await repo.attempt_leadership(
            service_name=service_name,
            instance_id=instance2,
            group_id="group1",
            ttl_seconds=5,
        )
        assert acquired3 is False

        # Cleanup
        await kv_store.disconnect()

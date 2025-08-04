"""Integration tests for event subscription load balancing modes."""

import asyncio
import contextlib
import uuid

import pytest

from aegis_sdk.application.service import Service
from aegis_sdk.domain.models import Event
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter


@pytest.mark.integration
class TestEventSubscriptionLoadBalancing:
    """Test event subscription load balancing in real environment."""

    @pytest.mark.asyncio
    async def test_compete_mode_load_balancing(self, nats_container):
        """Test that compete mode distributes events across instances."""
        # Create two instances of the same service
        adapter1 = NATSAdapter()
        await adapter1.connect([nats_container])

        # Create a stream for the test subjects
        js = adapter1._js
        with contextlib.suppress(Exception):
            # Stream might already exist
            await js.add_stream(name="MARKET", subjects=["events.market.*"])

        service1 = Service("pricing-service", adapter1, instance_id="pricing-service-1")

        adapter2 = NATSAdapter()
        await adapter2.connect([nats_container])
        service2 = Service("pricing-service", adapter2, instance_id="pricing-service-2")

        # Track which instance received each event
        events_received = {"instance1": [], "instance2": []}

        @service1.subscribe("events.market.data", mode="compete")
        async def handle_market_data_1(event: Event):
            events_received["instance1"].append(event.message_id)

        @service2.subscribe("events.market.data", mode="compete")
        async def handle_market_data_2(event: Event):
            events_received["instance2"].append(event.message_id)

        # Start both services
        await service1.start()
        await service2.start()

        # Give services time to register
        await asyncio.sleep(0.2)

        # Publish multiple events
        num_events = 10
        event_ids = []
        for i in range(num_events):
            event_id = str(uuid.uuid4())
            event_ids.append(event_id)

            event = Event(
                message_id=event_id,
                domain="market",
                event_type="data",
                payload={"index": i, "price": 100 + i},
                source="test-publisher",
            )
            await adapter1.publish_event(event)
            # Small delay to ensure ordering
            await asyncio.sleep(0.05)

        # Wait for events to be processed
        await asyncio.sleep(0.5)

        # Verify load balancing
        total_received = len(events_received["instance1"]) + len(events_received["instance2"])
        assert total_received == num_events, f"Expected {num_events} events, got {total_received}"

        # Check that both instances received some events (load balanced)
        assert len(events_received["instance1"]) > 0, "Instance 1 received no events"
        assert len(events_received["instance2"]) > 0, "Instance 2 received no events"

        # Verify no duplicate processing
        all_received = events_received["instance1"] + events_received["instance2"]
        assert len(all_received) == len(set(all_received)), "Duplicate event processing detected"

        # Clean up
        await service1.stop()
        await service2.stop()
        await adapter1.disconnect()
        await adapter2.disconnect()

    @pytest.mark.asyncio
    async def test_broadcast_mode_all_instances_receive(self, nats_container):
        """Test that broadcast mode delivers to all instances."""
        # Create two instances of a monitoring service
        adapter1 = NATSAdapter()
        await adapter1.connect([nats_container])

        # Create a stream for system alerts
        js = adapter1._js
        with contextlib.suppress(Exception):
            await js.add_stream(name="SYSTEM", subjects=["events.system.*"])

        service1 = Service("monitor-service", adapter1, instance_id="monitor-service-1")

        adapter2 = NATSAdapter()
        await adapter2.connect([nats_container])
        service2 = Service("monitor-service", adapter2, instance_id="monitor-service-2")

        # Track which events each instance received
        events_received = {"instance1": [], "instance2": []}

        @service1.subscribe("events.system.alert", mode="broadcast")
        async def handle_alert_1(event: Event):
            events_received["instance1"].append(event.message_id)

        @service2.subscribe("events.system.alert", mode="broadcast")
        async def handle_alert_2(event: Event):
            events_received["instance2"].append(event.message_id)

        # Start both services
        await service1.start()
        await service2.start()

        # Give services time to register
        await asyncio.sleep(0.2)

        # Publish multiple events
        num_events = 5
        event_ids = []
        for i in range(num_events):
            event_id = str(uuid.uuid4())
            event_ids.append(event_id)

            event = Event(
                message_id=event_id,
                domain="system",
                event_type="alert",
                payload={"level": "warning", "message": f"Alert {i}"},
                source="test-publisher",
            )
            await adapter1.publish_event(event)
            # Small delay to ensure ordering
            await asyncio.sleep(0.05)

        # Wait for events to be processed
        await asyncio.sleep(0.5)

        # Verify broadcast - both instances should receive all events
        assert (
            len(events_received["instance1"]) == num_events
        ), f"Instance 1 expected {num_events} events, got {len(events_received['instance1'])}"
        assert (
            len(events_received["instance2"]) == num_events
        ), f"Instance 2 expected {num_events} events, got {len(events_received['instance2'])}"

        # Verify both instances received the same events
        assert set(events_received["instance1"]) == set(event_ids), "Instance 1 missing events"
        assert set(events_received["instance2"]) == set(event_ids), "Instance 2 missing events"

        # Clean up
        await service1.stop()
        await service2.stop()
        await adapter1.disconnect()
        await adapter2.disconnect()

    @pytest.mark.asyncio
    async def test_mixed_mode_subscriptions(self, nats_container):
        """Test service with both compete and broadcast subscriptions."""
        # Create a service that uses both modes
        adapter = NATSAdapter()
        await adapter.connect([nats_container])

        # Create streams for both types of events
        js = adapter._js
        with contextlib.suppress(Exception):
            await js.add_stream(name="TRADE", subjects=["events.trade.*"])
            await js.add_stream(name="CONFIG", subjects=["events.config.*"])

        service = Service("hybrid-service", adapter)

        events_received = {"compete": [], "broadcast": []}

        @service.subscribe("events.trade.executed", mode="compete")
        async def handle_trade(event: Event):
            events_received["compete"].append(event.message_id)

        @service.subscribe("events.config.changed", mode="broadcast")
        async def handle_config(event: Event):
            events_received["broadcast"].append(event.message_id)

        await service.start()
        await asyncio.sleep(0.2)

        # Publish events
        trade_event = Event(
            domain="trade",
            event_type="executed",
            payload={"symbol": "AAPL", "quantity": 100},
            source="test",
        )
        await adapter.publish_event(trade_event)

        config_event = Event(
            domain="config",
            event_type="changed",
            payload={"setting": "max_risk", "value": 0.02},
            source="test",
        )
        await adapter.publish_event(config_event)

        await asyncio.sleep(0.3)

        # Verify both handlers received their events
        assert len(events_received["compete"]) == 1
        assert len(events_received["broadcast"]) == 1

        # Clean up
        await service.stop()
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_wildcard_pattern_modes(self, nats_container):
        """Test compete/broadcast modes with wildcard patterns."""
        # Create two instances
        adapter1 = NATSAdapter()
        await adapter1.connect([nats_container])
        service1 = Service("analytics-service", adapter1, instance_id="analytics-1")

        adapter2 = NATSAdapter()
        await adapter2.connect([nats_container])
        service2 = Service("analytics-service", adapter2, instance_id="analytics-2")

        compete_events = {"instance1": [], "instance2": []}
        broadcast_events = {"instance1": [], "instance2": []}

        # Compete mode for user events
        @service1.subscribe("events.user.*", mode="compete")
        async def handle_user_1(event: Event):
            compete_events["instance1"].append(event.event_type)

        @service2.subscribe("events.user.*", mode="compete")
        async def handle_user_2(event: Event):
            compete_events["instance2"].append(event.event_type)

        # Broadcast mode for system events
        @service1.subscribe("events.system.*", mode="broadcast")
        async def handle_system_1(event: Event):
            broadcast_events["instance1"].append(event.event_type)

        @service2.subscribe("events.system.*", mode="broadcast")
        async def handle_system_2(event: Event):
            broadcast_events["instance2"].append(event.event_type)

        await service1.start()
        await service2.start()
        await asyncio.sleep(0.2)

        # Publish various events
        user_events = ["login", "logout", "update", "delete"]
        for event_type in user_events:
            event = Event(domain="user", event_type=event_type, payload={}, source="test")
            await adapter1.publish_event(event)
            await asyncio.sleep(0.05)

        system_events = ["startup", "shutdown", "error"]
        for event_type in system_events:
            event = Event(domain="system", event_type=event_type, payload={}, source="test")
            await adapter1.publish_event(event)
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.5)

        # Verify compete mode distributed user events
        total_compete = len(compete_events["instance1"]) + len(compete_events["instance2"])
        assert total_compete == len(user_events)
        assert len(compete_events["instance1"]) > 0
        assert len(compete_events["instance2"]) > 0

        # Verify broadcast mode sent system events to both
        assert sorted(broadcast_events["instance1"]) == sorted(system_events)
        assert sorted(broadcast_events["instance2"]) == sorted(system_events)

        # Clean up
        await service1.stop()
        await service2.stop()
        await adapter1.disconnect()
        await adapter2.disconnect()

    @pytest.mark.asyncio
    async def test_instance_failure_compete_mode(self, nats_container):
        """Test that compete mode continues working when an instance fails."""
        # Create two instances
        adapter1 = NATSAdapter()
        await adapter1.connect([nats_container])

        # Create stream for important tasks
        js = adapter1._js
        with contextlib.suppress(Exception):
            await js.add_stream(name="IMPORTANT", subjects=["events.important.*"])

        service1 = Service("resilient-service", adapter1, instance_id="resilient-1")

        adapter2 = NATSAdapter()
        await adapter2.connect([nats_container])
        service2 = Service("resilient-service", adapter2, instance_id="resilient-2")

        events_received = []

        @service1.subscribe("events.important.task", mode="compete")
        async def handle_task_1(event: Event):
            events_received.append(("instance1", event.payload.get("id")))

        @service2.subscribe("events.important.task", mode="compete")
        async def handle_task_2(event: Event):
            events_received.append(("instance2", event.payload.get("id")))

        # Start both services
        await service1.start()
        await service2.start()
        await asyncio.sleep(0.2)

        # Publish some events
        for i in range(3):
            event = Event(domain="important", event_type="task", payload={"id": i}, source="test")
            await adapter1.publish_event(event)
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.3)

        # Stop one instance
        await service1.stop()
        await asyncio.sleep(0.2)

        # Publish more events - should all go to remaining instance
        for i in range(3, 6):
            event = Event(domain="important", event_type="task", payload={"id": i}, source="test")
            await adapter2.publish_event(event)
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.3)

        # Verify all events were processed
        processed_ids = [e[1] for e in events_received]
        assert sorted(processed_ids) == list(range(6))

        # Verify instance2 handled events after instance1 stopped
        instance2_events = [e for e in events_received if e[0] == "instance2"]
        instance2_ids = [e[1] for e in instance2_events]
        assert all(id in instance2_ids for id in [3, 4, 5])

        # Clean up
        await service2.stop()
        await adapter1.disconnect()
        await adapter2.disconnect()

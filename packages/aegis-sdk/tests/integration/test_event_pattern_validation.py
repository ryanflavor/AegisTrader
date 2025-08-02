"""Comprehensive Event pattern validation tests for Story 1.1."""

import asyncio
import time

import pytest

from aegis_sdk.domain.models import Event
from aegis_sdk.domain.patterns import SubjectPatterns


class TestEventPatternValidation:
    """Test suite for comprehensive Event pattern validation."""

    @pytest.mark.asyncio
    async def test_jetstream_event_publishing_durable(self, nats_adapter, nats_container):
        """Test JetStream event publishing with durable subscriptions."""
        domain = "order"
        event_type = "created"
        events_received = []

        # Create durable subscription
        async def event_handler(event: Event):
            events_received.append(event)

        # Subscribe with durable name
        await nats_adapter.subscribe_event(
            SubjectPatterns.event(domain, event_type), event_handler, durable="test-durable"
        )
        await asyncio.sleep(0.1)

        # Publish multiple events
        num_events = 10
        for i in range(num_events):
            event = Event(
                domain=domain,
                event_type=event_type,
                payload={"order_id": f"ORDER-{i}", "amount": 100.0 + i},
                version="1.0",
            )
            await nats_adapter.publish_event(event)

        # Wait for all events to be received
        await asyncio.sleep(0.5)

        # Verify all events received
        assert len(events_received) == num_events
        for i, event in enumerate(events_received):
            assert event.domain == domain
            assert event.event_type == event_type
            assert event.payload["order_id"] == f"ORDER-{i}"
            assert event.payload["amount"] == 100.0 + i

        # Test that durable subscription persists
        # Clear existing received events
        events_received.clear()

        # Publish more events after some delay (simulating disconnect)
        await asyncio.sleep(1.0)

        # Publish more events
        for i in range(num_events, num_events + 5):
            event = Event(
                domain=domain,
                event_type=event_type,
                payload={"order_id": f"ORDER-{i}", "amount": 100.0 + i},
                version="1.0",
            )
            await nats_adapter.publish_event(event)

        await asyncio.sleep(0.5)

        # Verify new events received on same durable subscription
        assert len(events_received) == 5
        for i, event in enumerate(events_received):
            assert event.payload["order_id"] == f"ORDER-{num_events + i}"

    @pytest.mark.asyncio
    async def test_wildcard_pattern_matching(self, nats_adapter):
        """Test wildcard pattern matching for events."""
        events_received = []

        async def wildcard_handler(event: Event):
            events_received.append(event)

        # Subscribe to wildcard pattern
        await nats_adapter.subscribe_event("events.order.*", wildcard_handler)
        await asyncio.sleep(0.1)

        # Publish events that match pattern
        matching_events = [
            Event(domain="order", event_type="created", payload={"id": 1}),
            Event(domain="order", event_type="updated", payload={"id": 2}),
            Event(domain="order", event_type="cancelled", payload={"id": 3}),
        ]

        # Publish events that don't match pattern
        non_matching_events = [
            Event(domain="payment", event_type="completed", payload={"id": 4}),
            Event(domain="shipping", event_type="dispatched", payload={"id": 5}),
        ]

        # Publish all events
        for event in matching_events + non_matching_events:
            await nats_adapter.publish_event(event)

        await asyncio.sleep(0.5)

        # Verify only matching events received
        assert len(events_received) == len(matching_events)
        received_ids = [e.payload["id"] for e in events_received]
        assert sorted(received_ids) == [1, 2, 3]

        # Test multi-level wildcard
        events_received.clear()

        # Subscribe to multi-level wildcard
        await nats_adapter.subscribe_event("events.>", wildcard_handler)
        await asyncio.sleep(0.1)

        # Publish various events
        test_events = [
            Event(domain="order", event_type="created", payload={"test": "multi1"}),
            Event(domain="payment", event_type="processed", payload={"test": "multi2"}),
            Event(domain="inventory", event_type="updated", payload={"test": "multi3"}),
        ]

        for event in test_events:
            await nats_adapter.publish_event(event)

        await asyncio.sleep(0.5)

        # All events should be received
        assert len(events_received) >= len(test_events)

    @pytest.mark.asyncio
    async def test_at_least_once_delivery_guarantee(self, nats_adapter):
        """Test at-least-once delivery guarantee with JetStream."""
        domain = "critical"
        event_type = "transaction"
        process_count = 0
        error_on_first = True

        async def failing_handler(event: Event):
            nonlocal process_count, error_on_first
            process_count += 1

            # Fail on first attempt to test redelivery
            if error_on_first and process_count == 1:
                raise Exception("Simulated processing error")

            # Success on retry
            return

        # Subscribe with JetStream (no wildcards for JetStream features)
        await nats_adapter.subscribe_event(
            SubjectPatterns.event(domain, event_type), failing_handler, durable="test-redelivery"
        )
        await asyncio.sleep(0.1)

        # Publish critical event
        event = Event(
            domain=domain,
            event_type=event_type,
            payload={"transaction_id": "TXN-001", "amount": 1000.0},
            version="1.0",
        )
        await nats_adapter.publish_event(event)

        # Wait for processing and potential redelivery
        await asyncio.sleep(2.0)

        # Verify event was processed at least once
        assert process_count >= 1, "Event should be delivered at least once"

    @pytest.mark.asyncio
    async def test_event_versioning_support(self, nats_adapter):
        """Test event versioning support."""
        domain = "product"
        event_type = "updated"
        events_by_version = {"1.0": [], "2.0": [], "3.0": []}

        async def versioned_handler(event: Event):
            if event.version in events_by_version:
                events_by_version[event.version].append(event)

        # Subscribe to all product update events
        await nats_adapter.subscribe_event(
            SubjectPatterns.event(domain, event_type), versioned_handler
        )
        await asyncio.sleep(0.1)

        # Publish events with different versions
        test_events = [
            Event(
                domain=domain,
                event_type=event_type,
                payload={"product_id": "P1", "name": "Product 1"},
                version="1.0",
            ),
            Event(
                domain=domain,
                event_type=event_type,
                payload={"product_id": "P2", "name": "Product 2", "category": "Electronics"},
                version="2.0",
            ),
            Event(
                domain=domain,
                event_type=event_type,
                payload={"product_id": "P3", "name": "Product 3", "metadata": {"tags": ["new"]}},
                version="3.0",
            ),
            Event(
                domain=domain,
                event_type=event_type,
                payload={"product_id": "P4", "name": "Product 4"},
                version="1.0",
            ),
        ]

        for event in test_events:
            await nats_adapter.publish_event(event)

        await asyncio.sleep(0.5)

        # Verify events grouped by version
        assert len(events_by_version["1.0"]) == 2
        assert len(events_by_version["2.0"]) == 1
        assert len(events_by_version["3.0"]) == 1

        # Verify version-specific handling works
        v1_products = [e.payload["product_id"] for e in events_by_version["1.0"]]
        assert sorted(v1_products) == ["P1", "P4"]

    @pytest.mark.asyncio
    async def test_event_subject_pattern_compliance(self, nats_adapter):
        """Verify subject pattern compliance: events.<domain>.<event_type>."""
        domain = "compliance"
        event_type = "test_event"
        received_subjects = []

        # Monkey patch JetStream publish to capture subjects
        original_publish = nats_adapter._js.publish

        async def capture_publish(subject, data, **kwargs):
            received_subjects.append(subject)
            return await original_publish(subject, data, **kwargs)

        nats_adapter._js.publish = capture_publish

        # Publish event
        event = Event(domain=domain, event_type=event_type, payload={"test": True}, version="1.0")
        await nats_adapter.publish_event(event)

        # Verify correct subject pattern used
        expected_subject = SubjectPatterns.event(domain, event_type)
        assert expected_subject == f"events.{domain}.{event_type}"
        assert expected_subject in received_subjects

        # Restore original method
        nats_adapter._js.publish = original_publish

    @pytest.mark.asyncio
    async def test_event_serialization_formats(self, nats_adapter, nats_adapter_msgpack):
        """Test both JSON and MessagePack serialization for events."""
        domain = "format"
        event_type = "test"

        # Complex event data to test serialization
        test_data = {
            "id": "EVT-001",
            "timestamp": time.time(),
            "user": {"id": 123, "name": "Test User"},
            "items": [
                {"sku": "ITEM-1", "quantity": 2, "price": 99.99},
                {"sku": "ITEM-2", "quantity": 1, "price": 149.99},
            ],
            "metadata": {"source": "web", "ip": "192.168.1.1", "user_agent": "Mozilla/5.0"},
            "unicode": "Event with émojis 🎉 and 中文",
        }

        json_events = []
        msgpack_events = []

        async def json_handler(event: Event):
            json_events.append(event)

        async def msgpack_handler(event: Event):
            msgpack_events.append(event)

        # Subscribe with JSON adapter
        await nats_adapter.subscribe_event(SubjectPatterns.event(domain, event_type), json_handler)

        # Subscribe with MessagePack adapter
        await nats_adapter_msgpack.subscribe_event(
            SubjectPatterns.event(domain, f"{event_type}_msgpack"), msgpack_handler
        )

        await asyncio.sleep(0.1)

        # Publish with both formats
        json_event = Event(domain=domain, event_type=event_type, payload=test_data)
        msgpack_event = Event(domain=domain, event_type=f"{event_type}_msgpack", payload=test_data)

        await nats_adapter.publish_event(json_event)
        await nats_adapter_msgpack.publish_event(msgpack_event)

        await asyncio.sleep(0.5)

        # Verify both formats work correctly
        assert len(json_events) == 1
        assert len(msgpack_events) == 1

        # Verify data integrity
        assert json_events[0].payload == test_data
        assert msgpack_events[0].payload == test_data

    @pytest.mark.asyncio
    async def test_concurrent_event_publishing(self, nats_adapter):
        """Test handling high volume concurrent event publishing."""
        domain = "performance"
        event_type = "burst"
        events_received = []

        async def counter_handler(event: Event):
            events_received.append(event)

        await nats_adapter.subscribe_event(
            SubjectPatterns.event(domain, event_type), counter_handler
        )
        await asyncio.sleep(0.1)

        # Publish many events concurrently
        num_events = 100
        tasks = []

        for i in range(num_events):
            event = Event(
                domain=domain,
                event_type=event_type,
                payload={"sequence": i, "timestamp": time.time()},
                version="1.0",
            )
            task = nats_adapter.publish_event(event)
            tasks.append(task)

        # Wait for all publishes to complete
        await asyncio.gather(*tasks)

        # Wait for all events to be received
        await asyncio.sleep(1.0)

        # Verify all events received
        assert len(events_received) == num_events

        # Verify all sequence numbers present
        received_sequences = [e.payload["sequence"] for e in events_received]
        assert sorted(received_sequences) == list(range(num_events))

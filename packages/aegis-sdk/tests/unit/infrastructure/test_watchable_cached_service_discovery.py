"""Unit tests for Watchable Cached Service Discovery."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk.domain.models import KVEntry, KVWatchEvent, ServiceInstance
from aegis_sdk.infrastructure import (
    BasicServiceDiscovery,
    WatchableCacheConfig,
    WatchableCachedServiceDiscovery,
    WatchConfig,
)
from aegis_sdk.ports.kv_store import KVStorePort
from aegis_sdk.ports.logger import LoggerPort
from aegis_sdk.ports.metrics import MetricsPort


class MockKVStore(KVStorePort):
    """Mock KV Store for testing."""

    def __init__(self):
        self.watch_events = []
        self._connected = False
        self._watch_cancelled = False

    async def connect(self, bucket: str, ttl: int | None = None) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def get(self, key: str) -> KVEntry | None:
        return None

    async def put(self, key: str, value, options=None) -> int:
        return 1

    async def delete(self, key: str, revision: int | None = None) -> bool:
        return True

    async def exists(self, key: str) -> bool:
        return False

    async def keys(self, prefix: str = "") -> list[str]:
        return []

    async def get_many(self, keys: list[str]) -> dict[str, KVEntry]:
        return {}

    async def put_many(self, entries: dict[str, any], options=None) -> dict[str, int]:
        return dict.fromkeys(entries, 1)

    async def delete_many(self, keys: list[str]) -> dict[str, bool]:
        return dict.fromkeys(keys, True)

    async def watch(self, key: str | None = None, prefix: str | None = None):
        """Mock watch that yields predefined events."""
        # Clear watch events after use to prevent re-yielding
        events_to_yield = self.watch_events[:]
        self.watch_events = []

        for event in events_to_yield:
            yield event
            await asyncio.sleep(0.01)  # Small delay to simulate real behavior

        # If no events or all events consumed, wait until cancelled
        # Use a shorter sleep to be more responsive to cancellation
        try:
            while not self._watch_cancelled:
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            # Clean shutdown when cancelled
            pass
        finally:
            self._watch_cancelled = False

    async def history(self, key: str, limit: int = 10) -> list[KVEntry]:
        return []

    async def purge(self, key: str) -> None:
        pass

    async def clear(self, prefix: str = "") -> int:
        return 0

    async def status(self) -> dict[str, any]:
        return {"connected": self._connected}


@pytest.mark.asyncio
class TestWatchableCachedServiceDiscovery:
    """Test Watchable Cached Service Discovery functionality."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        return AsyncMock()

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        logger = MagicMock(spec=LoggerPort)
        logger.info = MagicMock()
        logger.debug = MagicMock()
        logger.warning = MagicMock()
        logger.error = MagicMock()
        return logger

    @pytest.fixture
    def mock_metrics(self):
        """Create mock metrics."""
        return MagicMock(spec=MetricsPort)

    @pytest.fixture
    def mock_kv_store(self):
        """Create mock KV store."""
        return MockKVStore()

    @pytest.fixture
    def test_instances(self):
        """Create test service instances."""
        return [
            ServiceInstance(
                service_name="test-service",
                instance_id="instance-1",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
            ServiceInstance(
                service_name="test-service",
                instance_id="instance-2",
                version="1.0.0",
                status="ACTIVE",
                last_heartbeat=datetime.now(UTC),
            ),
        ]

    async def test_watchable_discovery_with_watch_disabled(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics, test_instances
    ):
        """Test watchable discovery when watch is disabled."""
        # Configure registry to return test instances
        mock_registry.list_instances.return_value = test_instances

        # Create basic discovery
        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)

        # Create config with watch disabled
        config = WatchableCacheConfig(
            ttl_seconds=10.0,
            watch=WatchConfig(enabled=False),
        )

        # Create watchable discovery
        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, mock_kv_store, config, mock_metrics, mock_logger
        )

        # Watch should not be enabled
        assert not discovery.is_watch_enabled()

        # Should work as regular cached discovery
        instances = await discovery.discover_instances("test-service")
        assert len(instances) == 2

        # Cache should work
        instances2 = await discovery.discover_instances("test-service")
        assert instances == instances2

        stats = discovery.get_cache_stats()
        assert stats["cache_hits"] == 1

    async def test_watchable_discovery_with_watch_enabled(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics, test_instances
    ):
        """Test watchable discovery with watch enabled."""
        # Configure registry
        mock_registry.list_instances.return_value = test_instances

        # Create basic discovery
        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)

        # Create config with watch enabled
        config = WatchableCacheConfig(
            ttl_seconds=30.0,
            watch=WatchConfig(
                enabled=True,
                reconnect_delay=0.1,
                max_reconnect_attempts=3,
            ),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, mock_kv_store, config, mock_metrics, mock_logger
        ) as discovery:
            # Watch should be enabled
            assert discovery.is_watch_enabled()

            # Wait for watch to start
            await asyncio.sleep(0.1)

            # Should work normally
            instances = await discovery.discover_instances("test-service")
            assert len(instances) == 2

            # Check watch stats
            stats = discovery.get_watch_stats()
            assert stats["enabled"]
            assert stats["running"]
            assert stats["reconnect_attempts"] == 0

    async def test_watch_event_handling(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics, test_instances
    ):
        """Test handling of watch events."""
        # Configure registry
        mock_registry.list_instances.return_value = test_instances

        # Add watch events to mock KV store
        entry = KVEntry(
            key="service-instances.test-service.instance-3",
            value={"service_name": "test-service", "instance_id": "instance-3"},
            revision=1,
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
        )

        mock_kv_store.watch_events = [
            KVWatchEvent(operation="PUT", entry=entry),
            KVWatchEvent(operation="DELETE", entry=entry),
        ]

        # Create discovery
        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)
        config = WatchableCacheConfig(
            ttl_seconds=30.0,
            watch=WatchConfig(enabled=True),
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, mock_kv_store, config, mock_metrics, mock_logger
        )

        try:
            # Start watch manually
            discovery._start_watch()

            # Populate cache
            await discovery.discover_instances("test-service")

            # Wait for watch events to be processed
            # Events should be processed quickly
            await asyncio.sleep(0.05)

            # Check that cache was invalidated (logger calls)
            # The events should trigger cache invalidation
            info_logs = [str(call) for call in mock_logger.info.call_args_list]
            assert any(
                "Cache invalidated due to watch event" in log for log in info_logs
            ), f"Expected cache invalidation log not found. Logs: {info_logs}"
        finally:
            # Stop the watch task
            await discovery.stop_watch()

    async def test_watch_reconnection_logic(self, mock_registry, mock_logger, mock_metrics):
        """Test watch reconnection on failures."""
        # Create a KV store that fails on watch
        failing_kv_store = MockKVStore()

        async def failing_watch(*args, **kwargs):
            raise Exception("Connection lost")
            if False:  # This makes it a generator without yielding
                yield

        failing_kv_store.watch = failing_watch

        # Create discovery
        basic_discovery = MagicMock()
        basic_discovery.discover_instances = AsyncMock(return_value=[])
        basic_discovery.get_selector = AsyncMock()
        basic_discovery.invalidate_cache = AsyncMock()

        config = WatchableCacheConfig(
            watch=WatchConfig(
                enabled=True,
                reconnect_delay=0.1,
                max_reconnect_attempts=2,
            ),
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, failing_kv_store, config, mock_metrics, mock_logger
        )

        # Wait for reconnection attempts
        await asyncio.sleep(0.5)

        # Check reconnection attempts
        stats = discovery.get_watch_stats()
        assert stats["reconnect_attempts"] >= 1

        # Stop watch
        await discovery.stop_watch()

    async def test_watch_stop_gracefully(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics
    ):
        """Test graceful watch stop."""
        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)
        config = WatchableCacheConfig(
            watch=WatchConfig(enabled=True),
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, mock_kv_store, config, mock_metrics, mock_logger
        )

        # Watch should be running
        assert discovery.is_watch_enabled()

        # Stop watch
        await discovery.stop_watch()

        # Watch should be stopped
        assert not discovery.is_watch_enabled()

        # Stats should reflect stopped state
        stats = discovery.get_watch_stats()
        assert not stats["running"]

    async def test_watch_handles_delete_without_entry(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics
    ):
        """Test handling DELETE/PURGE events without entry."""
        # Add DELETE event without entry
        mock_kv_store.watch_events = [
            KVWatchEvent(operation="DELETE", entry=None),
            KVWatchEvent(operation="PURGE", entry=None),
        ]

        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)
        config = WatchableCacheConfig(
            watch=WatchConfig(enabled=True),
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, mock_kv_store, config, mock_metrics, mock_logger
        ):
            # Wait for events to be processed
            await asyncio.sleep(0.3)

            # Should log debug message
            assert any(
                "Received DELETE/PURGE without entry" in str(call)
                for call in mock_logger.debug.call_args_list
            )

    async def test_context_manager_usage(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics
    ):
        """Test async context manager usage."""
        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)
        config = WatchableCacheConfig(
            watch=WatchConfig(enabled=True),
        )

        # Use as context manager
        async with WatchableCachedServiceDiscovery(
            basic_discovery, mock_kv_store, config, mock_metrics, mock_logger
        ) as discovery:
            assert discovery.is_watch_enabled()

        # Watch should be stopped after exit
        assert not discovery.is_watch_enabled()

    async def test_get_cache_stats_includes_watch_stats(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics
    ):
        """Test that cache stats include watch stats."""
        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)
        config = WatchableCacheConfig(
            watch=WatchConfig(
                enabled=True,
                reconnect_delay=5.0,
                max_reconnect_attempts=10,
            ),
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, mock_kv_store, config, mock_metrics, mock_logger
        )

        # Get combined stats
        stats = discovery.get_cache_stats()

        # Should include watch stats
        assert "watch" in stats
        assert stats["watch"]["enabled"]
        assert stats["watch"]["running"]
        assert stats["watch"]["config"]["reconnect_delay"] == 5.0
        assert stats["watch"]["config"]["max_reconnect_attempts"] == 10

        # Stop watch
        await discovery.stop_watch()

    async def test_metrics_recording_on_watch_events(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics
    ):
        """Test that metrics are recorded for watch events."""
        # Configure mock metrics
        mock_metrics.increment = MagicMock()

        # Add watch event
        entry = KVEntry(
            key="service-instances.metrics-test.instance-1",
            value={},
            revision=1,
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
        )
        mock_kv_store.watch_events = [
            KVWatchEvent(operation="PUT", entry=entry),
        ]

        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)
        config = WatchableCacheConfig(
            watch=WatchConfig(enabled=True),
            enable_metrics=True,
        )

        async with WatchableCachedServiceDiscovery(
            basic_discovery, mock_kv_store, config, mock_metrics, mock_logger
        ):
            # Wait for event processing
            await asyncio.sleep(0.3)

            # Check metrics were recorded
            mock_metrics.increment.assert_any_call("service_discovery.watch.events.put")
            mock_metrics.increment.assert_any_call(
                "service_discovery.watch.invalidations.metrics-test"
            )

    async def test_watch_task_timeout_on_stop(self, mock_registry, mock_logger, mock_metrics):
        """Test watch task timeout handling on stop."""
        # Create a KV store with slow watch
        slow_kv_store = MockKVStore()

        async def slow_watch(*args, **kwargs):
            try:
                while True:
                    await asyncio.sleep(0.1)  # Small delay to avoid CPU spin
                    # Never yields any events
            except asyncio.CancelledError:
                raise
            if False:  # This makes it a generator without yielding
                yield

        slow_kv_store.watch = slow_watch

        basic_discovery = MagicMock()
        basic_discovery.discover_instances = AsyncMock(return_value=[])
        basic_discovery.get_selector = AsyncMock()
        basic_discovery.invalidate_cache = AsyncMock()

        config = WatchableCacheConfig(
            watch=WatchConfig(enabled=True),
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, slow_kv_store, config, mock_metrics, mock_logger
        )

        # Wait for watch to start
        await asyncio.sleep(0.1)
        assert discovery.is_watch_enabled()

        # Stop watch (should timeout and cancel)
        await discovery.stop_watch()

        # Check warning was logged
        assert any(
            "Watch task did not stop gracefully" in str(call)
            for call in mock_logger.warning.call_args_list
        )

    async def test_start_watch_skips_if_already_running(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics
    ):
        """Test that _start_watch returns early if watch task is already running."""
        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)
        config = WatchableCacheConfig(
            watch=WatchConfig(enabled=True),
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, mock_kv_store, config, mock_metrics, mock_logger
        )

        # Watch should be started automatically
        assert discovery.is_watch_enabled()
        first_task = discovery._watch_task

        # Try to start watch again
        discovery._start_watch()

        # Should be the same task
        assert discovery._watch_task is first_task

        await discovery.stop_watch()

    async def test_watch_loop_resets_reconnect_attempts_on_success(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics
    ):
        """Test that successful watch resets reconnect attempts."""
        # Create a KV store that fails once then succeeds
        failing_kv_store = MockKVStore()
        call_count = 0
        continue_watch = True

        async def intermittent_watch(*args, **kwargs):
            nonlocal call_count, continue_watch
            call_count += 1
            if call_count == 1:
                raise Exception("First call fails")
            # Second call succeeds - create a proper async generator
            # that completes after _watch_kv_store enters the loop
            if call_count == 2:
                # Yield nothing to let the async for loop start
                # Then complete to trigger the reset
                return
            # For subsequent calls, keep running until stopped
            while continue_watch:
                await asyncio.sleep(0.01)
            yield  # Makes this an async generator

        failing_kv_store.watch = intermittent_watch

        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)
        config = WatchableCacheConfig(
            watch=WatchConfig(
                enabled=True,
                reconnect_delay=0.05,  # Shorter delay for faster test
                max_reconnect_attempts=5,
            ),
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, failing_kv_store, config, mock_metrics, mock_logger
        )

        try:
            # Start the watch manually
            discovery._start_watch()

            # Wait for first failure
            await asyncio.sleep(0.02)

            # After first failure, attempts should be 1
            assert discovery._reconnect_attempts == 1

            # Wait for reconnect delay and successful second call
            await asyncio.sleep(0.08)

            # The second call completes immediately, resetting attempts
            # Wait a bit for the reset to happen
            await asyncio.sleep(0.05)

            # After successful watch completion, attempts should be reset
            assert discovery._reconnect_attempts == 0

            # Verify we had at least 2 calls (might be in 3rd by now)
            assert call_count >= 2

        finally:
            # Stop watching
            continue_watch = False
            # Ensure we stop the watch task
            await discovery.stop_watch()

    async def test_stop_watch_returns_early_if_no_task(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics
    ):
        """Test that stop_watch returns immediately if no watch task exists."""
        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)
        config = WatchableCacheConfig(
            watch=WatchConfig(enabled=False),  # Watch disabled
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, mock_kv_store, config, mock_metrics, mock_logger
        )

        # No watch task should exist
        assert discovery._watch_task is None

        # Stop should return immediately without error
        await discovery.stop_watch()

        # Still no task
        assert discovery._watch_task is None

    async def test_watch_loop_breaks_on_stop_event(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics
    ):
        """Test that watch loop exits when stop event is set."""
        # Create a KV store that yields events continuously
        continuous_kv_store = MockKVStore()

        async def continuous_watch(*args, **kwargs):
            while True:
                yield KVWatchEvent(
                    operation="PUT",
                    entry=KVEntry(
                        key="service-instances.test.inst1",
                        value={},
                        revision=1,
                        created_at=datetime.now(UTC).isoformat(),
                        updated_at=datetime.now(UTC).isoformat(),
                    ),
                )
                await asyncio.sleep(0.01)

        continuous_kv_store.watch = continuous_watch

        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)
        config = WatchableCacheConfig(
            watch=WatchConfig(enabled=True),
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, continuous_kv_store, config, mock_metrics, mock_logger
        )

        # Let it process a few events
        await asyncio.sleep(0.1)

        # Stop the watch
        await discovery.stop_watch()

        # Task should be done
        assert discovery._watch_task is None or discovery._watch_task.done()

    async def test_handle_watch_event_error_logging(
        self, mock_registry, mock_kv_store, mock_logger, mock_metrics
    ):
        """Test that errors in _handle_watch_event are logged but don't crash the watch."""
        # Create a discovery that will throw errors when handling events
        basic_discovery = BasicServiceDiscovery(mock_registry, mock_logger)
        config = WatchableCacheConfig(
            watch=WatchConfig(enabled=True),
        )

        discovery = WatchableCachedServiceDiscovery(
            basic_discovery, mock_kv_store, config, mock_metrics, mock_logger
        )

        # Mock invalidate_cache to raise an error
        discovery.invalidate_cache = AsyncMock(side_effect=Exception("Cache error"))

        # Add event that will trigger the error
        mock_kv_store.watch_events = [
            KVWatchEvent(
                operation="PUT",
                entry=KVEntry(
                    key="service-instances.test-service.instance-1",
                    value={},
                    revision=1,
                    created_at=datetime.now(UTC).isoformat(),
                    updated_at=datetime.now(UTC).isoformat(),
                ),
            )
        ]

        # Wait for event processing
        await asyncio.sleep(0.3)

        # Check that error was logged
        mock_logger.error.assert_called()
        assert any(
            "Error handling watch event" in str(call) for call in mock_logger.error.call_args_list
        )

        await discovery.stop_watch()

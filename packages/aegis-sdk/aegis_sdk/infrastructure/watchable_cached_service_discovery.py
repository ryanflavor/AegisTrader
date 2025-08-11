"""Cached Service Discovery with real-time KV Store watch support."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ..ports.logger import LoggerPort
from ..ports.metrics import MetricsPort
from .cached_service_discovery import CacheConfig, CachedServiceDiscovery

if TYPE_CHECKING:
    from ..ports.kv_store import KVStorePort
    from ..ports.service_discovery import ServiceDiscoveryPort


class WatchConfig(BaseModel):
    """Configuration for KV Store watch functionality."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
    )

    enabled: bool = Field(default=False)
    reconnect_delay: float = Field(default=5.0, gt=0)
    max_reconnect_attempts: int = Field(default=10, gt=0)
    prefix_pattern: str = Field(default="service-instances", min_length=1)


class WatchableCacheConfig(CacheConfig):
    """Extended cache configuration with watch support."""

    watch: WatchConfig = Field(default_factory=WatchConfig)


class WatchableCachedServiceDiscovery(CachedServiceDiscovery):
    """Cached service discovery with real-time KV Store watch support.

    This enhanced implementation adds optional real-time cache updates by watching
    the KV Store for service instance changes. When enabled, the cache is automatically
    updated when instances are added, modified, or removed without waiting for TTL expiration.
    """

    def __init__(
        self,
        inner: ServiceDiscoveryPort,
        kv_store: KVStorePort,
        config: WatchableCacheConfig | None = None,
        metrics: MetricsPort | None = None,
        logger: LoggerPort | None = None,
    ):
        """Initialize watchable cached service discovery.

        Args:
            inner: The underlying service discovery implementation
            kv_store: KV Store for watching changes
            config: Cache and watch configuration
            metrics: Optional metrics port for statistics
            logger: Optional logger for debugging
        """
        # Initialize parent with base config
        base_config = CacheConfig(
            ttl_seconds=config.ttl_seconds if config else 10.0,
            max_entries=config.max_entries if config else 1000,
            enable_metrics=config.enable_metrics if config else True,
        )
        super().__init__(inner, base_config, metrics, logger)

        self._kv_store = kv_store
        self._watch_config = config.watch if config else WatchConfig()
        self._watch_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._reconnect_attempts = 0

        # Start watch task if enabled
        if self._watch_config.enabled:
            self._start_watch()

    def _start_watch(self) -> None:
        """Start the background watch task."""
        if self._watch_task and not self._watch_task.done():
            return

        self._stop_event.clear()
        self._watch_task = asyncio.create_task(self._watch_loop())

        if self._logger:
            self._logger.info("Started KV Store watch for service discovery updates")

    async def _watch_loop(self) -> None:
        """Main watch loop with reconnection logic."""
        while not self._stop_event.is_set():
            try:
                await self._watch_kv_store()
                # Reset reconnect attempts on successful watch
                self._reconnect_attempts = 0
            except Exception as e:
                self._reconnect_attempts += 1

                if self._logger:
                    self._logger.error(
                        "KV Store watch error",
                        error=str(e),
                        attempts=self._reconnect_attempts,
                        max_attempts=self._watch_config.max_reconnect_attempts,
                    )

                # Check if we've exceeded max reconnect attempts
                if self._reconnect_attempts >= self._watch_config.max_reconnect_attempts:
                    if self._logger:
                        self._logger.error(
                            "Max reconnect attempts reached, disabling watch",
                            attempts=self._reconnect_attempts,
                        )
                    break

                # Wait before reconnecting
                await asyncio.sleep(self._watch_config.reconnect_delay)

    async def _watch_kv_store(self) -> None:
        """Watch KV Store for service instance changes."""
        prefix = f"{self._watch_config.prefix_pattern}__"

        if self._logger:
            self._logger.debug("Starting KV Store watch", prefix=prefix)

        async for event in self._kv_store.watch(prefix=prefix):  # type: ignore[attr-defined]
            if self._stop_event.is_set():
                break

            try:
                await self._handle_watch_event(event)
            except Exception as e:
                if self._logger:
                    self._logger.error(
                        "Error handling watch event",
                        operation=event.operation,
                        error=str(e),
                    )

    async def _handle_watch_event(self, event) -> None:
        """Handle a single watch event from KV Store.

        Args:
            event: KVWatchEvent from the KV Store
        """
        # Extract service name from key
        # Key format: service-instances__{service_name}__{instance_id}
        if event.entry and event.entry.key:
            parts = event.entry.key.split("__")
            if len(parts) >= 3:
                service_name = parts[1]

                if self._logger:
                    self._logger.debug(
                        "Processing watch event",
                        operation=event.operation,
                        service=service_name,
                        key=event.entry.key,
                    )

                # Invalidate cache for the affected service
                # This will force a fresh discovery on next request
                await self.invalidate_cache(service_name)

                # Record metrics
                if self._config.enable_metrics and self._metrics:
                    self._metrics.increment(
                        f"service_discovery.watch.events.{event.operation.lower()}"
                    )
                    self._metrics.increment(f"service_discovery.watch.invalidations.{service_name}")

                if self._logger:
                    self._logger.info(
                        "Cache invalidated due to watch event",
                        operation=event.operation,
                        service=service_name,
                    )

        elif event.operation in ["DELETE", "PURGE"]:
            # For DELETE/PURGE without entry, we might need to handle differently
            if self._logger:
                self._logger.debug(
                    "Received DELETE/PURGE without entry",
                    operation=event.operation,
                )

    async def stop_watch(self) -> None:
        """Stop the watch task gracefully."""
        if not self._watch_task:
            return

        self._stop_event.set()

        # Wait for task to complete with timeout
        try:
            await asyncio.wait_for(self._watch_task, timeout=5.0)
        except TimeoutError:
            if self._logger:
                self._logger.warning("Watch task did not stop gracefully, cancelling")
            self._watch_task.cancel()

        self._watch_task = None

        if self._logger:
            self._logger.info("Stopped KV Store watch")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - stop watch task."""
        await self.stop_watch()

    def is_watch_enabled(self) -> bool:
        """Check if watch is enabled and running.

        Returns:
            True if watch is enabled and task is running
        """
        return (
            self._watch_config.enabled
            and self._watch_task is not None
            and not self._watch_task.done()
        )

    def get_watch_stats(self) -> dict:
        """Get watch statistics.

        Returns:
            Dictionary with watch statistics
        """
        return {
            "enabled": self._watch_config.enabled,
            "running": self.is_watch_enabled(),
            "reconnect_attempts": self._reconnect_attempts,
            "config": {
                "reconnect_delay": self._watch_config.reconnect_delay,
                "max_reconnect_attempts": self._watch_config.max_reconnect_attempts,
                "prefix_pattern": self._watch_config.prefix_pattern,
            },
        }

    def get_cache_stats(self) -> dict:
        """Get combined cache and watch statistics.

        Returns:
            Dictionary with cache and watch statistics
        """
        stats = super().get_cache_stats()
        stats["watch"] = self.get_watch_stats()
        return stats

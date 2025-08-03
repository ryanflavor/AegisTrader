"""Cached wrapper for Service Discovery implementations."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..domain.models import ServiceInstance
from ..ports.logger import LoggerPort
from ..ports.metrics import MetricsPort
from ..ports.service_discovery import (
    InstanceSelector,
    SelectionStrategy,
    ServiceDiscoveryPort,
)


class CacheEntry(BaseModel):
    """Cache entry for discovered instances."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
    )

    instances: list[ServiceInstance]
    timestamp: float
    hits: int = Field(default=0, ge=0)

    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if this cache entry has expired based on TTL."""
        age = time.time() - self.timestamp
        return age >= ttl_seconds

    def increment_hits(self) -> None:
        """Increment the hit counter for this entry."""
        self.hits += 1


class CacheConfig(BaseModel):
    """Configuration for service discovery cache."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
    )

    ttl_seconds: float = Field(default=10.0, gt=0)
    max_entries: int = Field(default=1000, gt=0)
    enable_metrics: bool = Field(default=True)


class CachedServiceDiscovery(ServiceDiscoveryPort):
    """Cached wrapper for service discovery implementations.

    This wrapper adds TTL-based caching to any ServiceDiscoveryPort implementation,
    reducing the load on the service registry and improving discovery performance.
    """

    def __init__(
        self,
        inner: ServiceDiscoveryPort,
        config: CacheConfig | None = None,
        metrics: MetricsPort | None = None,
        logger: LoggerPort | None = None,
    ):
        """Initialize cached service discovery.

        Args:
            inner: The underlying service discovery implementation
            config: Cache configuration (defaults used if None)
            metrics: Optional metrics port for cache statistics
            logger: Optional logger for debugging
        """
        self._inner = inner
        self._config = config or CacheConfig()
        self._metrics = metrics
        self._logger = logger
        self._cache: dict[str, CacheEntry] = {}
        self._total_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0

    def _is_cache_valid(self, entry: CacheEntry) -> bool:
        """Check if a cache entry is still valid based on TTL."""
        return not entry.is_expired(self._config.ttl_seconds)

    def _record_hit(self, service_name: str, cache_key: str | None = None) -> None:
        """Record a cache hit.

        Args:
            service_name: The service name for metrics/logging
            cache_key: The actual cache key to use for incrementing hits
        """
        self._cache_hits += 1

        # Use provided cache_key or try to find one that matches the service
        if cache_key and cache_key in self._cache:
            self._cache[cache_key].increment_hits()
        elif not cache_key:
            # Try to find any cache key for this service
            for key in self._cache:
                if key.startswith(f"{service_name}:"):
                    self._cache[key].increment_hits()
                    break

        if self._config.enable_metrics and self._metrics:
            self._metrics.increment(f"service_discovery.cache.hits.{service_name}")

        if self._logger:
            self._logger.debug(
                "Service discovery cache hit",
                service=service_name,
                hit_rate=self._get_hit_rate(),
            )

    def _record_miss(self, service_name: str) -> None:
        """Record a cache miss."""
        self._cache_misses += 1

        if self._config.enable_metrics and self._metrics:
            self._metrics.increment(f"service_discovery.cache.misses.{service_name}")

        if self._logger:
            self._logger.debug(
                "Service discovery cache miss",
                service=service_name,
                hit_rate=self._get_hit_rate(),
            )

    def _get_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._cache_hits + self._cache_misses
        if total == 0:
            return 0.0
        return self._cache_hits / total

    def _evict_old_entries(self) -> None:
        """Evict expired cache entries."""
        expired_keys = [
            key for key, entry in self._cache.items() if entry.is_expired(self._config.ttl_seconds)
        ]

        for key in expired_keys:
            del self._cache[key]
            if self._logger:
                self._logger.debug("Evicted expired cache entry", service=key)

    def _ensure_cache_size(self) -> None:
        """Ensure cache doesn't exceed max entries by evicting LRU entries."""
        if len(self._cache) <= self._config.max_entries:
            return

        # Sort by least recently used (oldest timestamp)
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].timestamp,
        )

        # Evict oldest entries
        entries_to_remove = len(self._cache) - self._config.max_entries
        for key, _ in sorted_entries[:entries_to_remove]:
            del self._cache[key]
            if self._logger:
                self._logger.debug("Evicted LRU cache entry", service=key)

    async def discover_instances(
        self, service_name: str, only_healthy: bool = True
    ) -> list[ServiceInstance]:
        """Discover instances with caching.

        Args:
            service_name: Name of the service to discover
            only_healthy: Whether to return only healthy instances

        Returns:
            List of discovered service instances (from cache if available)
        """
        self._total_requests += 1

        # Create cache key including health filter
        cache_key = f"{service_name}:{only_healthy}"

        # Check cache
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if self._is_cache_valid(entry):
                self._record_hit(service_name, cache_key)
                return entry.instances.copy()  # Return a copy to prevent external modification

        # Cache miss or expired
        self._record_miss(service_name)

        try:
            # Discover from inner implementation
            instances = await self._inner.discover_instances(service_name, only_healthy)

            # Update cache
            self._cache[cache_key] = CacheEntry(
                instances=instances,
                timestamp=time.time(),
            )

            # Maintain cache size
            self._evict_old_entries()
            self._ensure_cache_size()

            if self._logger:
                self._logger.info(
                    "Cached service discovery results",
                    service=service_name,
                    instance_count=len(instances),
                    ttl=self._config.ttl_seconds,
                )

            return instances

        except Exception as e:
            if self._logger:
                self._logger.error(
                    "Service discovery failed, checking stale cache",
                    service=service_name,
                    error=str(e),
                )

            # On failure, return stale cache if available
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                if self._logger:
                    self._logger.warning(
                        "Using stale cache due to discovery failure",
                        service=service_name,
                        age_seconds=time.time() - entry.timestamp,
                    )
                return entry.instances

            # Re-raise if no cache available
            raise

    async def select_instance(
        self,
        service_name: str,
        strategy: SelectionStrategy = SelectionStrategy.ROUND_ROBIN,
        preferred_instance_id: str | None = None,
    ) -> ServiceInstance | None:
        """Select instance using cached discovery results.

        Args:
            service_name: Name of the service
            strategy: Selection strategy to use
            preferred_instance_id: Optional preferred instance for sticky selection

        Returns:
            Selected instance or None if no healthy instances available
        """
        # Discover instances (will use cache if available)
        instances = await self.discover_instances(service_name, only_healthy=True)
        if not instances:
            return None

        # Use inner selector
        selector = await self.get_selector(strategy)
        return await selector.select(instances, service_name, preferred_instance_id)

    async def get_selector(self, strategy: SelectionStrategy) -> InstanceSelector:
        """Get selector from inner implementation."""
        return await self._inner.get_selector(strategy)

    async def invalidate_cache(self, service_name: str | None = None) -> None:
        """Invalidate cache entries.

        Args:
            service_name: Optional service name to invalidate, None for all
        """
        if service_name:
            # Invalidate all entries for this service (both healthy and all)
            keys_to_remove = [key for key in self._cache if key.startswith(f"{service_name}:")]
            for key in keys_to_remove:
                del self._cache[key]

            if self._logger:
                self._logger.info(
                    "Invalidated cache for service",
                    service=service_name,
                    entries_removed=len(keys_to_remove),
                )
        else:
            # Clear entire cache
            entries_count = len(self._cache)
            self._cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0

            if self._logger:
                self._logger.info(
                    "Invalidated entire cache",
                    entries_removed=entries_count,
                )

        # Also invalidate inner implementation's cache if it has one
        await self._inner.invalidate_cache(service_name)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "total_requests": self._total_requests,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": self._get_hit_rate(),
            "cache_size": len(self._cache),
            "config": {
                "ttl_seconds": self._config.ttl_seconds,
                "max_entries": self._config.max_entries,
                "enable_metrics": self._config.enable_metrics,
            },
        }

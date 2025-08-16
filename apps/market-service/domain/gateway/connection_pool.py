"""
Connection Pool for managing multiple gateway front addresses
Provides failover, load balancing, and blacklisting capabilities
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LoadBalancingStrategy(Enum):
    """Load balancing strategies for connection pool"""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_RECENTLY_USED = "least_recently_used"
    LEAST_CONNECTIONS = "least_connections"


class ConnectionEndpoint(BaseModel):
    """Represents a single connection endpoint"""

    address: str = Field(description="Connection address (e.g., tcp://host:port)")
    priority: int = Field(default=1, description="Priority for this endpoint (higher = preferred)")
    is_active: bool = Field(default=True, description="Whether endpoint is currently active")
    is_blacklisted: bool = Field(default=False, description="Whether endpoint is blacklisted")
    blacklist_until: datetime | None = Field(default=None, description="Blacklist expiry time")
    last_used: datetime | None = Field(default=None, description="Last successful use time")
    last_failed: datetime | None = Field(default=None, description="Last failure time")
    failure_count: int = Field(default=0, description="Number of consecutive failures")
    success_count: int = Field(default=0, description="Number of successful connections")
    active_connections: int = Field(default=0, description="Current active connections")

    def is_available(self) -> bool:
        """Check if endpoint is available for use"""
        if not self.is_active:
            return False

        if self.is_blacklisted:
            # Check if blacklist has expired
            if self.blacklist_until and datetime.now() >= self.blacklist_until:
                self.is_blacklisted = False
                self.blacklist_until = None
                self.failure_count = 0
                return True
            return False

        return True

    def record_success(self) -> None:
        """Record successful connection"""
        self.success_count += 1
        self.failure_count = 0
        self.last_used = datetime.now()

    def record_failure(self) -> None:
        """Record failed connection"""
        self.failure_count += 1
        self.last_failed = datetime.now()

    def blacklist(self, duration: timedelta) -> None:
        """Blacklist this endpoint for specified duration"""
        self.is_blacklisted = True
        self.blacklist_until = datetime.now() + duration

    def increment_connections(self) -> None:
        """Increment active connection count"""
        self.active_connections += 1

    def decrement_connections(self) -> None:
        """Decrement active connection count"""
        self.active_connections = max(0, self.active_connections - 1)


@dataclass
class ConnectionPoolConfig:
    """Configuration for connection pool"""

    strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    blacklist_threshold: int = 3  # Failures before blacklisting
    blacklist_duration: int = 300  # Seconds to blacklist
    max_connections_per_endpoint: int = 10
    enable_health_checks: bool = True
    health_check_interval: int = 30  # Seconds


class ConnectionPoolStats(BaseModel):
    """Statistics for connection pool"""

    total_endpoints: int = 0
    available_endpoints: int = 0
    blacklisted_endpoints: int = 0
    total_connections: int = 0
    total_failures: int = 0
    total_successes: int = 0
    current_index: int = 0


class ConnectionPool:
    """
    Manages multiple connection endpoints with failover and load balancing
    """

    def __init__(
        self,
        endpoints: list[str],
        config: ConnectionPoolConfig | None = None,
    ):
        """
        Initialize connection pool

        Args:
            endpoints: List of connection endpoint addresses
            config: Pool configuration
        """
        self.config = config or ConnectionPoolConfig()
        self.endpoints: list[ConnectionEndpoint] = [
            ConnectionEndpoint(address=addr) for addr in endpoints
        ]
        self.stats = ConnectionPoolStats(total_endpoints=len(self.endpoints))
        self._lock = asyncio.Lock()
        self._round_robin_index = 0
        self._health_check_task: asyncio.Task | None = None

    def get_available_endpoints(self) -> list[ConnectionEndpoint]:
        """Get list of available endpoints"""
        return [ep for ep in self.endpoints if ep.is_available()]

    async def get_next_endpoint(self) -> ConnectionEndpoint | None:
        """
        Get next endpoint based on configured strategy

        Returns:
            Next available endpoint or None if all are unavailable
        """
        async with self._lock:
            available = self.get_available_endpoints()

            if not available:
                return None

            # Update stats
            self.stats.available_endpoints = len(available)
            self.stats.blacklisted_endpoints = sum(1 for ep in self.endpoints if ep.is_blacklisted)

            # Select based on strategy
            if self.config.strategy == LoadBalancingStrategy.ROUND_ROBIN:
                endpoint = self._select_round_robin(available)
            elif self.config.strategy == LoadBalancingStrategy.RANDOM:
                endpoint = self._select_random(available)
            elif self.config.strategy == LoadBalancingStrategy.LEAST_RECENTLY_USED:
                endpoint = self._select_least_recently_used(available)
            elif self.config.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                endpoint = self._select_least_connections(available)
            else:
                endpoint = available[0]

            # Check connection limit
            if endpoint.active_connections >= self.config.max_connections_per_endpoint:
                # Try to find another endpoint with capacity
                for ep in available:
                    if ep.active_connections < self.config.max_connections_per_endpoint:
                        return ep
                # No endpoints have capacity
                return None

            return endpoint

    def _select_round_robin(self, endpoints: list[ConnectionEndpoint]) -> ConnectionEndpoint:
        """Select endpoint using round-robin strategy"""
        # Sort by priority first
        endpoints = sorted(endpoints, key=lambda e: e.priority, reverse=True)

        # Get highest priority endpoints
        max_priority = endpoints[0].priority
        high_priority_endpoints = [e for e in endpoints if e.priority == max_priority]

        # Round-robin among high priority endpoints
        index = self._round_robin_index % len(high_priority_endpoints)
        self._round_robin_index = (self._round_robin_index + 1) % len(high_priority_endpoints)

        return high_priority_endpoints[index]

    def _select_random(self, endpoints: list[ConnectionEndpoint]) -> ConnectionEndpoint:
        """Select endpoint randomly with priority weighting"""
        # Weight by priority
        weights = [ep.priority for ep in endpoints]
        return random.choices(endpoints, weights=weights)[0]

    def _select_least_recently_used(
        self, endpoints: list[ConnectionEndpoint]
    ) -> ConnectionEndpoint:
        """Select least recently used endpoint"""
        # Sort by last_used (None means never used, so prioritize those)
        return min(endpoints, key=lambda e: (e.last_used or datetime.min, -e.priority))

    def _select_least_connections(self, endpoints: list[ConnectionEndpoint]) -> ConnectionEndpoint:
        """Select endpoint with least active connections"""
        return min(endpoints, key=lambda e: (e.active_connections, -e.priority))

    async def mark_success(self, endpoint: ConnectionEndpoint) -> None:
        """
        Mark endpoint as successful

        Args:
            endpoint: Endpoint that succeeded
        """
        async with self._lock:
            endpoint.record_success()
            self.stats.total_successes += 1

    async def mark_failure(self, endpoint: ConnectionEndpoint) -> None:
        """
        Mark endpoint as failed and potentially blacklist

        Args:
            endpoint: Endpoint that failed
        """
        async with self._lock:
            endpoint.record_failure()
            self.stats.total_failures += 1

            # Check if we should blacklist
            if endpoint.failure_count >= self.config.blacklist_threshold:
                duration = timedelta(seconds=self.config.blacklist_duration)
                endpoint.blacklist(duration)

    async def add_endpoint(self, address: str, priority: int = 1) -> None:
        """
        Add new endpoint to pool

        Args:
            address: Endpoint address
            priority: Endpoint priority
        """
        async with self._lock:
            # Check if already exists
            if any(ep.address == address for ep in self.endpoints):
                return

            endpoint = ConnectionEndpoint(address=address, priority=priority)
            self.endpoints.append(endpoint)
            self.stats.total_endpoints = len(self.endpoints)

    async def remove_endpoint(self, address: str) -> None:
        """
        Remove endpoint from pool

        Args:
            address: Endpoint address to remove
        """
        async with self._lock:
            self.endpoints = [ep for ep in self.endpoints if ep.address != address]
            self.stats.total_endpoints = len(self.endpoints)

    async def blacklist_endpoint(self, address: str, duration: timedelta | None = None) -> None:
        """
        Manually blacklist an endpoint

        Args:
            address: Endpoint address to blacklist
            duration: Blacklist duration (uses config default if None)
        """
        async with self._lock:
            for endpoint in self.endpoints:
                if endpoint.address == address:
                    duration = duration or timedelta(seconds=self.config.blacklist_duration)
                    endpoint.blacklist(duration)
                    break

    async def clear_blacklist(self) -> None:
        """Clear all blacklisted endpoints"""
        async with self._lock:
            for endpoint in self.endpoints:
                endpoint.is_blacklisted = False
                endpoint.blacklist_until = None
                endpoint.failure_count = 0

    def get_stats(self) -> dict:
        """
        Get pool statistics

        Returns:
            Dictionary containing pool stats
        """
        available = self.get_available_endpoints()

        return {
            "total_endpoints": self.stats.total_endpoints,
            "available_endpoints": len(available),
            "blacklisted_endpoints": self.stats.blacklisted_endpoints,
            "total_connections": sum(ep.active_connections for ep in self.endpoints),
            "total_failures": self.stats.total_failures,
            "total_successes": self.stats.total_successes,
            "strategy": self.config.strategy.value,
            "endpoints": [
                {
                    "address": ep.address,
                    "priority": ep.priority,
                    "is_available": ep.is_available(),
                    "is_blacklisted": ep.is_blacklisted,
                    "active_connections": ep.active_connections,
                    "failure_count": ep.failure_count,
                    "success_count": ep.success_count,
                }
                for ep in self.endpoints
            ],
        }

    async def start_health_checks(self, check_func: Any) -> None:
        """
        Start periodic health checks for endpoints

        Args:
            check_func: Async function to check endpoint health
        """
        if not self.config.enable_health_checks:
            return

        async def health_check_loop():
            while True:
                try:
                    await asyncio.sleep(self.config.health_check_interval)

                    for endpoint in self.endpoints:
                        if not endpoint.is_available():
                            continue

                        try:
                            # Run health check
                            await check_func(endpoint.address)
                            # If successful and was blacklisted, clear it
                            if endpoint.is_blacklisted:
                                endpoint.is_blacklisted = False
                                endpoint.blacklist_until = None
                                endpoint.failure_count = 0
                        except Exception:
                            # Health check failed
                            await self.mark_failure(endpoint)

                except asyncio.CancelledError:
                    break
                except Exception:
                    # Log error but continue
                    pass

        self._health_check_task = asyncio.create_task(health_check_loop())

    async def stop_health_checks(self) -> None:
        """Stop health check task"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

    async def shutdown(self) -> None:
        """Shutdown connection pool"""
        await self.stop_health_checks()

        # Reset all endpoints
        for endpoint in self.endpoints:
            endpoint.active_connections = 0
            endpoint.is_active = False

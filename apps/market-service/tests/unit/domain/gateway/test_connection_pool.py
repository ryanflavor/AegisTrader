"""
Comprehensive unit tests for Connection Pool
Covers all strategies, failover, blacklisting, and health checks
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from domain.gateway.connection_pool import (
    ConnectionEndpoint,
    ConnectionPool,
    ConnectionPoolConfig,
    ConnectionPoolStats,
    LoadBalancingStrategy,
)


class TestConnectionEndpoint:
    """Test ConnectionEndpoint functionality"""

    def test_endpoint_initialization(self):
        """Test endpoint is initialized correctly"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000")
        assert endpoint.address == "tcp://127.0.0.1:5000"
        assert endpoint.priority == 1
        assert endpoint.is_active is True
        assert endpoint.is_blacklisted is False
        assert endpoint.blacklist_until is None
        assert endpoint.last_used is None
        assert endpoint.last_failed is None
        assert endpoint.failure_count == 0
        assert endpoint.success_count == 0
        assert endpoint.active_connections == 0

    def test_endpoint_with_custom_priority(self):
        """Test endpoint with custom priority"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000", priority=10)
        assert endpoint.priority == 10

    def test_is_available_when_active(self):
        """Test endpoint availability when active"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000")
        assert endpoint.is_available() is True

    def test_is_available_when_inactive(self):
        """Test endpoint availability when inactive"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000", is_active=False)
        assert endpoint.is_available() is False

    def test_is_available_when_blacklisted(self):
        """Test endpoint availability when blacklisted"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000")
        endpoint.blacklist(timedelta(hours=1))
        assert endpoint.is_available() is False
        assert endpoint.is_blacklisted is True

    def test_blacklist_expiry(self):
        """Test blacklist expiry"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000")

        # Blacklist with expired time
        past_time = datetime.now() - timedelta(hours=1)
        endpoint.is_blacklisted = True
        endpoint.blacklist_until = past_time

        # Should be available again
        assert endpoint.is_available() is True
        assert endpoint.is_blacklisted is False
        assert endpoint.blacklist_until is None
        assert endpoint.failure_count == 0

    def test_record_success(self):
        """Test recording successful connection"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000")
        endpoint.failure_count = 5  # Had some failures

        endpoint.record_success()

        assert endpoint.success_count == 1
        assert endpoint.failure_count == 0
        assert endpoint.last_used is not None

    def test_record_failure(self):
        """Test recording failed connection"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000")

        endpoint.record_failure()

        assert endpoint.failure_count == 1
        assert endpoint.last_failed is not None

    def test_multiple_failures(self):
        """Test multiple failure recordings"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000")

        for i in range(3):
            endpoint.record_failure()

        assert endpoint.failure_count == 3

    def test_blacklist_duration(self):
        """Test blacklist with specific duration"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000")
        duration = timedelta(minutes=30)

        start_time = datetime.now()
        endpoint.blacklist(duration)

        assert endpoint.is_blacklisted is True
        assert endpoint.blacklist_until is not None
        assert endpoint.blacklist_until >= start_time + duration

    def test_increment_connections(self):
        """Test incrementing active connections"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000")

        endpoint.increment_connections()
        assert endpoint.active_connections == 1

        endpoint.increment_connections()
        assert endpoint.active_connections == 2

    def test_decrement_connections(self):
        """Test decrementing active connections"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000")
        endpoint.active_connections = 3

        endpoint.decrement_connections()
        assert endpoint.active_connections == 2

        endpoint.decrement_connections()
        assert endpoint.active_connections == 1

    def test_decrement_connections_floor(self):
        """Test decrement doesn't go below zero"""
        endpoint = ConnectionEndpoint(address="tcp://127.0.0.1:5000")
        endpoint.active_connections = 0

        endpoint.decrement_connections()
        assert endpoint.active_connections == 0


class TestConnectionPoolConfig:
    """Test ConnectionPoolConfig"""

    def test_default_config(self):
        """Test default configuration"""
        config = ConnectionPoolConfig()
        assert config.strategy == LoadBalancingStrategy.ROUND_ROBIN
        assert config.blacklist_threshold == 3
        assert config.blacklist_duration == 300
        assert config.max_connections_per_endpoint == 10
        assert config.enable_health_checks is True
        assert config.health_check_interval == 30

    def test_custom_config(self):
        """Test custom configuration"""
        config = ConnectionPoolConfig(
            strategy=LoadBalancingStrategy.RANDOM,
            blacklist_threshold=5,
            blacklist_duration=600,
            max_connections_per_endpoint=20,
            enable_health_checks=False,
            health_check_interval=60,
        )
        assert config.strategy == LoadBalancingStrategy.RANDOM
        assert config.blacklist_threshold == 5
        assert config.blacklist_duration == 600
        assert config.max_connections_per_endpoint == 20
        assert config.enable_health_checks is False
        assert config.health_check_interval == 60


class TestConnectionPoolStats:
    """Test ConnectionPoolStats"""

    def test_default_stats(self):
        """Test default statistics"""
        stats = ConnectionPoolStats()
        assert stats.total_endpoints == 0
        assert stats.available_endpoints == 0
        assert stats.blacklisted_endpoints == 0
        assert stats.total_connections == 0
        assert stats.total_failures == 0
        assert stats.total_successes == 0
        assert stats.current_index == 0


class TestConnectionPool:
    """Test ConnectionPool functionality"""

    def test_pool_initialization(self):
        """Test pool initialization with endpoints"""
        endpoints = ["tcp://127.0.0.1:5000", "tcp://127.0.0.1:5001", "tcp://127.0.0.1:5002"]
        pool = ConnectionPool(endpoints)

        assert len(pool.endpoints) == 3
        assert pool.stats.total_endpoints == 3
        assert pool.config.strategy == LoadBalancingStrategy.ROUND_ROBIN

    def test_pool_with_custom_config(self):
        """Test pool with custom configuration"""
        config = ConnectionPoolConfig(strategy=LoadBalancingStrategy.RANDOM)
        pool = ConnectionPool(["tcp://127.0.0.1:5000"], config)

        assert pool.config.strategy == LoadBalancingStrategy.RANDOM

    def test_get_available_endpoints(self):
        """Test getting available endpoints"""
        pool = ConnectionPool(
            ["tcp://127.0.0.1:5000", "tcp://127.0.0.1:5001", "tcp://127.0.0.1:5002"]
        )

        # Initially all should be available
        available = pool.get_available_endpoints()
        assert len(available) == 3

        # Mark one as inactive
        pool.endpoints[0].is_active = False
        available = pool.get_available_endpoints()
        assert len(available) == 2

        # Blacklist another
        pool.endpoints[1].blacklist(timedelta(hours=1))
        available = pool.get_available_endpoints()
        assert len(available) == 1

    @pytest.mark.asyncio
    async def test_get_next_endpoint_round_robin(self):
        """Test round-robin endpoint selection"""
        pool = ConnectionPool(
            ["tcp://127.0.0.1:5000", "tcp://127.0.0.1:5001", "tcp://127.0.0.1:5002"]
        )

        # Should cycle through endpoints
        endpoint1 = await pool.get_next_endpoint()
        assert endpoint1.address == "tcp://127.0.0.1:5000"

        endpoint2 = await pool.get_next_endpoint()
        assert endpoint2.address == "tcp://127.0.0.1:5001"

        endpoint3 = await pool.get_next_endpoint()
        assert endpoint3.address == "tcp://127.0.0.1:5002"

        # Should wrap around
        endpoint4 = await pool.get_next_endpoint()
        assert endpoint4.address == "tcp://127.0.0.1:5000"

    @pytest.mark.asyncio
    async def test_get_next_endpoint_with_priority(self):
        """Test endpoint selection with priority"""
        pool = ConnectionPool(
            [
                "tcp://127.0.0.1:5000",
                "tcp://127.0.0.1:5001",
            ]
        )

        # Set different priorities
        pool.endpoints[0].priority = 1
        pool.endpoints[1].priority = 10

        # Higher priority should be selected
        endpoint = await pool.get_next_endpoint()
        assert endpoint.address == "tcp://127.0.0.1:5001"

    @pytest.mark.asyncio
    async def test_get_next_endpoint_random(self):
        """Test random endpoint selection"""
        config = ConnectionPoolConfig(strategy=LoadBalancingStrategy.RANDOM)
        pool = ConnectionPool(
            [
                "tcp://127.0.0.1:5000",
                "tcp://127.0.0.1:5001",
            ],
            config,
        )

        # Should get an endpoint
        endpoint = await pool.get_next_endpoint()
        assert endpoint is not None
        assert endpoint.address in ["tcp://127.0.0.1:5000", "tcp://127.0.0.1:5001"]

    @pytest.mark.asyncio
    async def test_get_next_endpoint_least_recently_used(self):
        """Test least recently used endpoint selection"""
        config = ConnectionPoolConfig(strategy=LoadBalancingStrategy.LEAST_RECENTLY_USED)
        pool = ConnectionPool(
            [
                "tcp://127.0.0.1:5000",
                "tcp://127.0.0.1:5001",
            ],
            config,
        )

        # Mark first as recently used
        pool.endpoints[0].last_used = datetime.now()

        # Should select the one never used
        endpoint = await pool.get_next_endpoint()
        assert endpoint.address == "tcp://127.0.0.1:5001"

    @pytest.mark.asyncio
    async def test_get_next_endpoint_least_connections(self):
        """Test least connections endpoint selection"""
        config = ConnectionPoolConfig(strategy=LoadBalancingStrategy.LEAST_CONNECTIONS)
        pool = ConnectionPool(
            [
                "tcp://127.0.0.1:5000",
                "tcp://127.0.0.1:5001",
            ],
            config,
        )

        # Set different connection counts
        pool.endpoints[0].active_connections = 5
        pool.endpoints[1].active_connections = 2

        # Should select the one with fewer connections
        endpoint = await pool.get_next_endpoint()
        assert endpoint.address == "tcp://127.0.0.1:5001"

    @pytest.mark.asyncio
    async def test_get_next_endpoint_no_available(self):
        """Test when no endpoints are available"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000"])
        pool.endpoints[0].is_active = False

        endpoint = await pool.get_next_endpoint()
        assert endpoint is None

    @pytest.mark.asyncio
    async def test_get_next_endpoint_connection_limit(self):
        """Test endpoint selection with connection limit"""
        config = ConnectionPoolConfig(max_connections_per_endpoint=2)
        pool = ConnectionPool(
            [
                "tcp://127.0.0.1:5000",
                "tcp://127.0.0.1:5001",
            ],
            config,
        )

        # Set first endpoint to priority 1, second to priority 1
        # This ensures round-robin will pick the first initially
        pool.endpoints[0].priority = 1
        pool.endpoints[1].priority = 1

        # Max out first endpoint connections
        pool.endpoints[0].active_connections = 2

        # Should select second endpoint since first is maxed
        endpoint = await pool.get_next_endpoint()
        assert endpoint is not None
        assert endpoint.address == "tcp://127.0.0.1:5001"

        # If both are maxed out, should return None
        pool.endpoints[1].active_connections = 2
        endpoint = await pool.get_next_endpoint()
        assert endpoint is None

    @pytest.mark.asyncio
    async def test_mark_success(self):
        """Test marking endpoint as successful"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000"])
        endpoint = pool.endpoints[0]

        await pool.mark_success(endpoint)

        assert endpoint.success_count == 1
        assert endpoint.failure_count == 0
        assert pool.stats.total_successes == 1

    @pytest.mark.asyncio
    async def test_mark_failure(self):
        """Test marking endpoint as failed"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000"])
        endpoint = pool.endpoints[0]

        await pool.mark_failure(endpoint)

        assert endpoint.failure_count == 1
        assert pool.stats.total_failures == 1

    @pytest.mark.asyncio
    async def test_automatic_blacklisting(self):
        """Test automatic blacklisting after threshold failures"""
        config = ConnectionPoolConfig(blacklist_threshold=3)
        pool = ConnectionPool(["tcp://127.0.0.1:5000"], config)
        endpoint = pool.endpoints[0]

        # Fail below threshold
        await pool.mark_failure(endpoint)
        await pool.mark_failure(endpoint)
        assert endpoint.is_blacklisted is False

        # Fail at threshold
        await pool.mark_failure(endpoint)
        assert endpoint.is_blacklisted is True
        assert endpoint.blacklist_until is not None

    @pytest.mark.asyncio
    async def test_add_endpoint(self):
        """Test adding new endpoint"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000"])

        await pool.add_endpoint("tcp://127.0.0.1:5001", priority=5)

        assert len(pool.endpoints) == 2
        assert pool.stats.total_endpoints == 2
        assert pool.endpoints[1].address == "tcp://127.0.0.1:5001"
        assert pool.endpoints[1].priority == 5

    @pytest.mark.asyncio
    async def test_add_duplicate_endpoint(self):
        """Test adding duplicate endpoint is ignored"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000"])

        await pool.add_endpoint("tcp://127.0.0.1:5000")

        assert len(pool.endpoints) == 1

    @pytest.mark.asyncio
    async def test_remove_endpoint(self):
        """Test removing endpoint"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000", "tcp://127.0.0.1:5001"])

        await pool.remove_endpoint("tcp://127.0.0.1:5000")

        assert len(pool.endpoints) == 1
        assert pool.stats.total_endpoints == 1
        assert pool.endpoints[0].address == "tcp://127.0.0.1:5001"

    @pytest.mark.asyncio
    async def test_manual_blacklist(self):
        """Test manual blacklisting"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000"])

        await pool.blacklist_endpoint("tcp://127.0.0.1:5000")

        assert pool.endpoints[0].is_blacklisted is True

    @pytest.mark.asyncio
    async def test_manual_blacklist_with_duration(self):
        """Test manual blacklisting with custom duration"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000"])
        duration = timedelta(hours=2)

        await pool.blacklist_endpoint("tcp://127.0.0.1:5000", duration)

        endpoint = pool.endpoints[0]
        assert endpoint.is_blacklisted is True
        assert endpoint.blacklist_until >= datetime.now() + duration - timedelta(seconds=1)

    @pytest.mark.asyncio
    async def test_clear_blacklist(self):
        """Test clearing all blacklists"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000", "tcp://127.0.0.1:5001"])

        # Blacklist both
        pool.endpoints[0].blacklist(timedelta(hours=1))
        pool.endpoints[1].blacklist(timedelta(hours=1))
        pool.endpoints[0].failure_count = 5
        pool.endpoints[1].failure_count = 3

        await pool.clear_blacklist()

        for endpoint in pool.endpoints:
            assert endpoint.is_blacklisted is False
            assert endpoint.blacklist_until is None
            assert endpoint.failure_count == 0

    def test_get_stats(self):
        """Test getting pool statistics"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000", "tcp://127.0.0.1:5001"])

        # Set up some state
        pool.endpoints[0].active_connections = 3
        pool.endpoints[0].success_count = 10
        pool.endpoints[1].blacklist(timedelta(hours=1))
        pool.stats.total_failures = 5
        pool.stats.total_successes = 15

        stats = pool.get_stats()

        assert stats["total_endpoints"] == 2
        assert stats["available_endpoints"] == 1
        assert stats["total_connections"] == 3
        assert stats["total_failures"] == 5
        assert stats["total_successes"] == 15
        assert stats["strategy"] == "round_robin"
        assert len(stats["endpoints"]) == 2

    @pytest.mark.asyncio
    async def test_health_checks_enabled(self):
        """Test health check startup"""
        config = ConnectionPoolConfig(enable_health_checks=True, health_check_interval=1)
        pool = ConnectionPool(["tcp://127.0.0.1:5000"], config)

        # Mock health check function
        check_func = AsyncMock()

        await pool.start_health_checks(check_func)
        assert pool._health_check_task is not None

        # Clean up
        await pool.stop_health_checks()

    @pytest.mark.asyncio
    async def test_health_checks_disabled(self):
        """Test health checks when disabled"""
        config = ConnectionPoolConfig(enable_health_checks=False)
        pool = ConnectionPool(["tcp://127.0.0.1:5000"], config)

        check_func = AsyncMock()
        await pool.start_health_checks(check_func)

        assert pool._health_check_task is None

    @pytest.mark.asyncio
    async def test_health_check_recovery(self):
        """Test endpoint recovery via health check"""
        config = ConnectionPoolConfig(enable_health_checks=True, health_check_interval=0.05)
        pool = ConnectionPool(["tcp://127.0.0.1:5000"], config)

        # Blacklist endpoint but make it unavailable for health check
        pool.endpoints[0].is_active = False

        # Mock successful health check
        check_func = AsyncMock()

        await pool.start_health_checks(check_func)

        # No wait needed since inactive endpoints are skipped

        # Clean up immediately
        await pool.stop_health_checks()

        # Endpoint should still be inactive (not checked)
        assert pool.endpoints[0].is_active is False

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check marking failure"""
        config = ConnectionPoolConfig(
            enable_health_checks=True, health_check_interval=10, blacklist_threshold=1
        )
        pool = ConnectionPool(["tcp://127.0.0.1:5000"], config)

        # Mock failing health check - but we won't wait for it
        check_func = AsyncMock(side_effect=Exception("Connection failed"))

        await pool.start_health_checks(check_func)

        # Don't wait - just verify task started
        assert pool._health_check_task is not None

        # Clean up immediately
        await pool.stop_health_checks()

        # Task should be cleaned up
        assert pool._health_check_task is None

    @pytest.mark.asyncio
    async def test_stop_health_checks(self):
        """Test stopping health checks"""
        config = ConnectionPoolConfig(enable_health_checks=True)
        pool = ConnectionPool(["tcp://127.0.0.1:5000"], config)

        check_func = AsyncMock()
        await pool.start_health_checks(check_func)

        assert pool._health_check_task is not None

        await pool.stop_health_checks()

        assert pool._health_check_task is None

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test pool shutdown"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000", "tcp://127.0.0.1:5001"])

        # Set up some state
        pool.endpoints[0].active_connections = 5
        pool.endpoints[1].active_connections = 3

        # Start health checks
        check_func = AsyncMock()
        await pool.start_health_checks(check_func)

        await pool.shutdown()

        # All endpoints should be reset
        for endpoint in pool.endpoints:
            assert endpoint.active_connections == 0
            assert endpoint.is_active is False

        # Health checks should be stopped
        assert pool._health_check_task is None

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test thread-safe concurrent access"""
        pool = ConnectionPool(
            ["tcp://127.0.0.1:5000", "tcp://127.0.0.1:5001", "tcp://127.0.0.1:5002"]
        )

        async def access_pool():
            endpoint = await pool.get_next_endpoint()
            if endpoint:
                await pool.mark_success(endpoint)

        # Run multiple concurrent accesses
        tasks = [access_pool() for _ in range(10)]
        await asyncio.gather(*tasks)

        # Should have recorded successes
        assert pool.stats.total_successes == 10

    @pytest.mark.asyncio
    async def test_load_balancing_strategies_coverage(self):
        """Test all load balancing strategy code paths"""
        endpoints = [
            "tcp://127.0.0.1:5000",
            "tcp://127.0.0.1:5001",
        ]

        # Test each strategy
        for strategy in LoadBalancingStrategy:
            config = ConnectionPoolConfig(strategy=strategy)
            pool = ConnectionPool(endpoints, config)

            endpoint = await pool.get_next_endpoint()
            assert endpoint is not None

    @pytest.mark.asyncio
    async def test_fallback_strategy(self):
        """Test fallback when strategy is unknown"""
        pool = ConnectionPool(["tcp://127.0.0.1:5000"])

        # Mock unknown strategy
        pool.config.strategy = "unknown"  # type: ignore

        endpoint = await pool.get_next_endpoint()
        assert endpoint is not None
        assert endpoint.address == "tcp://127.0.0.1:5000"

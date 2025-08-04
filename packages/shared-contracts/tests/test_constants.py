"""Tests for shared constants."""

from __future__ import annotations

from shared_contracts.constants import (
    EventPatterns,
    KVBuckets,
    RPCPatterns,
    ServiceDefaults,
    ServiceNames,
)


def test_service_names() -> None:
    """Test service name constants."""
    assert ServiceNames.ORDER_SERVICE == "order-service"
    assert ServiceNames.PRICING_SERVICE == "pricing-service"
    assert ServiceNames.RISK_SERVICE == "risk-service"
    assert ServiceNames.MONITOR_API == "monitor-api"
    assert ServiceNames.MONITOR_UI == "monitor-ui"


def test_event_patterns() -> None:
    """Test event pattern constants."""
    # Base pattern
    assert EventPatterns.EVENT_BASE == "events"

    # Order events
    assert EventPatterns.ORDER_CREATED == "events.order.created"
    assert EventPatterns.ORDER_UPDATED == "events.order.updated"
    assert EventPatterns.ORDER_FILLED == "events.order.filled"
    assert EventPatterns.ORDER_CANCELLED == "events.order.cancelled"

    # Price events
    assert EventPatterns.PRICE_UPDATED == "events.price.updated"
    assert EventPatterns.PRICE_QUOTED == "events.price.quoted"

    # Risk events
    assert EventPatterns.RISK_ASSESSED == "events.risk.assessed"

    # Position events
    assert EventPatterns.POSITION_UPDATED == "events.position.updated"

    # Subscription patterns
    assert EventPatterns.ALL_EVENTS == "events.>"
    assert EventPatterns.ORDER_EVENTS == "events.order.*"
    assert EventPatterns.PRICE_EVENTS == "events.price.*"
    assert EventPatterns.RISK_EVENTS == "events.risk.*"


def test_kv_buckets() -> None:
    """Test KV bucket name constants."""
    assert KVBuckets.SERVICE_DEFINITIONS == "service-definitions"
    assert KVBuckets.SERVICE_INSTANCES == "service-instances"
    assert KVBuckets.CONFIGURATION == "configuration"


def test_rpc_patterns() -> None:
    """Test RPC pattern constants."""
    # Health and diagnostics
    assert RPCPatterns.ECHO == "echo"
    assert RPCPatterns.HEALTH == "health"
    assert RPCPatterns.METRICS == "metrics"

    # Common operations
    assert RPCPatterns.CREATE == "create"
    assert RPCPatterns.GET == "get"
    assert RPCPatterns.LIST == "list"
    assert RPCPatterns.UPDATE == "update"
    assert RPCPatterns.DELETE == "delete"

    # Simulation
    assert RPCPatterns.SIMULATE_WORK == "simulate_work"


def test_service_defaults() -> None:
    """Test service default values."""
    # Timeouts
    assert ServiceDefaults.HEARTBEAT_INTERVAL == 30
    assert ServiceDefaults.HEALTH_CHECK_INTERVAL == 10
    assert ServiceDefaults.RPC_TIMEOUT == 5000

    # Retry settings
    assert ServiceDefaults.MAX_RETRIES == 3
    assert ServiceDefaults.RETRY_BACKOFF == 1000

    # Cache settings
    assert ServiceDefaults.CACHE_TTL == 60
    assert ServiceDefaults.DISCOVERY_CACHE_TTL == 30

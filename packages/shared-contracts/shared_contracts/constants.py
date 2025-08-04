"""Shared constants for AegisTrader services.

This module defines technical constants used across services,
NOT business domain models.
"""

from __future__ import annotations


class ServiceNames:
    """Standard service names used in the system."""

    ORDER_SERVICE = "order-service"
    PRICING_SERVICE = "pricing-service"
    RISK_SERVICE = "risk-service"
    MONITOR_API = "monitor-api"
    MONITOR_UI = "monitor-ui"


class EventPatterns:
    """Standard event patterns following AegisSDK conventions."""

    # Base pattern for all events
    EVENT_BASE = "events"

    # Order events
    ORDER_CREATED = f"{EVENT_BASE}.order.created"
    ORDER_UPDATED = f"{EVENT_BASE}.order.updated"
    ORDER_FILLED = f"{EVENT_BASE}.order.filled"
    ORDER_CANCELLED = f"{EVENT_BASE}.order.cancelled"

    # Price events
    PRICE_UPDATED = f"{EVENT_BASE}.price.updated"
    PRICE_QUOTED = f"{EVENT_BASE}.price.quoted"

    # Risk events
    RISK_ASSESSED = f"{EVENT_BASE}.risk.assessed"

    # Position events
    POSITION_UPDATED = f"{EVENT_BASE}.position.updated"

    # Subscription patterns
    ALL_EVENTS = f"{EVENT_BASE}.>"
    ORDER_EVENTS = f"{EVENT_BASE}.order.*"
    PRICE_EVENTS = f"{EVENT_BASE}.price.*"
    RISK_EVENTS = f"{EVENT_BASE}.risk.*"


class KVBuckets:
    """Standard KV bucket names."""

    SERVICE_DEFINITIONS = "service-definitions"
    SERVICE_INSTANCES = "service-instances"
    CONFIGURATION = "configuration"


class RPCPatterns:
    """Standard RPC method patterns."""

    # Health and diagnostics
    ECHO = "echo"
    HEALTH = "health"
    METRICS = "metrics"

    # Common operations
    CREATE = "create"
    GET = "get"
    LIST = "list"
    UPDATE = "update"
    DELETE = "delete"

    # Simulation
    SIMULATE_WORK = "simulate_work"


class ServiceDefaults:
    """Default configuration values."""

    # Timeouts
    HEARTBEAT_INTERVAL = 30  # seconds
    HEALTH_CHECK_INTERVAL = 10  # seconds
    RPC_TIMEOUT = 5000  # milliseconds

    # Retry settings
    MAX_RETRIES = 3
    RETRY_BACKOFF = 1000  # milliseconds

    # Cache settings
    CACHE_TTL = 60  # seconds
    DISCOVERY_CACHE_TTL = 30  # seconds

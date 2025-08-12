"""
Market Data Domain Module.

This module contains the core domain logic for market data management,
including entities, value objects, aggregates, and events.
"""

from .aggregates import MarketDataGateway
from .entities import MarketDataSession, MarketDataSubscription
from .events import (
    AnomalyDetected,
    DataQualityIssue,
    DomainEvent,
    GatewayConnected,
    GatewayDisconnected,
    HeartbeatReceived,
    MarketDataSubscribed,
    MarketDataUnsubscribed,
    MarketSessionEnded,
    MarketSessionStarted,
    SubscriptionLimitReached,
    TickProcessed,
    TickReceived,
    TickValidationFailed,
)
from .value_objects import (
    InstrumentType,
    MarketDepth,
    OrderSide,
    OrderType,
    Price,
    Symbol,
    Tick,
    TimeRange,
    Volume,
)

__all__ = [
    # Aggregates
    "MarketDataGateway",
    # Entities
    "MarketDataSession",
    "MarketDataSubscription",
    # Events
    "AnomalyDetected",
    "DataQualityIssue",
    "DomainEvent",
    "GatewayConnected",
    "GatewayDisconnected",
    "HeartbeatReceived",
    "MarketDataSubscribed",
    "MarketDataUnsubscribed",
    "MarketSessionEnded",
    "MarketSessionStarted",
    "SubscriptionLimitReached",
    "TickProcessed",
    "TickReceived",
    "TickValidationFailed",
    # Value Objects
    "InstrumentType",
    "MarketDepth",
    "OrderSide",
    "OrderType",
    "Price",
    "Symbol",
    "Tick",
    "TimeRange",
    "Volume",
]

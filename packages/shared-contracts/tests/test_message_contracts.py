"""Tests for message contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shared_contracts.message_contracts import (
    BaseEventContract,
    RPCRequestContract,
    RPCResponseContract,
    ServiceHealthContract,
    ServiceMetricsContract,
)


def test_base_event_contract() -> None:
    """Test BaseEventContract creation."""
    event = BaseEventContract(
        event_id="evt-123",
        event_type="events.order.created",
        timestamp=datetime.now(UTC),
        source_service="order-service",
        source_instance="order-service-abc123",
        payload={
            "order_id": "ORD-001",
            "symbol": "AAPL",
            "quantity": 100,
        },
    )

    assert event.event_id == "evt-123"
    assert event.event_type == "events.order.created"
    assert event.source_service == "order-service"
    assert event.source_instance == "order-service-abc123"
    assert event.version == "1.0"  # Default
    assert event.payload["order_id"] == "ORD-001"
    assert event.metadata == {}  # Default empty


def test_event_with_metadata() -> None:
    """Test event with metadata."""
    event = BaseEventContract(
        event_id="evt-456",
        event_type="events.price.updated",
        timestamp=datetime.now(UTC),
        source_service="pricing-service",
        source_instance="pricing-service-xyz789",
        version="2.0",
        metadata={
            "correlation_id": "corr-123",
            "user_id": "user-456",
            "trace_id": "trace-789",
        },
        payload={
            "symbol": "BTC",
            "price": 45000.00,
        },
    )

    assert event.version == "2.0"
    assert event.metadata["correlation_id"] == "corr-123"
    assert event.metadata["user_id"] == "user-456"


def test_rpc_request_contract() -> None:
    """Test RPCRequestContract."""
    request = RPCRequestContract(
        method="create_order",
        params={
            "symbol": "AAPL",
            "quantity": 100,
            "side": "BUY",
        },
        timeout=5000,
    )

    assert request.method == "create_order"
    assert request.params["symbol"] == "AAPL"
    assert request.timeout == 5000
    assert request.metadata == {}


def test_rpc_response_contract_success() -> None:
    """Test successful RPC response."""
    response = RPCResponseContract(
        result={
            "order_id": "ORD-001",
            "status": "created",
        },
        metadata={"duration_ms": 125},
    )

    assert response.result is not None
    assert response.result["order_id"] == "ORD-001"
    assert response.error is None
    assert response.metadata["duration_ms"] == 125


def test_rpc_response_contract_error() -> None:
    """Test error RPC response."""
    response = RPCResponseContract(
        error={
            "code": "INSUFFICIENT_FUNDS",
            "message": "Not enough balance to place order",
            "details": {"available": 1000, "required": 5000},
        },
    )

    assert response.result is None
    assert response.error is not None
    assert response.error["code"] == "INSUFFICIENT_FUNDS"


def test_service_health_contract() -> None:
    """Test ServiceHealthContract."""
    health = ServiceHealthContract(
        status="healthy",
        service="order-service",
        instance="order-service-abc123",
        version="1.0.0",
        uptime=3600.5,
        checks={
            "database": True,
            "nats": True,
            "disk_space": True,
        },
        metrics={
            "orders_processed": 1500,
            "active_connections": 25,
        },
    )

    assert health.status == "healthy"
    assert health.service == "order-service"
    assert health.uptime == 3600.5
    assert health.checks["database"] is True
    assert health.metrics["orders_processed"] == 1500


def test_service_metrics_contract() -> None:
    """Test ServiceMetricsContract."""
    metrics = ServiceMetricsContract(
        service="pricing-service",
        instance="pricing-service-xyz789",
        timestamp=datetime.now(UTC),
        counters={
            "requests_total": 10000,
            "errors_total": 15,
        },
        gauges={
            "active_connections": 42,
            "memory_usage_mb": 256.5,
        },
        histograms={
            "request_duration_ms": {
                "p50": 10.5,
                "p95": 45.2,
                "p99": 125.8,
                "mean": 15.3,
            },
        },
    )

    assert metrics.service == "pricing-service"
    assert metrics.counters["requests_total"] == 10000
    assert metrics.gauges["memory_usage_mb"] == 256.5
    assert metrics.histograms["request_duration_ms"]["p99"] == 125.8


def test_event_validation() -> None:
    """Test event validation."""
    with pytest.raises(ValidationError) as exc_info:
        BaseEventContract(
            event_id="evt-789",
            # Missing: event_type, timestamp, source_service, source_instance
            payload={"test": "data"},
        )

    assert "event_type" in str(exc_info.value)
    assert "timestamp" in str(exc_info.value)

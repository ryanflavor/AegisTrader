"""Tests for utility functions."""

from __future__ import annotations

import pytest

from shared_contracts.utils import parse_event_pattern


def test_parse_event_pattern_order_created() -> None:
    """Test parsing order created event pattern."""
    domain, event_type = parse_event_pattern("events.order.created")
    assert domain == "order"
    assert event_type == "created"


def test_parse_event_pattern_risk_assessed() -> None:
    """Test parsing risk assessed event pattern."""
    domain, event_type = parse_event_pattern("events.risk.assessed")
    assert domain == "risk"
    assert event_type == "assessed"


def test_parse_event_pattern_price_updated() -> None:
    """Test parsing price updated event pattern."""
    domain, event_type = parse_event_pattern("events.price.updated")
    assert domain == "price"
    assert event_type == "updated"


def test_parse_event_pattern_complex_event_type() -> None:
    """Test parsing pattern with complex event type."""
    domain, event_type = parse_event_pattern("events.order.partially.filled")
    assert domain == "order"
    assert event_type == "partially.filled"


def test_parse_event_pattern_invalid_format() -> None:
    """Test parsing invalid event pattern."""
    with pytest.raises(ValueError) as exc_info:
        parse_event_pattern("order.created")  # Missing 'events' prefix

    assert "Invalid event pattern" in str(exc_info.value)
    assert "Expected format: events.{domain}.{type}" in str(exc_info.value)


def test_parse_event_pattern_too_short() -> None:
    """Test parsing pattern that's too short."""
    with pytest.raises(ValueError) as exc_info:
        parse_event_pattern("events.order")  # Missing event type

    assert "Invalid event pattern" in str(exc_info.value)

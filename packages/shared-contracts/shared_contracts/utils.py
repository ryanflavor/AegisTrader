"""Utility functions for shared contracts."""

from __future__ import annotations


def parse_event_pattern(pattern: str) -> tuple[str, str]:
    """Parse event pattern into domain and event_type.

    Args:
        pattern: Event pattern like "events.order.created"

    Returns:
        Tuple of (domain, event_type)

    Example:
        >>> parse_event_pattern("events.order.created")
        ("order", "created")
        >>> parse_event_pattern("events.risk.assessed")
        ("risk", "assessed")
    """
    parts = pattern.split(".")
    if len(parts) < 3 or parts[0] != "events":
        raise ValueError(
            f"Invalid event pattern: {pattern}. Expected format: events.{{domain}}.{{type}}"
        )

    domain = parts[1]
    event_type = ".".join(parts[2:])
    return domain, event_type

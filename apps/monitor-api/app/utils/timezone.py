"""Timezone utilities for UTC+8 standardization.

This module provides consistent UTC+8 timezone handling across the application.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

# Define UTC+8 timezone (Singapore/Hong Kong/China time)
UTC_PLUS_8 = timezone(timedelta(hours=8))


def now_utc8() -> datetime:
    """Get current time in UTC+8 timezone.

    Returns:
        datetime: Current datetime in UTC+8 timezone
    """
    return datetime.now(UTC_PLUS_8)


def now_utc8_iso() -> str:
    """Get current time in UTC+8 as ISO string.

    Returns:
        str: Current datetime in UTC+8 as ISO format string
    """
    return now_utc8().isoformat()


def utc8_timestamp_factory() -> datetime:
    """Factory function for Pydantic default_factory.

    Returns:
        datetime: Current datetime in UTC+8 timezone
    """
    return now_utc8()


def convert_to_utc8(dt: datetime) -> datetime:
    """Convert any datetime to UTC+8 timezone.

    Args:
        dt: Datetime to convert

    Returns:
        datetime: Datetime converted to UTC+8 timezone
    """
    if dt.tzinfo is None:
        # Assume naive datetime is in UTC
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC_PLUS_8)


def parse_iso_to_utc8(iso_string: str) -> datetime:
    """Parse ISO datetime string and convert to UTC+8.

    Args:
        iso_string: ISO format datetime string

    Returns:
        datetime: Parsed datetime in UTC+8 timezone
    """
    dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    return convert_to_utc8(dt)

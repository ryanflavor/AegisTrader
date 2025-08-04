"""Tests for timezone utilities."""

from datetime import UTC, datetime, timedelta, timezone

from app.utils.timezone import (
    UTC_PLUS_8,
    convert_to_utc8,
    now_utc8,
    now_utc8_iso,
    parse_iso_to_utc8,
    utc8_timestamp_factory,
)


class TestTimezoneUtilities:
    """Test cases for timezone utility functions."""

    def test_utc_plus_8_constant(self) -> None:
        """Test UTC+8 timezone constant is correct."""
        assert UTC_PLUS_8 == timezone(timedelta(hours=8))
        assert UTC_PLUS_8.utcoffset(None) == timedelta(hours=8)

    def test_now_utc8(self) -> None:
        """Test now_utc8 returns datetime in UTC+8."""
        result = now_utc8()
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC_PLUS_8
        # Check it's recent (within last minute)
        now = datetime.now(UTC_PLUS_8)
        assert abs((now - result).total_seconds()) < 60

    def test_now_utc8_iso(self) -> None:
        """Test now_utc8_iso returns ISO format string."""
        result = now_utc8_iso()
        assert isinstance(result, str)
        # Should contain timezone offset
        assert "+08:00" in result
        # Should be parseable
        parsed = datetime.fromisoformat(result)
        assert parsed.tzinfo is not None

    def test_utc8_timestamp_factory(self) -> None:
        """Test utc8_timestamp_factory for Pydantic."""
        result = utc8_timestamp_factory()
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC_PLUS_8

    def test_convert_to_utc8_with_timezone(self) -> None:
        """Test converting datetime with timezone to UTC+8."""
        # Test with UTC datetime
        utc_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        result = convert_to_utc8(utc_dt)
        assert result.tzinfo == UTC_PLUS_8
        # UTC midnight should be 8am UTC+8
        assert result.hour == 8
        assert result.day == 1

        # Test with other timezone
        pst = timezone(timedelta(hours=-8))
        pst_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=pst)
        result = convert_to_utc8(pst_dt)
        assert result.tzinfo == UTC_PLUS_8
        # PST midnight should be 4pm UTC+8
        assert result.hour == 16

    def test_convert_to_utc8_naive_datetime(self) -> None:
        """Test converting naive datetime to UTC+8."""
        # Naive datetime should be assumed as UTC
        naive_dt = datetime(2024, 1, 1, 0, 0, 0)
        result = convert_to_utc8(naive_dt)
        assert result.tzinfo == UTC_PLUS_8
        # UTC midnight should be 8am UTC+8
        assert result.hour == 8

    def test_parse_iso_to_utc8_with_z_suffix(self) -> None:
        """Test parsing ISO string with Z suffix."""
        iso_string = "2024-01-01T00:00:00Z"
        result = parse_iso_to_utc8(iso_string)
        assert result.tzinfo == UTC_PLUS_8
        assert result.hour == 8  # UTC midnight = 8am UTC+8

    def test_parse_iso_to_utc8_with_offset(self) -> None:
        """Test parsing ISO string with timezone offset."""
        iso_string = "2024-01-01T00:00:00+00:00"
        result = parse_iso_to_utc8(iso_string)
        assert result.tzinfo == UTC_PLUS_8
        assert result.hour == 8

        # Test with UTC+8 input
        iso_string = "2024-01-01T08:00:00+08:00"
        result = parse_iso_to_utc8(iso_string)
        assert result.tzinfo == UTC_PLUS_8
        assert result.hour == 8  # Should remain 8am

    def test_parse_iso_to_utc8_with_microseconds(self) -> None:
        """Test parsing ISO string with microseconds."""
        iso_string = "2024-01-01T00:00:00.123456Z"
        result = parse_iso_to_utc8(iso_string)
        assert result.tzinfo == UTC_PLUS_8
        assert result.microsecond == 123456

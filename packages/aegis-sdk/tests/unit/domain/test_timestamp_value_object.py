"""Tests for the Timestamp value object."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from aegis_sdk.domain.value_objects import Timestamp


class TestTimestamp:
    """Test the Timestamp value object."""

    def test_create_timestamp_from_datetime(self):
        """Test creating timestamp from datetime."""
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        timestamp = Timestamp(value=dt)
        assert timestamp.value == dt
        assert timestamp.value.tzinfo == UTC

    def test_create_timestamp_now(self):
        """Test creating timestamp with current time."""
        before = datetime.now(UTC)
        timestamp = Timestamp.now()
        after = datetime.now(UTC)

        assert before <= timestamp.value <= after
        assert timestamp.value.tzinfo == UTC

    def test_timestamp_requires_timezone(self):
        """Test that timestamp requires timezone-aware datetime."""
        # Naive datetime should raise error
        naive_dt = datetime(2024, 1, 15, 10, 30, 45)
        with pytest.raises(ValueError, match="Timestamp must be timezone-aware"):
            Timestamp(value=naive_dt)

    def test_timestamp_from_iso_string(self):
        """Test creating timestamp from ISO string."""
        # UTC with Z suffix
        ts1 = Timestamp.from_iso_string("2024-01-15T10:30:45Z")
        assert ts1.value == datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)

        # UTC with +00:00
        ts2 = Timestamp.from_iso_string("2024-01-15T10:30:45+00:00")
        assert ts2.value == datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)

        # With timezone offset
        ts3 = Timestamp.from_iso_string("2024-01-15T10:30:45+05:00")
        expected_tz = timezone(timedelta(hours=5))
        expected_dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=expected_tz)
        assert ts3.value == expected_dt

    def test_timestamp_to_iso_string(self):
        """Test converting timestamp to ISO string."""
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        timestamp = Timestamp(value=dt)

        # Default format
        assert timestamp.to_iso_string() == "2024-01-15T10:30:45+00:00"

        # With Z suffix
        assert timestamp.to_iso_string(use_z_suffix=True) == "2024-01-15T10:30:45Z"

    def test_timestamp_from_unix(self):
        """Test creating timestamp from Unix timestamp."""
        # Known Unix timestamp: 1705314645 = 2024-01-15 10:30:45 UTC
        timestamp = Timestamp.from_unix(1705314645)
        expected = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        assert timestamp.value == expected

    def test_timestamp_to_unix(self):
        """Test converting timestamp to Unix timestamp."""
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        timestamp = Timestamp(value=dt)
        assert timestamp.to_unix() == 1705314645

    def test_timestamp_comparison(self):
        """Test timestamp comparison operations."""
        t1 = Timestamp(value=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))
        t2 = Timestamp(value=datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC))
        t3 = Timestamp(value=datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC))

        # Less than
        assert t1 < t2
        assert not t2 < t1

        # Greater than
        assert t2 > t1
        assert not t1 > t2

        # Equal
        assert t2 == t3
        assert t1 != t2

        # Less than or equal
        assert t1 <= t2
        assert t2 <= t3

        # Greater than or equal
        assert t2 >= t1
        assert t2 >= t3

    def test_timestamp_add_duration(self):
        """Test adding duration to timestamp."""
        from aegis_sdk.domain.value_objects import Duration

        ts = Timestamp(value=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))
        duration = Duration(seconds=3600)  # 1 hour

        new_ts = ts.add(duration)
        expected = datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC)
        assert new_ts.value == expected
        assert ts.value == datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)  # Original unchanged

    def test_timestamp_subtract_duration(self):
        """Test subtracting duration from timestamp."""
        from aegis_sdk.domain.value_objects import Duration

        ts = Timestamp(value=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))
        duration = Duration(seconds=1800)  # 30 minutes

        new_ts = ts.subtract(duration)
        expected = datetime(2024, 1, 15, 9, 30, 0, tzinfo=UTC)
        assert new_ts.value == expected

    def test_timestamp_diff(self):
        """Test calculating duration between timestamps."""
        from aegis_sdk.domain.value_objects import Duration

        t1 = Timestamp(value=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))
        t2 = Timestamp(value=datetime(2024, 1, 15, 11, 30, 0, tzinfo=UTC))

        duration = t2.diff(t1)
        assert isinstance(duration, Duration)
        assert duration.seconds == 5400  # 1.5 hours

    def test_timestamp_is_before_after(self):
        """Test is_before and is_after methods."""
        t1 = Timestamp(value=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC))
        t2 = Timestamp(value=datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC))

        assert t1.is_before(t2)
        assert not t2.is_before(t1)
        assert not t1.is_before(t1)

        assert t2.is_after(t1)
        assert not t1.is_after(t2)
        assert not t1.is_after(t1)

    def test_timestamp_immutability(self):
        """Test that Timestamp is immutable."""
        from pydantic import ValidationError

        timestamp = Timestamp.now()
        with pytest.raises(ValidationError, match="frozen"):
            timestamp.value = datetime.now(UTC)

    def test_timestamp_hash(self):
        """Test that Timestamp is hashable."""
        dt = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        t1 = Timestamp(value=dt)
        t2 = Timestamp(value=dt)
        t3 = Timestamp(value=datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC))

        # Same timestamps have same hash
        assert hash(t1) == hash(t2)

        # Can be used in sets
        timestamp_set = {t1, t2, t3}
        assert len(timestamp_set) == 2  # t1 and t2 are the same

    def test_timestamp_string_representation(self):
        """Test string representation of timestamp."""
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        timestamp = Timestamp(value=dt)
        assert str(timestamp) == "2024-01-15T10:30:45+00:00"

    def test_timestamp_to_utc(self):
        """Test converting timestamp to UTC."""
        # Create timestamp in different timezone
        other_tz = timezone(timedelta(hours=5))
        dt = datetime(2024, 1, 15, 15, 30, 45, tzinfo=other_tz)
        timestamp = Timestamp(value=dt)

        # Convert to UTC
        utc_timestamp = timestamp.to_utc()
        expected = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
        assert utc_timestamp.value == expected
        assert utc_timestamp.value.tzinfo == UTC

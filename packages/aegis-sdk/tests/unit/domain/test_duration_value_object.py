"""Tests for the Duration value object."""

import pytest

from aegis_sdk.domain.value_objects import Duration


class TestDuration:
    """Test the Duration value object."""

    def test_create_duration_from_seconds(self):
        """Test creating duration from seconds."""
        duration = Duration(seconds=90)
        assert duration.seconds == 90
        assert duration.total_seconds() == 90

    def test_create_duration_from_milliseconds(self):
        """Test creating duration from milliseconds."""
        duration = Duration.from_milliseconds(1500)
        assert duration.seconds == 1.5
        assert duration.total_seconds() == 1.5

    def test_create_duration_from_minutes(self):
        """Test creating duration from minutes."""
        duration = Duration.from_minutes(2)
        assert duration.seconds == 120
        assert duration.total_seconds() == 120

    def test_create_duration_from_hours(self):
        """Test creating duration from hours."""
        duration = Duration.from_hours(1.5)
        assert duration.seconds == 5400
        assert duration.total_seconds() == 5400

    def test_duration_string_representation(self):
        """Test string representation of duration."""
        # Seconds only
        assert str(Duration(seconds=45)) == "45s"

        # Minutes and seconds
        assert str(Duration(seconds=90)) == "1m 30s"

        # Hours, minutes and seconds
        assert str(Duration(seconds=3665)) == "1h 1m 5s"

        # Days
        assert str(Duration(seconds=90000)) == "1d 1h"

        # Fractional seconds
        assert str(Duration(seconds=1.5)) == "1.5s"

    def test_duration_comparison(self):
        """Test duration comparison operations."""
        d1 = Duration(seconds=30)
        d2 = Duration(seconds=60)
        d3 = Duration(seconds=60)

        # Less than
        assert d1 < d2
        assert not d2 < d1

        # Greater than
        assert d2 > d1
        assert not d1 > d2

        # Equal
        assert d2 == d3
        assert d1 != d2

        # Less than or equal
        assert d1 <= d2
        assert d2 <= d3

        # Greater than or equal
        assert d2 >= d1
        assert d2 >= d3

    def test_duration_arithmetic(self):
        """Test duration arithmetic operations."""
        d1 = Duration(seconds=30)
        d2 = Duration(seconds=20)

        # Addition
        result = d1 + d2
        assert result.seconds == 50
        assert isinstance(result, Duration)

        # Subtraction
        result = d1 - d2
        assert result.seconds == 10
        assert isinstance(result, Duration)

        # Multiplication by scalar
        result = d1 * 2
        assert result.seconds == 60
        assert isinstance(result, Duration)

        # Division by scalar
        result = d1 / 2
        assert result.seconds == 15
        assert isinstance(result, Duration)

    def test_duration_negative_not_allowed(self):
        """Test that negative durations are not allowed."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            Duration(seconds=-1)

        # Subtraction resulting in negative should also fail
        d1 = Duration(seconds=10)
        d2 = Duration(seconds=20)
        with pytest.raises(ValueError, match="Duration must be non-negative"):
            d1 - d2

    def test_duration_immutability(self):
        """Test that Duration is immutable."""
        from pydantic import ValidationError

        duration = Duration(seconds=60)
        with pytest.raises(ValidationError, match="frozen"):
            duration.seconds = 120

    def test_duration_conversions(self):
        """Test duration conversion methods."""
        duration = Duration(seconds=3665.5)

        assert duration.to_milliseconds() == 3665500
        assert duration.to_minutes() == pytest.approx(61.0916667, rel=1e-5)
        assert duration.to_hours() == pytest.approx(1.0181944, rel=1e-5)

    def test_duration_is_zero(self):
        """Test is_zero method."""
        assert Duration(seconds=0).is_zero()
        assert not Duration(seconds=0.1).is_zero()
        assert not Duration(seconds=1).is_zero()

    def test_duration_hash(self):
        """Test that Duration is hashable."""
        d1 = Duration(seconds=60)
        d2 = Duration(seconds=60)
        d3 = Duration(seconds=61)

        # Same durations have same hash
        assert hash(d1) == hash(d2)

        # Can be used in sets
        duration_set = {d1, d2, d3}
        assert len(duration_set) == 2  # d1 and d2 are the same

    def test_duration_from_timedelta(self):
        """Test creating Duration from timedelta."""
        from datetime import timedelta

        td = timedelta(hours=1, minutes=30, seconds=45)
        duration = Duration.from_timedelta(td)

        assert duration.seconds == 5445
        assert duration.to_hours() == pytest.approx(1.5125, rel=1e-5)

    def test_duration_to_timedelta(self):
        """Test converting Duration to timedelta."""
        from datetime import timedelta

        duration = Duration(seconds=5445)
        td = duration.to_timedelta()

        assert isinstance(td, timedelta)
        assert td.total_seconds() == 5445

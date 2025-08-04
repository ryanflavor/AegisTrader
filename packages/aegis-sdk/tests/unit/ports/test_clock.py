"""Tests for the Clock port abstraction."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from aegis_sdk.ports.clock import ClockPort


class TestClockPort:
    """Test the Clock port interface."""

    def test_clock_port_is_abstract(self):
        """Test that ClockPort cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ClockPort()

    def test_mock_clock_implementation(self):
        """Test using a mock clock for testing."""
        # Create a mock clock
        mock_clock = Mock(spec=ClockPort)

        # Set up the mock to return a specific time
        test_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_clock.now.return_value = test_time

        # Use the clock
        current_time = mock_clock.now()

        # Verify the result
        assert current_time == test_time
        assert current_time.tzinfo == UTC
        mock_clock.now.assert_called_once()

    def test_clock_timezone_awareness(self):
        """Test that clock always returns timezone-aware datetimes."""
        # Create a mock clock that returns timezone-aware time
        mock_clock = Mock(spec=ClockPort)

        # Test UTC
        utc_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_clock.now.return_value = utc_time
        assert mock_clock.now().tzinfo is not None
        assert mock_clock.now().tzinfo == UTC

        # Test other timezone
        other_tz = timezone(timedelta(hours=5))
        tz_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=other_tz)
        mock_clock.now.return_value = tz_time
        assert mock_clock.now().tzinfo is not None
        assert mock_clock.now().tzinfo == other_tz

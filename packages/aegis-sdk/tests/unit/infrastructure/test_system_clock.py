"""Tests for the SystemClock implementation."""

from datetime import UTC, datetime

from aegis_sdk.infrastructure.system_clock import SystemClock
from aegis_sdk.ports.clock import ClockPort


class TestSystemClock:
    """Test the SystemClock implementation."""

    def test_implements_clock_port(self):
        """Test that SystemClock implements ClockPort interface."""
        clock = SystemClock()
        assert isinstance(clock, ClockPort)

    def test_returns_current_time(self):
        """Test that now() returns current time."""
        clock = SystemClock()

        # Get time before and after
        before = datetime.now(UTC)
        clock_time = clock.now()
        after = datetime.now(UTC)

        # Clock time should be between before and after
        assert before <= clock_time <= after

    def test_returns_timezone_aware_datetime(self):
        """Test that now() returns timezone-aware datetime."""
        clock = SystemClock()
        current_time = clock.now()

        assert current_time.tzinfo is not None
        assert current_time.tzinfo == UTC

    def test_consistent_timezone(self):
        """Test that SystemClock consistently returns UTC times."""
        clock = SystemClock()

        # Multiple calls should all return UTC
        for _ in range(5):
            time = clock.now()
            assert time.tzinfo == UTC

    def test_multiple_calls_advance_time(self):
        """Test that multiple calls return advancing time."""
        clock = SystemClock()

        times = []
        for _ in range(3):
            times.append(clock.now())

        # Each subsequent time should be >= previous
        for i in range(1, len(times)):
            assert times[i] >= times[i - 1]

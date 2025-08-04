"""System clock implementation using Python's datetime."""

from datetime import UTC, datetime

from ..ports.clock import ClockPort


class SystemClock(ClockPort):
    """Default clock implementation using system time.

    This implementation uses Python's datetime module to provide
    the current time in UTC timezone.
    """

    def now(self) -> datetime:
        """Get the current UTC time.

        Returns:
            The current time as a timezone-aware datetime in UTC.
        """
        return datetime.now(UTC)

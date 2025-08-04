"""Clock port abstraction for time handling.

This module defines the clock abstraction to decouple domain logic from
system time, making it easier to test and control time-dependent behavior.
"""

from abc import ABC, abstractmethod
from datetime import datetime


class ClockPort(ABC):
    """Abstract clock interface for time operations.

    This port provides an abstraction over system time, allowing for:
    - Consistent timezone-aware datetime handling
    - Easy testing with mock clocks
    - Potential for custom time sources (e.g., NTP-synchronized)
    """

    @abstractmethod
    def now(self) -> datetime:
        """Get the current time as a timezone-aware datetime.

        Returns:
            A timezone-aware datetime representing the current time.

        Note:
            Implementations MUST return timezone-aware datetimes.
            Using UTC is recommended for consistency.
        """
        ...

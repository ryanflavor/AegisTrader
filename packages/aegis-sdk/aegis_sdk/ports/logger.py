"""Logger port for infrastructure logging."""

from abc import ABC, abstractmethod
from typing import Any


class LoggerPort(ABC):
    """Abstract interface for logging operations.

    This port defines the contract for logging implementations,
    following the dependency inversion principle.
    """

    @abstractmethod
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        ...

    @abstractmethod
    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        ...

    @abstractmethod
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        ...

    @abstractmethod
    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error message."""
        ...

    @abstractmethod
    def exception(self, message: str, exc_info: Exception | None = None, **kwargs: Any) -> None:
        """Log an exception with traceback."""
        ...

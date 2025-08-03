"""Simple logger implementation for development."""

import logging
from typing import Any

from ..ports.logger import LoggerPort


class SimpleLogger(LoggerPort):
    """Simple logger implementation using Python's standard logging.

    This is a basic implementation suitable for development and testing.
    Production environments should use more sophisticated logging solutions.
    """

    def __init__(self, name: str = "aegis_sdk", level: int = logging.INFO):
        """Initialize the logger.

        Args:
            name: Logger name (default: "aegis_sdk")
            level: Logging level (default: INFO)
        """
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)

        # Add console handler if not already present
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        self._logger.debug(message, extra=kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        self._logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        self._logger.warning(message, extra=kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error message."""
        self._logger.error(message, extra=kwargs)

    def exception(self, message: str, exc_info: Exception | None = None, **kwargs: Any) -> None:
        """Log an exception with traceback."""
        self._logger.exception(message, exc_info=exc_info or True, extra=kwargs)

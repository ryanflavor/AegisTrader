"""
Centralized logging configuration for Market Service.
Prevents duplicate logs and controls verbosity.
"""

import logging
import os
import sys


def setup_logging(log_level: str = None) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: Logging level (INFO, WARNING, ERROR, DEBUG)
    """
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")

    # Clear any existing handlers
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Create single stream handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
    )

    # Configure root logger
    root.setLevel(log_level)
    root.addHandler(handler)

    # Silence noisy loggers
    if log_level != "DEBUG":
        # SDK internals - show INFO for debugging heartbeat issues
        logging.getLogger("aegis_sdk.nats_kv_store").setLevel(logging.WARNING)
        logging.getLogger("aegis_sdk.infrastructure").setLevel(logging.INFO)
        logging.getLogger("aegis_sdk.application").setLevel(logging.INFO)

        # Service duplicates - disable propagation
        logging.getLogger("CTP-Gateway").propagate = False
        logging.getLogger("market-service").propagate = False

        # Re-add handler for critical service logs only
        for service_name in ["CTP-Gateway", "market-service"]:
            service_logger = logging.getLogger(service_name)
            service_logger.setLevel(logging.INFO)
            # Create filter to only show important messages
            service_logger.addFilter(ImportantLogFilter())

    # Application loggers stay at configured level
    logging.getLogger("application").setLevel(log_level)
    logging.getLogger("infra").setLevel(log_level)
    logging.getLogger("domain").setLevel(log_level)


class ImportantLogFilter(logging.Filter):
    """Filter to only show important log messages."""

    IMPORTANT_PATTERNS = [
        "Service started",
        "Service stopped",
        "Won election",
        "Lost election",
        "Leadership acquired",
        "Leadership released",
        "ERROR",
        "WARNING",
        "CRITICAL",
        "Successfully took over",
        "Connected to",
        "Disconnected from",
        "Gateway.*initialized",
        "Periodic check",
        "heartbeat",
        "Heartbeat",
        "Leader expired",
        "STALE",
        "Not the current leader",
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records to only show important messages."""
        # Always show warnings and above
        if record.levelno >= logging.WARNING:
            return True

        # Check if message matches important patterns
        message = record.getMessage()
        return any(pattern in message for pattern in self.IMPORTANT_PATTERNS)

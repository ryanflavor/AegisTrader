"""Comprehensive tests for SimpleLogger implementation following TDD principles."""

import logging
from unittest.mock import Mock, patch

from aegis_sdk.infrastructure.simple_logger import SimpleLogger
from aegis_sdk.ports.logger import LoggerPort


class TestSimpleLogger:
    """Test cases for SimpleLogger implementation."""

    def test_implements_logger_port(self):
        """Test that SimpleLogger properly implements LoggerPort."""
        logger = SimpleLogger()
        assert isinstance(logger, LoggerPort)

    def test_initialization_default_values(self):
        """Test logger initialization with default values."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            SimpleLogger()

            mock_get_logger.assert_called_once_with("aegis_sdk")
            mock_logger.setLevel.assert_called_once_with(logging.INFO)

    def test_initialization_custom_values(self):
        """Test logger initialization with custom values."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            SimpleLogger(name="custom_logger", level=logging.DEBUG)

            mock_get_logger.assert_called_once_with("custom_logger")
            mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    def test_handler_added_when_none_exist(self):
        """Test that handler is added when none exist."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_logger.handlers = []  # No handlers
            mock_get_logger.return_value = mock_logger

            with patch("logging.StreamHandler") as mock_handler_class:
                mock_handler = Mock()
                mock_handler_class.return_value = mock_handler

                SimpleLogger()

                mock_handler_class.assert_called_once()
                mock_logger.addHandler.assert_called_once_with(mock_handler)
                mock_handler.setFormatter.assert_called_once()

    def test_handler_not_added_when_exists(self):
        """Test that handler is not added when one already exists."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_logger.handlers = [Mock()]  # Existing handler
            mock_get_logger.return_value = mock_logger

            with patch("logging.StreamHandler") as mock_handler_class:
                SimpleLogger()

                # Handler should not be created
                mock_handler_class.assert_not_called()
                mock_logger.addHandler.assert_not_called()

    def test_debug_method(self):
        """Test debug method without kwargs."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            logger = SimpleLogger()
            logger.debug("Debug message")

            mock_logger.debug.assert_called_once_with("Debug message", extra={})

    def test_debug_method_with_kwargs(self):
        """Test debug method with kwargs - covers line 35."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            logger = SimpleLogger()
            logger.debug("Debug message", user_id=123, action="login")

            mock_logger.debug.assert_called_once_with(
                "Debug message", extra={"user_id": 123, "action": "login"}
            )

    def test_info_method(self):
        """Test info method."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            logger = SimpleLogger()
            logger.info("Info message", request_id="abc123")

            mock_logger.info.assert_called_once_with("Info message", extra={"request_id": "abc123"})

    def test_warning_method(self):
        """Test warning method."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            logger = SimpleLogger()
            logger.warning("Warning message", threshold=0.8)

            mock_logger.warning.assert_called_once_with("Warning message", extra={"threshold": 0.8})

    def test_error_method(self):
        """Test error method."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            logger = SimpleLogger()
            logger.error("Error message", error_code="E001")

            mock_logger.error.assert_called_once_with("Error message", extra={"error_code": "E001"})

    def test_exception_method_with_exception_object(self):
        """Test exception method with explicit exception."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            logger = SimpleLogger()
            exc = ValueError("Test error")
            logger.exception("Exception occurred", exc_info=exc, context="processing")

            mock_logger.exception.assert_called_once_with(
                "Exception occurred", exc_info=exc, extra={"context": "processing"}
            )

    def test_exception_method_without_exception(self):
        """Test exception method without explicit exception."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            logger = SimpleLogger()
            logger.exception("Exception occurred", request_id="xyz789")

            mock_logger.exception.assert_called_once_with(
                "Exception occurred", exc_info=True, extra={"request_id": "xyz789"}
            )

    def test_formatter_configuration(self):
        """Test that formatter is properly configured."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_logger.handlers = []
            mock_get_logger.return_value = mock_logger

            with patch("logging.StreamHandler") as mock_handler_class:
                mock_handler = Mock()
                mock_handler_class.return_value = mock_handler

                with patch("logging.Formatter") as mock_formatter_class:
                    mock_formatter = Mock()
                    mock_formatter_class.return_value = mock_formatter

                    SimpleLogger()

                    # Check formatter format string
                    mock_formatter_class.assert_called_once_with(
                        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                    )
                    mock_handler.setFormatter.assert_called_once_with(mock_formatter)

    def test_different_log_levels(self):
        """Test initialization with different log levels."""
        test_levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]

        for level, level_name in test_levels:
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                SimpleLogger(name=f"test_{level_name}", level=level)

                mock_logger.setLevel.assert_called_once_with(level)

    def test_multiple_kwargs_handling(self):
        """Test handling of multiple kwargs in logging methods."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            SimpleLogger()

            # Test with many kwargs
            kwargs = {
                "user_id": 123,
                "session_id": "abc-def-ghi",
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0",
                "timestamp": "2025-01-01T00:00:00Z",
                "action": "login",
                "success": True,
            }

            logger = SimpleLogger()
            logger.info("User action", **kwargs)

            mock_logger.info.assert_called_once_with("User action", extra=kwargs)

    def test_edge_cases(self):
        """Test edge cases for logger."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            SimpleLogger()

            # Empty message
            logger = SimpleLogger()
            logger.debug("")
            mock_logger.debug.assert_called_with("", extra={})

            # None as kwargs value
            logger = SimpleLogger()
            logger.info("Test", value=None)
            mock_logger.info.assert_called_with("Test", extra={"value": None})

            # Special characters in message
            logger = SimpleLogger()
            logger.warning("Test with special chars: !@#$%^&*()")
            mock_logger.warning.assert_called_with("Test with special chars: !@#$%^&*()", extra={})

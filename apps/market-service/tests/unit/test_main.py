"""Unit tests for refactored main.py following DDD and hexagonal architecture."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMainEntry:
    """Test main entry point with ApplicationFactory."""

    @pytest.mark.asyncio
    async def test_main_uses_application_factory(self):
        """Test that main properly uses ApplicationFactory for dependency injection."""
        # Arrange
        mock_launcher = AsyncMock()
        mock_launcher.run = AsyncMock()
        mock_launcher.cleanup = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.create_application = AsyncMock(return_value=mock_launcher)

        with (
            patch("main.ApplicationFactory", return_value=mock_factory),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance

            # Import main after patching
            from main import main

            # Act
            # Create task to test main
            task = asyncio.create_task(main())

            # Wait briefly for initialization
            await asyncio.sleep(0.1)

            # Cancel task to simulate shutdown
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            # Assert
            mock_factory.create_application.assert_called_once()
            mock_launcher.run.assert_called_once()
            mock_launcher.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_handles_exceptions(self):
        """Test that main properly handles exceptions."""
        # Arrange
        mock_launcher = AsyncMock()
        mock_launcher.run = AsyncMock(side_effect=Exception("Test error"))
        mock_launcher.cleanup = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.create_application = AsyncMock(return_value=mock_launcher)

        with (
            patch("main.ApplicationFactory", return_value=mock_factory),
            patch("asyncio.get_event_loop") as mock_loop,
            patch("main.logger") as mock_logger,
        ):
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance

            # Import main after patching
            from main import main

            # Act & Assert
            # The main function should handle the exception
            await main()

            # Verify error was logged
            mock_logger.error.assert_called()
            # Verify cleanup was still called
            mock_launcher.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_signal_handlers(self):
        """Test that main sets up signal handlers correctly."""
        # Arrange
        mock_launcher = AsyncMock()
        mock_launcher.run = AsyncMock()
        mock_launcher.cleanup = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.create_application = AsyncMock(return_value=mock_launcher)

        with (
            patch("main.ApplicationFactory", return_value=mock_factory),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance

            # Import main after patching
            from main import main

            # Act
            task = asyncio.create_task(main())
            await asyncio.sleep(0.1)
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            # Assert - signal handlers should be added for SIGTERM and SIGINT
            assert mock_loop_instance.add_signal_handler.call_count == 2

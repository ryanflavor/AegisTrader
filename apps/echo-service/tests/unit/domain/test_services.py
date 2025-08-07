"""Unit tests for domain services."""

from __future__ import annotations

import pytest
from app.domain.models import EchoMode, EchoRequest
from app.domain.services import EchoProcessor, MetricsCollector


class TestEchoProcessor:
    """Test cases for the EchoProcessor domain service."""

    @pytest.mark.asyncio
    async def test_simple_echo(self):
        """Test simple echo mode processing."""
        # Arrange
        processor = EchoProcessor("test-instance")
        request = EchoRequest(message="Hello World", mode=EchoMode.SIMPLE)

        # Act
        response = await processor.process_echo(request)

        # Assert
        assert response.echo == "Hello World"
        assert response.original == "Hello World"
        assert response.mode == EchoMode.SIMPLE
        assert response.instance_id == "test-instance"
        assert response.sequence_number == 1
        assert response.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_delayed_echo(self):
        """Test delayed echo mode processing."""
        # Arrange
        processor = EchoProcessor("test-instance")
        request = EchoRequest(
            message="Test",
            mode=EchoMode.DELAYED,
            delay_seconds=0.01,  # Small delay for testing
        )

        # Act
        response = await processor.process_echo(request)

        # Assert
        assert "[Delayed 0.01s] Test" in response.echo
        assert response.original == "Test"
        assert response.mode == EchoMode.DELAYED
        assert response.processing_time_ms >= 10  # At least 10ms due to delay

    @pytest.mark.asyncio
    async def test_transform_echo_uppercase(self):
        """Test transform echo mode with uppercase."""
        # Arrange
        processor = EchoProcessor("test-instance")
        request = EchoRequest(
            message="hello",
            mode=EchoMode.TRANSFORM,
            transform_type=None,  # Default to uppercase
        )

        # Act
        response = await processor.process_echo(request)

        # Assert
        assert response.echo == "HELLO"
        assert response.original == "hello"

    @pytest.mark.asyncio
    async def test_transform_echo_reverse(self):
        """Test transform echo mode with reverse."""
        # Arrange
        processor = EchoProcessor("test-instance")
        request = EchoRequest(message="hello", mode=EchoMode.TRANSFORM, transform_type="reverse")

        # Act
        response = await processor.process_echo(request)

        # Assert
        assert response.echo == "olleh"
        assert response.original == "hello"

    @pytest.mark.asyncio
    async def test_batch_echo(self):
        """Test batch echo mode processing."""
        # Arrange
        processor = EchoProcessor("test-instance")
        request = EchoRequest(message="Test", mode=EchoMode.BATCH)

        # Act
        response = await processor.process_echo(request)

        # Assert
        assert response.echo == "Test | Test | Test"
        assert response.mode == EchoMode.BATCH

    @pytest.mark.asyncio
    async def test_sequence_counter_increments(self):
        """Test that sequence counter increments with each request."""
        # Arrange
        processor = EchoProcessor("test-instance")
        request = EchoRequest(message="Test")

        # Act
        response1 = await processor.process_echo(request)
        response2 = await processor.process_echo(request)
        response3 = await processor.process_echo(request)

        # Assert
        assert response1.sequence_number == 1
        assert response2.sequence_number == 2
        assert response3.sequence_number == 3


class TestMetricsCollector:
    """Test cases for the MetricsCollector domain service."""

    def test_record_successful_request(self):
        """Test recording a successful request."""
        # Arrange
        collector = MetricsCollector()

        # Act
        collector.record_request(EchoMode.SIMPLE, 10.5, success=True)

        # Assert
        assert collector.total_requests == 1
        assert collector.successful_requests == 1
        assert collector.failed_requests == 0
        assert collector.get_average_latency() == 10.5
        assert collector.mode_counts[EchoMode.SIMPLE] == 1

    def test_record_failed_request(self):
        """Test recording a failed request."""
        # Arrange
        collector = MetricsCollector()

        # Act
        collector.record_request(EchoMode.SIMPLE, 0.0, success=False)

        # Assert
        assert collector.total_requests == 1
        assert collector.successful_requests == 0
        assert collector.failed_requests == 1

    def test_average_latency_calculation(self):
        """Test average latency calculation."""
        # Arrange
        collector = MetricsCollector()

        # Act
        collector.record_request(EchoMode.SIMPLE, 10.0, success=True)
        collector.record_request(EchoMode.SIMPLE, 20.0, success=True)
        collector.record_request(EchoMode.SIMPLE, 30.0, success=True)

        # Assert
        assert collector.get_average_latency() == 20.0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        # Arrange
        collector = MetricsCollector()

        # Act
        collector.record_request(EchoMode.SIMPLE, 10.0, success=True)
        collector.record_request(EchoMode.SIMPLE, 10.0, success=True)
        collector.record_request(EchoMode.SIMPLE, 10.0, success=False)

        # Assert
        success_rate = collector.get_success_rate()
        assert success_rate == pytest.approx(66.67, rel=0.1)

    def test_success_rate_with_no_requests(self):
        """Test success rate when no requests have been made."""
        # Arrange
        collector = MetricsCollector()

        # Act
        success_rate = collector.get_success_rate()

        # Assert
        assert success_rate == 100.0

    def test_mode_distribution_tracking(self):
        """Test that different modes are tracked correctly."""
        # Arrange
        collector = MetricsCollector()

        # Act
        collector.record_request(EchoMode.SIMPLE, 10.0)
        collector.record_request(EchoMode.SIMPLE, 10.0)
        collector.record_request(EchoMode.DELAYED, 10.0)
        collector.record_request(EchoMode.TRANSFORM, 10.0)
        collector.record_request(EchoMode.BATCH, 10.0)

        # Assert
        assert collector.mode_counts[EchoMode.SIMPLE] == 2
        assert collector.mode_counts[EchoMode.DELAYED] == 1
        assert collector.mode_counts[EchoMode.TRANSFORM] == 1
        assert collector.mode_counts[EchoMode.BATCH] == 1

    def test_uptime_calculation(self):
        """Test uptime calculation."""
        # Arrange
        collector = MetricsCollector()

        # Act
        import time

        time.sleep(0.1)  # Sleep for 100ms
        uptime = collector.get_uptime_seconds()

        # Assert
        assert uptime >= 0.1
        assert uptime < 1.0  # Should be less than 1 second

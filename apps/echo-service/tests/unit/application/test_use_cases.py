"""Unit tests for application use cases following TDD and hexagonal architecture."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.application.use_cases import EchoUseCase, GetMetricsUseCase, HealthCheckUseCase
from app.domain.models import EchoMode, EchoRequest, EchoResponse
from app.domain.services import EchoProcessor, MetricsCollector


class TestEchoUseCase:
    """Test suite for EchoUseCase."""

    @pytest.fixture
    def processor(self):
        """Create mock echo processor."""
        processor = MagicMock(spec=EchoProcessor)
        processor.process_echo = AsyncMock()
        return processor

    @pytest.fixture
    def metrics(self):
        """Create mock metrics collector."""
        return MagicMock(spec=MetricsCollector)

    @pytest.fixture
    def use_case(self, processor, metrics):
        """Create echo use case with mocks."""
        return EchoUseCase(processor, metrics)

    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, processor, metrics):
        """Test successful echo request execution."""
        # Setup
        request = EchoRequest(
            message="test",
            mode=EchoMode.SIMPLE,
        )
        response = EchoResponse(
            original="test",
            echo="test",
            mode=EchoMode.SIMPLE,
            processing_time_ms=10.5,
            sequence_number=1,
            instance_id="test-123",
        )
        processor.process_echo.return_value = response

        # Execute
        result = await use_case.execute(request)

        # Verify
        assert result == response
        processor.process_echo.assert_called_once_with(request)
        metrics.record_request.assert_called_once_with(
            mode=EchoMode.SIMPLE,
            latency_ms=10.5,
            success=True,
        )

    @pytest.mark.asyncio
    async def test_execute_failure(self, use_case, processor, metrics):
        """Test echo request execution failure."""
        # Setup
        request = EchoRequest(
            message="test",
            mode=EchoMode.TRANSFORM,
            transform_type="uppercase",
        )
        processor.process_echo.side_effect = ValueError("Processing failed")

        # Execute and verify exception is raised
        with pytest.raises(ValueError) as exc_info:
            await use_case.execute(request)

        assert "Processing failed" in str(exc_info.value)

        # Verify failure was recorded
        processor.process_echo.assert_called_once_with(request)
        metrics.record_request.assert_called_once_with(
            mode=EchoMode.TRANSFORM,
            latency_ms=0.0,
            success=False,
        )


class TestGetMetricsUseCase:
    """Test suite for GetMetricsUseCase."""

    @pytest.fixture
    def metrics(self):
        """Create mock metrics collector."""
        metrics = MagicMock(spec=MetricsCollector)
        metrics.total_requests = 100
        metrics.successful_requests = 95
        metrics.failed_requests = 5
        metrics.get_average_latency.return_value = 15.5
        metrics.get_uptime_seconds.return_value = 3600.0
        metrics.mode_counts = {
            EchoMode.SIMPLE: 50,
            EchoMode.DELAYED: 30,
            EchoMode.TRANSFORM: 20,
        }
        return metrics

    @pytest.fixture
    def use_case(self, metrics):
        """Create metrics use case with mocks."""
        return GetMetricsUseCase(
            instance_id="test-123",
            version="1.0.0",
            metrics=metrics,
        )

    @pytest.mark.asyncio
    async def test_execute_without_requests(self, use_case, metrics):
        """Test getting metrics when no requests have been made."""
        result = await use_case.execute()

        assert result.instance_id == "test-123"
        assert result.total_requests == 100
        assert result.successful_requests == 95
        assert result.failed_requests == 5
        assert result.average_latency_ms == 15.5
        assert result.uptime_seconds == 3600.0
        assert result.last_request_at is None
        assert result.mode_distribution == {
            EchoMode.SIMPLE: 50,
            EchoMode.DELAYED: 30,
            EchoMode.TRANSFORM: 20,
        }

    @pytest.mark.asyncio
    async def test_execute_with_last_request(self, use_case):
        """Test getting metrics after recording last request time."""
        # Update last request time
        test_time = datetime.now(UTC)
        use_case.update_last_request_time()

        # Execute
        result = await use_case.execute()

        assert result.last_request_at is not None
        # Check that the time is recent (within last second)
        time_diff = (datetime.now(UTC) - result.last_request_at).total_seconds()
        assert time_diff < 1.0

    def test_update_last_request_time(self, use_case):
        """Test updating last request timestamp."""
        assert use_case.last_request_time is None

        use_case.update_last_request_time()

        assert use_case.last_request_time is not None
        assert isinstance(use_case.last_request_time, datetime)


class TestHealthCheckUseCase:
    """Test suite for HealthCheckUseCase."""

    @pytest.fixture
    def use_case(self):
        """Create health check use case."""
        return HealthCheckUseCase(
            instance_id="test-123",
            version="1.0.0",
        )

    @pytest.mark.asyncio
    async def test_execute_healthy(self, use_case):
        """Test health check when all checks pass."""
        use_case.set_nats_status(True)

        result = await use_case.execute()

        assert result.status == "healthy"
        assert result.instance_id == "test-123"
        assert result.version == "1.0.0"
        assert result.checks["nats"] is True
        assert result.checks["processor"] is True
        assert "memory" in result.checks

    @pytest.mark.asyncio
    async def test_execute_degraded(self, use_case):
        """Test health check when NATS is connected but memory check fails."""
        use_case.set_nats_status(True)

        # Mock memory check to fail
        with patch.object(use_case, "_check_memory", return_value=False):
            result = await use_case.execute()

        assert result.status == "degraded"
        assert result.checks["nats"] is True
        assert result.checks["processor"] is True
        assert result.checks["memory"] is False

    @pytest.mark.asyncio
    async def test_execute_unhealthy(self, use_case):
        """Test health check when NATS is disconnected."""
        use_case.set_nats_status(False)

        result = await use_case.execute()

        assert result.status == "unhealthy"
        assert result.checks["nats"] is False
        assert result.checks["processor"] is True

    def test_set_nats_status(self, use_case):
        """Test setting NATS connection status."""
        assert use_case.nats_connected is False

        use_case.set_nats_status(True)
        assert use_case.nats_connected is True

        use_case.set_nats_status(False)
        assert use_case.nats_connected is False

    def test_check_memory_within_limits(self, use_case):
        """Test memory check when within limits."""
        # Mock process memory info
        with patch("psutil.Process") as mock_process_class:
            mock_process = MagicMock()
            mock_process.memory_info.return_value.rss = 100 * 1024 * 1024  # 100MB
            mock_process_class.return_value = mock_process

            result = use_case._check_memory()

        assert result is True

    def test_check_memory_exceeds_limits(self, use_case):
        """Test memory check when exceeding limits."""
        # Mock process memory info
        with patch("psutil.Process") as mock_process_class:
            mock_process = MagicMock()
            mock_process.memory_info.return_value.rss = 300 * 1024 * 1024  # 300MB
            mock_process_class.return_value = mock_process

            result = use_case._check_memory()

        assert result is False

    def test_check_memory_without_psutil(self, use_case):
        """Test memory check when psutil is not available."""
        # When psutil is not available, should return True
        import sys

        # Temporarily remove psutil from sys.modules to simulate import failure
        psutil_backup = sys.modules.get("psutil")
        if "psutil" in sys.modules:
            del sys.modules["psutil"]

        # Mock the import to raise ImportError
        with patch.dict("sys.modules", {"psutil": None}):
            result = use_case._check_memory()

        # Restore psutil if it was there
        if psutil_backup:
            sys.modules["psutil"] = psutil_backup

        assert result is True

    def test_check_memory_with_exception(self, use_case):
        """Test memory check when exception occurs."""
        # Mock process to raise exception
        with patch("psutil.Process") as mock_process_class:
            mock_process_class.side_effect = Exception("Process error")

            result = use_case._check_memory()

        assert result is False

"""Comprehensive edge case and error scenario tests for TestExecutionService following TDD principles."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from aegis_sdk_dev.application.test_runner_service import TestExecutionService
from aegis_sdk_dev.domain.models import (
    ExecutionResult,
    ExecutionType,
    RunConfiguration,
    ValidationIssue,
    ValidationLevel,
)


class TestTestExecutionServiceEdgeCases:
    """Test TestExecutionService edge cases and error conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_console = Mock()
        self.mock_process_executor = Mock()
        self.service = TestExecutionService(
            console=self.mock_console,
            process_executor=self.mock_process_executor,
        )

    # Test initialization edge cases
    def test_init_with_none_console_raises(self):
        """Test initialization with None console raises error."""
        # Act & Assert
        with pytest.raises(AttributeError):
            service = TestExecutionService(
                console=None,
                process_executor=self.mock_process_executor,
            )
            # Try to use the service
            asyncio.run(service.run_tests())

    def test_init_with_none_process_executor_raises(self):
        """Test initialization with None process executor raises error."""
        # Act & Assert
        with pytest.raises(AttributeError):
            service = TestExecutionService(
                console=self.mock_console,
                process_executor=None,
            )
            # Try to use the service
            asyncio.run(service.run_tests())

    def test_init_with_invalid_dependencies(self):
        """Test initialization with invalid dependency types."""
        # Act & Assert - should work due to duck typing
        service = TestExecutionService(
            console="not_a_console",  # Wrong type but might work with duck typing
            process_executor=123,  # Wrong type
        )
        # Will fail when trying to use methods
        with pytest.raises(AttributeError):
            asyncio.run(service.run_tests())

    # Test run_tests edge cases
    @pytest.mark.asyncio
    async def test_run_tests_with_invalid_test_type(self):
        """Test run_tests with invalid test type."""
        # Act & Assert
        with pytest.raises(ValueError):
            await self.service.run_tests(test_type="invalid_type")

        # Verify error message was printed
        self.mock_console.print_error.assert_called_with("Invalid test type: invalid_type")

    @pytest.mark.asyncio
    async def test_run_tests_with_empty_test_type(self):
        """Test run_tests with empty test type string."""
        # Act & Assert
        with pytest.raises(ValueError):
            await self.service.run_tests(test_type="")

    @pytest.mark.asyncio
    async def test_run_tests_with_none_test_type(self):
        """Test run_tests with None test type."""
        # Act & Assert
        with pytest.raises(TypeError):
            await self.service.run_tests(test_type=None)

    @pytest.mark.asyncio
    async def test_run_tests_with_negative_min_coverage(self):
        """Test run_tests with negative minimum coverage."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(0, "All tests passed"))

        # Act
        result = await self.service.run_tests(test_type="unit", min_coverage=-10.0)

        # Assert - should handle gracefully
        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    async def test_run_tests_with_min_coverage_over_100(self):
        """Test run_tests with minimum coverage over 100%."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(0, "All tests passed"))

        # Act
        result = await self.service.run_tests(test_type="unit", min_coverage=150.0)

        # Assert - should handle gracefully
        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    async def test_run_tests_with_invalid_test_path(self):
        """Test run_tests with non-existent test path."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(
            return_value=(1, "ERROR: test path not found")
        )

        # Act
        result = await self.service.run_tests(test_type="unit", test_path="/nonexistent/path")

        # Assert
        assert result.failed > 0

    @pytest.mark.asyncio
    async def test_run_tests_with_empty_markers_list(self):
        """Test run_tests with empty markers list."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(0, "All tests passed"))

        # Act
        result = await self.service.run_tests(test_type="unit", markers=[])

        # Assert
        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    async def test_run_tests_with_invalid_markers(self):
        """Test run_tests with invalid marker syntax."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(0, "All tests passed"))

        # Act
        result = await self.service.run_tests(
            test_type="unit", markers=["not-a-valid-marker!", "@#$%"]
        )

        # Assert - pytest should handle invalid markers
        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    async def test_run_tests_timeout_handling(self):
        """Test run_tests handles timeout correctly."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(
            side_effect=TimeoutError("Test execution timed out")
        )

        # Act
        result = await self.service.run_tests(test_type="unit")

        # Assert
        assert result.failed == 1
        assert "Test execution timed out" in result.errors
        assert result.duration_seconds == 300.0
        self.mock_console.print_error.assert_called_with("Test execution timed out after 5 minutes")

    @pytest.mark.asyncio
    async def test_run_tests_process_executor_exception(self):
        """Test run_tests when process executor raises unexpected exception."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="Unexpected error"):
            await self.service.run_tests(test_type="unit")

    @pytest.mark.asyncio
    async def test_run_tests_with_exit_code_minus_one(self):
        """Test run_tests with exit code -1 (killed process)."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(-1, "Process killed"))

        # Act
        result = await self.service.run_tests(test_type="unit")

        # Assert
        assert result.failed > 0

    @pytest.mark.asyncio
    async def test_run_tests_with_very_long_output(self):
        """Test run_tests with extremely long output."""
        # Arrange
        long_output = "x" * (10 * 1024 * 1024)  # 10MB of output
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(0, long_output))

        # Act
        result = await self.service.run_tests(test_type="unit")

        # Assert - should handle large output
        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    async def test_run_tests_with_unicode_output(self):
        """Test run_tests with unicode characters in output."""
        # Arrange
        unicode_output = "Tests passed ✓ 世界 🌍 مرحبا"
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(0, unicode_output))

        # Act
        result = await self.service.run_tests(test_type="unit")

        # Assert
        assert isinstance(result, ExecutionResult)

    # Test _display_test_results edge cases
    def test_display_test_results_with_zero_tests(self):
        """Test displaying results when no tests were run."""
        # Arrange
        result = ExecutionResult(
            test_type=ExecutionType.UNIT,
            passed=0,
            failed=0,
            skipped=0,
            duration_seconds=0.0,
        )
        config = RunConfiguration(test_type=ExecutionType.UNIT)

        # Act
        self.service._display_test_results(result, config)

        # Assert
        self.mock_console.print_panel.assert_called_once()

    def test_display_test_results_with_negative_duration(self):
        """Test displaying results with negative duration (clock issue)."""
        # Arrange
        result = ExecutionResult(
            test_type=ExecutionType.UNIT,
            passed=10,
            failed=0,
            duration_seconds=-1.5,  # Negative duration
        )
        config = RunConfiguration(test_type=ExecutionType.UNIT)

        # Act
        self.service._display_test_results(result, config)

        # Assert - should handle gracefully
        self.mock_console.print_panel.assert_called_once()

    def test_display_test_results_with_none_coverage(self):
        """Test displaying results when coverage is None but expected."""
        # Arrange
        result = ExecutionResult(
            test_type=ExecutionType.UNIT,
            passed=10,
            failed=0,
            coverage_percentage=None,
            duration_seconds=1.0,
        )
        config = RunConfiguration(test_type=ExecutionType.UNIT, coverage=True, min_coverage=80.0)

        # Act
        self.service._display_test_results(result, config)

        # Assert - should not display coverage
        assert not any("Coverage" in str(call) for call in self.mock_console.print.call_args_list)

    def test_display_test_results_with_coverage_exactly_at_threshold(self):
        """Test displaying results when coverage exactly meets threshold."""
        # Arrange
        result = ExecutionResult(
            test_type=ExecutionType.UNIT,
            passed=10,
            failed=0,
            coverage_percentage=80.0,
            duration_seconds=1.0,
        )
        config = RunConfiguration(test_type=ExecutionType.UNIT, coverage=True, min_coverage=80.0)

        # Act
        self.service._display_test_results(result, config)

        # Assert - should show green color
        calls = self.mock_console.print.call_args_list
        coverage_call = [c for c in calls if "Coverage" in str(c)]
        assert len(coverage_call) > 0
        assert "green" in str(coverage_call[0])

    # Test run_continuous_tests edge cases
    @pytest.mark.asyncio
    async def test_run_continuous_tests_with_invalid_watch_path(self):
        """Test continuous tests with invalid watch path."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(1, "Path not found"))

        # Act
        await self.service.run_continuous_tests(watch_path="/nonexistent/path")

        # Assert
        self.mock_console.print_error.assert_called()

    @pytest.mark.asyncio
    async def test_run_continuous_tests_with_none_config(self):
        """Test continuous tests with None configuration."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(0, "Tests passed"))

        # Act
        await self.service.run_continuous_tests(test_config=None)

        # Assert - should use default config
        self.mock_console.print_success.assert_called_with("All tests passed!")

    @pytest.mark.asyncio
    async def test_run_continuous_tests_with_failing_tests(self):
        """Test continuous tests when tests fail."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(1, "Tests failed"))

        # Act
        await self.service.run_continuous_tests()

        # Assert
        self.mock_console.print_error.assert_called_with(
            "Some tests failed. Fix issues and tests will re-run."
        )

    # Test check_test_dependencies edge cases
    def test_check_dependencies_all_missing(self):
        """Test checking dependencies when all are missing."""
        # Arrange
        self.mock_process_executor.check_command_exists = Mock(return_value=False)

        # Act
        all_available, missing = self.service.check_test_dependencies()

        # Assert
        assert not all_available
        assert "pytest" in missing
        assert "coverage" in missing

    def test_check_dependencies_pytest_only_missing(self):
        """Test checking dependencies when only pytest is missing."""

        # Arrange
        def check_command(cmd):
            return cmd != "pytest"

        self.mock_process_executor.check_command_exists = Mock(side_effect=check_command)

        # Act
        all_available, missing = self.service.check_test_dependencies()

        # Assert
        assert not all_available
        assert "pytest" in missing
        assert "coverage" not in missing

    def test_check_dependencies_all_available(self):
        """Test checking dependencies when all are available."""
        # Arrange
        self.mock_process_executor.check_command_exists = Mock(return_value=True)

        # Act
        all_available, missing = self.service.check_test_dependencies()

        # Assert
        assert all_available
        assert len(missing) == 0

    def test_check_dependencies_with_exception(self):
        """Test checking dependencies when check raises exception."""
        # Arrange
        self.mock_process_executor.check_command_exists = Mock(
            side_effect=RuntimeError("Cannot check")
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="Cannot check"):
            self.service.check_test_dependencies()

    # Test orchestrator integration edge cases
    @pytest.mark.asyncio
    async def test_run_tests_orchestrator_prepare_failure(self):
        """Test when orchestrator fails to prepare environment."""
        # Arrange
        with patch.object(
            self.service._orchestrator,
            "prepare_test_environment",
            side_effect=RuntimeError("Cannot prepare environment"),
        ):
            # Act & Assert
            with pytest.raises(RuntimeError, match="Cannot prepare environment"):
                await self.service.run_tests(test_type="unit")

    @pytest.mark.asyncio
    async def test_run_tests_orchestrator_analyze_failure(self):
        """Test when orchestrator fails to analyze results."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(0, "output"))

        with patch.object(
            self.service._orchestrator,
            "analyze_test_results",
            side_effect=ValueError("Cannot analyze"),
        ):
            # Act & Assert
            with pytest.raises(ValueError, match="Cannot analyze"):
                await self.service.run_tests(test_type="unit")

    @pytest.mark.asyncio
    async def test_run_tests_with_validation_issues(self):
        """Test run_tests with various validation issues."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(0, "output"))

        validation_issues = [
            ValidationIssue(
                level=ValidationLevel.ERROR,
                category="COVERAGE",
                message="Coverage below threshold",
            ),
            ValidationIssue(
                level=ValidationLevel.WARNING,
                category="PERFORMANCE",
                message="Tests took too long",
            ),
            ValidationIssue(level=ValidationLevel.INFO, category="GENERAL", message="Info message"),
        ]

        with patch.object(
            self.service._orchestrator,
            "validate_test_results",
            return_value=validation_issues,
        ):
            # Act
            result = await self.service.run_tests(test_type="unit")

            # Assert
            self.mock_console.print_error.assert_any_call("COVERAGE: Coverage below threshold")
            self.mock_console.print_warning.assert_called_with("PERFORMANCE: Tests took too long")

    # Test concurrent execution edge cases
    @pytest.mark.asyncio
    async def test_run_tests_concurrent_calls(self):
        """Test multiple concurrent calls to run_tests."""
        # Arrange
        self.mock_process_executor.run_pytest = AsyncMock(return_value=(0, "Tests passed"))

        # Act - run multiple tests concurrently
        tasks = [
            self.service.run_tests(test_type="unit"),
            self.service.run_tests(test_type="integration"),
            self.service.run_tests(test_type="e2e"),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Assert
        assert len(results) == 3
        for result in results:
            if not isinstance(result, Exception):
                assert isinstance(result, ExecutionResult)

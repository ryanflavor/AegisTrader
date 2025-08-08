"""Test runner application service."""

from __future__ import annotations

import time

from aegis_sdk_dev.domain.models import ExecutionResult, ExecutionType, RunConfiguration
from aegis_sdk_dev.domain.services import TestOrchestrator
from aegis_sdk_dev.ports.console import ConsolePort
from aegis_sdk_dev.ports.process import ProcessExecutorPort


class TestExecutionService:
    """Application service for test execution use cases."""

    def __init__(
        self,
        console: ConsolePort,
        process_executor: ProcessExecutorPort,
    ):
        """Initialize test runner service.

        Args:
            console: Console port for output
            process_executor: Process executor port for running tests
        """
        self._console = console
        self._process_executor = process_executor
        self._orchestrator = TestOrchestrator()

    async def run_tests(
        self,
        test_type: str = "all",
        verbose: bool = False,
        coverage: bool = True,
        min_coverage: float = 80.0,
        test_path: str = "tests",
        markers: list[str] | None = None,
    ) -> ExecutionResult:
        """Run tests based on configuration.

        Args:
            test_type: Type of tests to run (unit, integration, e2e, all)
            verbose: Enable verbose output
            coverage: Generate coverage report
            min_coverage: Minimum coverage percentage required
            test_path: Path to test directory
            markers: Pytest markers to use

        Returns:
            ExecutionResult with execution details
        """
        # Create test configuration
        try:
            test_type_enum = ExecutionType(test_type)
        except ValueError:
            self._console.print_error(f"Invalid test type: {test_type}")
            self._console.print(f"Valid types: {', '.join([t.value for t in ExecutionType])}")
            raise

        config = RunConfiguration(
            test_type=test_type_enum,
            verbose=verbose,
            coverage=coverage,
            min_coverage=min_coverage,
            test_path=test_path,
            markers=markers or [],
        )

        # Display test configuration
        self._console.print(f"[cyan]Running {test_type} tests[/cyan]")
        if verbose:
            self._console.print("Verbose mode: ON")
        if coverage:
            self._console.print(f"Coverage report: ON (minimum: {min_coverage}%)")

        # Prepare test environment
        env = self._orchestrator.prepare_test_environment(config)
        pytest_args = env["pytest_args"]

        # Add test type specific markers
        if test_type_enum == ExecutionType.UNIT:
            pytest_args.extend(["-m", "not integration and not e2e"])
        elif test_type_enum == ExecutionType.INTEGRATION:
            pytest_args.extend(["-m", "integration"])
        elif test_type_enum == ExecutionType.E2E:
            pytest_args.extend(["-m", "e2e"])

        # Run tests
        start_time = time.time()
        try:
            exit_code, output = await self._process_executor.run_pytest(pytest_args, timeout=300.0)
        except TimeoutError:
            self._console.print_error("Test execution timed out after 5 minutes")
            return ExecutionResult(
                test_type=test_type_enum,
                failed=1,
                duration_seconds=300.0,
                errors=["Test execution timed out"],
            )

        duration = time.time() - start_time

        # Analyze results
        result = self._orchestrator.analyze_test_results(exit_code, output, duration, config)

        # Display results
        self._display_test_results(result, config)

        # Validate against criteria
        issues = self._orchestrator.validate_test_results(result, config)
        for issue in issues:
            if issue.level.value == "ERROR":
                self._console.print_error(f"{issue.category}: {issue.message}")
            elif issue.level.value == "WARNING":
                self._console.print_warning(f"{issue.category}: {issue.message}")

        return result

    def _display_test_results(self, result: ExecutionResult, config: RunConfiguration) -> None:
        """Display test results in a formatted manner.

        Args:
            result: Test execution result
            config: Test configuration
        """
        # Create summary
        status = "PASSED" if result.is_successful() else "FAILED"
        status_color = "green" if result.is_successful() else "red"

        self._console.print_panel(
            f"[{status_color} bold]{status}[/{status_color} bold]\n"
            f"Tests: {result.passed} passed, {result.failed} failed, {result.skipped} skipped\n"
            f"Duration: {result.duration_seconds:.2f}s",
            title=f"{config.test_type.value.upper()} Test Results",
            style=status_color,
        )

        # Display coverage if available
        if config.coverage and result.coverage_percentage is not None:
            coverage_color = (
                "green" if result.coverage_percentage >= config.min_coverage else "yellow"
            )
            self._console.print(
                f"\n[{coverage_color}]Coverage: {result.coverage_percentage:.1f}%[/{coverage_color}]"
            )

        # Display success rate
        if result.total_tests > 0:
            self._console.print(f"Success Rate: {result.success_rate:.1f}%")

    async def run_continuous_tests(
        self,
        watch_path: str = ".",
        test_config: RunConfiguration | None = None,
    ) -> None:
        """Run tests continuously, watching for file changes.

        Args:
            watch_path: Path to watch for changes
            test_config: Test configuration to use
        """
        self._console.print("[cyan]Starting continuous test runner[/cyan]")
        self._console.print(f"Watching: {watch_path}")
        self._console.print("Press Ctrl+C to stop")

        # This would typically integrate with a file watcher
        # For now, we'll just run tests once
        if test_config is None:
            test_config = RunConfiguration(
                test_type=ExecutionType.ALL,
                verbose=False,
                coverage=True,
            )

        result = await self.run_tests(
            test_type=test_config.test_type.value,
            verbose=test_config.verbose,
            coverage=test_config.coverage,
            min_coverage=test_config.min_coverage,
            test_path=test_config.test_path,
            markers=test_config.markers,
        )

        if result.is_successful():
            self._console.print_success("All tests passed!")
        else:
            self._console.print_error("Some tests failed. Fix issues and tests will re-run.")

    def check_test_dependencies(self) -> tuple[bool, list[str]]:
        """Check if all required test dependencies are available.

        Returns:
            Tuple of (all_available, list of missing dependencies)
        """
        missing = []

        # Check for pytest
        if not self._process_executor.check_command_exists("pytest"):
            missing.append("pytest")

        # Check for coverage
        if not self._process_executor.check_command_exists("coverage"):
            missing.append("coverage")

        all_available = len(missing) == 0
        return all_available, missing

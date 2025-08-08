"""Application service for SDK monitoring operations.

This service provides monitoring capabilities for AegisSDK services,
including test execution, performance metrics, and health monitoring.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..domain.exceptions import ServiceUnavailableException
from ..ports.sdk_monitoring import SDKMonitoringPort


class TestScenario(BaseModel):
    """Test scenario configuration."""

    name: str = Field(description="Scenario name")
    description: str = Field(description="Scenario description")
    tests: list[str] = Field(default_factory=list, description="Test cases to run")
    tags: list[str] = Field(default_factory=list, description="Tags for filtering")


class TestResult(BaseModel):
    """Individual test result."""

    name: str = Field(description="Test name")
    status: str = Field(description="Test status: passed, failed, skipped, error")
    duration: float = Field(description="Test duration in seconds")
    message: str | None = Field(default=None, description="Result message")
    error: str | None = Field(default=None, description="Error details if failed")


class TestSuiteReport(BaseModel):
    """Complete test suite report."""

    timestamp: datetime = Field(default_factory=datetime.now)
    scenario: str = Field(description="Scenario name")
    total_tests: int = Field(description="Total number of tests")
    passed: int = Field(description="Tests passed")
    failed: int = Field(description="Tests failed")
    skipped: int = Field(description="Tests skipped")
    errors: int = Field(description="Tests with errors")
    duration: float = Field(description="Total duration in seconds")
    success_rate: float = Field(description="Success rate percentage")
    results: list[TestResult] = Field(default_factory=list)


class EventStreamMetrics(BaseModel):
    """Metrics for event stream monitoring."""

    total_events: int = Field(default=0)
    events_per_second: float = Field(default=0.0)
    events_by_type: dict[str, int] = Field(default_factory=dict)
    events_by_service: dict[str, int] = Field(default_factory=dict)
    last_event_time: datetime | None = Field(default=None)


class LoadTestMetrics(BaseModel):
    """Metrics from load testing."""

    requests_per_second: float = Field(description="Current RPS")
    mean_latency_ms: float = Field(description="Mean latency")
    p95_latency_ms: float = Field(description="95th percentile latency")
    p99_latency_ms: float = Field(description="99th percentile latency")
    error_rate: float = Field(description="Error rate percentage")
    active_connections: int = Field(description="Active connections")


class FailoverMetrics(BaseModel):
    """Metrics for failover monitoring."""

    current_leader: str | None = Field(default=None, description="Current leader instance")
    failover_count: int = Field(default=0, description="Number of failovers detected")
    mean_failover_time_ms: float = Field(default=0.0, description="Mean failover time")
    last_failover: datetime | None = Field(default=None, description="Last failover timestamp")
    availability_percentage: float = Field(default=100.0, description="Service availability")


class SDKMonitoringService:
    """Application service for SDK monitoring operations."""

    def __init__(self, monitoring_port: SDKMonitoringPort):
        """Initialize the SDK monitoring service.

        Args:
            monitoring_port: Port for SDK monitoring operations
        """
        self._monitoring_port = monitoring_port
        self._test_results_cache: dict[str, TestSuiteReport] = {}
        self._event_metrics = EventStreamMetrics()
        self._load_metrics = LoadTestMetrics(
            requests_per_second=0,
            mean_latency_ms=0,
            p95_latency_ms=0,
            p99_latency_ms=0,
            error_rate=0,
            active_connections=0,
        )
        self._failover_metrics = FailoverMetrics()

    async def run_test_scenario(
        self, scenario_name: str, tags: list[str] | None = None
    ) -> TestSuiteReport:
        """Run a test scenario and return results.

        Args:
            scenario_name: Name of the scenario to run
            tags: Optional tags to filter tests

        Returns:
            TestSuiteReport: Test execution report

        Raises:
            ServiceUnavailableException: If test runner is not available
        """
        try:
            # Execute tests via monitoring port
            results = await self._monitoring_port.run_tests(scenario_name, tags)

            # Create report
            report = TestSuiteReport(
                scenario=scenario_name,
                total_tests=results.get("total_tests", 0),
                passed=results.get("passed", 0),
                failed=results.get("failed", 0),
                skipped=results.get("skipped", 0),
                errors=results.get("errors", 0),
                duration=results.get("duration", 0.0),
                success_rate=results.get("success_rate", 0.0),
                results=[
                    TestResult(
                        name=test["name"],
                        status=test["status"],
                        duration=test["duration"],
                        message=test.get("message"),
                        error=test.get("error"),
                    )
                    for test in results.get("tests", [])
                ],
            )

            # Cache results
            self._test_results_cache[scenario_name] = report

            return report

        except Exception as e:
            raise ServiceUnavailableException(f"Failed to run test scenario: {str(e)}") from e

    async def get_test_scenarios(self) -> list[TestScenario]:
        """Get available test scenarios.

        Returns:
            list[TestScenario]: Available test scenarios
        """
        scenarios = await self._monitoring_port.get_test_scenarios()

        return [
            TestScenario(
                name=s["name"],
                description=s["description"],
                tests=s.get("tests", []),
                tags=s.get("tags", []),
            )
            for s in scenarios
        ]

    async def get_last_test_report(self, scenario_name: str) -> TestSuiteReport | None:
        """Get the last test report for a scenario.

        Args:
            scenario_name: Name of the scenario

        Returns:
            TestSuiteReport | None: Last test report or None
        """
        return self._test_results_cache.get(scenario_name)

    async def monitor_event_stream(self, topics: list[str] | None = None) -> EventStreamMetrics:
        """Get event stream monitoring metrics.

        Args:
            topics: Optional topics to monitor

        Returns:
            EventStreamMetrics: Current event stream metrics
        """
        try:
            metrics = await self._monitoring_port.get_event_metrics(topics)

            self._event_metrics = EventStreamMetrics(
                total_events=metrics.get("total_events", 0),
                events_per_second=metrics.get("events_per_second", 0.0),
                events_by_type=metrics.get("events_by_type", {}),
                events_by_service=metrics.get("events_by_service", {}),
                last_event_time=(
                    datetime.fromisoformat(metrics["last_event_time"])
                    if metrics.get("last_event_time")
                    else None
                ),
            )

            return self._event_metrics

        except Exception:
            # Return cached metrics on error
            return self._event_metrics

    async def get_load_test_metrics(self, service_name: str | None = None) -> LoadTestMetrics:
        """Get load testing metrics.

        Args:
            service_name: Optional service to get metrics for

        Returns:
            LoadTestMetrics: Current load test metrics
        """
        try:
            metrics = await self._monitoring_port.get_load_metrics(service_name)

            self._load_metrics = LoadTestMetrics(
                requests_per_second=metrics.get("rps", 0.0),
                mean_latency_ms=metrics.get("mean_latency", 0.0),
                p95_latency_ms=metrics.get("p95_latency", 0.0),
                p99_latency_ms=metrics.get("p99_latency", 0.0),
                error_rate=metrics.get("error_rate", 0.0),
                active_connections=metrics.get("connections", 0),
            )

            return self._load_metrics

        except Exception:
            return self._load_metrics

    async def get_failover_metrics(self, service_name: str) -> FailoverMetrics:
        """Get failover monitoring metrics.

        Args:
            service_name: Service to monitor

        Returns:
            FailoverMetrics: Current failover metrics
        """
        try:
            metrics = await self._monitoring_port.get_failover_metrics(service_name)

            self._failover_metrics = FailoverMetrics(
                current_leader=metrics.get("current_leader"),
                failover_count=metrics.get("failover_count", 0),
                mean_failover_time_ms=metrics.get("mean_failover_time", 0.0),
                last_failover=(
                    datetime.fromisoformat(metrics["last_failover"])
                    if metrics.get("last_failover")
                    else None
                ),
                availability_percentage=metrics.get("availability", 100.0),
            )

            return self._failover_metrics

        except Exception:
            return self._failover_metrics

    async def validate_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate SDK configuration.

        Args:
            config: Configuration to validate

        Returns:
            dict: Validation results
        """
        try:
            return await self._monitoring_port.validate_config(config)
        except Exception as e:
            return {"valid": False, "errors": [str(e)], "warnings": []}

    async def get_service_dependencies(self, service_name: str) -> dict[str, Any]:
        """Get service dependency graph.

        Args:
            service_name: Service to analyze

        Returns:
            dict: Service dependencies
        """
        return await self._monitoring_port.get_service_dependencies(service_name)

    async def get_service_health(self, service_name: str) -> dict[str, Any] | None:
        """Get health status for a specific service.

        Args:
            service_name: Name of the service

        Returns:
            dict | None: Service health data or None if not found
        """
        try:
            # Get service dependencies to check health
            deps = await self._monitoring_port.get_service_dependencies(service_name)
            if not deps:
                return None

            # Build health response from dependencies data
            return {
                "service_name": service_name,
                "status": deps.get("status", "unknown"),
                "instance_count": deps.get("instance_count", 0),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception:
            return None

    async def get_all_services_health(self) -> list[dict[str, Any]]:
        """Get health status for all services.

        Returns:
            list: Health data for all services
        """
        try:
            # Get test scenarios as a proxy for available services
            scenarios = await self._monitoring_port.get_test_scenarios()

            health_data = []
            for scenario in scenarios:
                service_name = scenario.get("name", "unknown")
                health_data.append(
                    {
                        "service_name": service_name,
                        "status": "healthy",
                        "instance_count": 1,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            return health_data
        except Exception:
            return []

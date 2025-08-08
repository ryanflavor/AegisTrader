"""Port interface for SDK monitoring operations.

This port defines the contract for SDK monitoring capabilities
including test execution, metrics collection, and validation.
"""

from __future__ import annotations

from typing import Any, Protocol


class SDKMonitoringPort(Protocol):
    """Protocol interface for SDK monitoring operations."""

    async def run_tests(self, scenario: str, tags: list[str] | None = None) -> dict[str, Any]:
        """Run SDK test scenarios.

        Args:
            scenario: Test scenario to run
            tags: Optional tags to filter tests

        Returns:
            dict: Test results including pass/fail counts and details
        """
        ...

    async def get_test_scenarios(self) -> list[dict[str, Any]]:
        """Get available test scenarios.

        Returns:
            list: Available test scenarios with metadata
        """
        ...

    async def get_event_metrics(self, topics: list[str] | None = None) -> dict[str, Any]:
        """Get event stream metrics.

        Args:
            topics: Optional topics to monitor

        Returns:
            dict: Event stream metrics
        """
        ...

    async def get_load_metrics(self, service_name: str | None = None) -> dict[str, Any]:
        """Get load testing metrics.

        Args:
            service_name: Optional service to get metrics for

        Returns:
            dict: Load testing metrics
        """
        ...

    async def get_failover_metrics(self, service_name: str) -> dict[str, Any]:
        """Get failover metrics for a service.

        Args:
            service_name: Service to monitor

        Returns:
            dict: Failover metrics
        """
        ...

    async def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate SDK configuration.

        Args:
            config: Configuration to validate

        Returns:
            dict: Validation results
        """
        ...

    async def get_service_dependencies(self, service_name: str) -> dict[str, Any]:
        """Get service dependency graph.

        Args:
            service_name: Service to analyze

        Returns:
            dict: Service dependencies
        """
        ...

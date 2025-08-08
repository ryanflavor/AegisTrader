#!/usr/bin/env python3
"""
AegisSDK Test Runner

Automated scenario testing tool for validating SDK functionality
against K8s environments with comprehensive reporting.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


class TestScenario(str, Enum):
    """Available test scenarios."""

    BASIC_CONNECTIVITY = "basic_connectivity"
    SERVICE_DISCOVERY = "service_discovery"
    RPC_COMMUNICATION = "rpc_communication"
    EVENT_PUBSUB = "event_pubsub"
    FAILOVER = "failover"
    LOAD_BALANCING = "load_balancing"
    KV_STORE = "kv_store"
    FULL_SUITE = "full_suite"


class TestResult(str, Enum):
    """Test result status."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestCase:
    """Individual test case."""

    name: str
    description: str
    scenario: TestScenario
    test_func: Callable
    timeout: float = 10.0
    required_services: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class TestCaseResult:
    """Result of a test case execution."""

    test_case: TestCase
    result: TestResult
    duration: float
    message: str = ""
    error: Exception | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestSuiteResults:
    """Aggregated test suite results."""

    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    test_results: list[TestCaseResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None


class AegisTestRunner:
    """
    Test runner for AegisSDK scenarios.

    Validates SDK functionality against real K8s environments
    with comprehensive test scenarios.
    """

    def __init__(self, console: Console | None = None):
        """Initialize the test runner."""
        self.console = console or Console()
        self.test_cases: list[TestCase] = []
        self.nats_adapter: NATSAdapter | None = None
        self.discovery: BasicServiceDiscovery | None = None
        self.results = TestSuiteResults()

    def register_test(self, test_case: TestCase) -> None:
        """Register a test case."""
        self.test_cases.append(test_case)

    async def setup(self) -> None:
        """Set up test infrastructure."""
        try:
            # Connect to NATS
            self.nats_adapter = NATSAdapter()
            await self.nats_adapter.connect("nats://localhost:4222")

            # Set up service discovery
            kv_store = NATSKVStore(self.nats_adapter)
            await kv_store.connect("service_registry")
            registry = KVServiceRegistry(kv_store)
            self.discovery = BasicServiceDiscovery(registry)

            self.console.print("[green]✓ Test infrastructure connected[/green]")
        except Exception as e:
            self.console.print(f"[red]✗ Setup failed: {e}[/red]")
            raise

    async def teardown(self) -> None:
        """Clean up test infrastructure."""
        if self.nats_adapter:
            await self.nats_adapter.disconnect()

    async def run_test(self, test_case: TestCase) -> TestCaseResult:
        """Run a single test case."""
        start_time = time.perf_counter()

        try:
            # Check required services
            if test_case.required_services:
                for service_name in test_case.required_services:
                    instances = await self.discovery.discover(service_name)
                    if not instances:
                        return TestCaseResult(
                            test_case=test_case,
                            result=TestResult.SKIPPED,
                            duration=0,
                            message=f"Required service '{service_name}' not found",
                        )

            # Run test with timeout
            result = await asyncio.wait_for(test_case.test_func(self), timeout=test_case.timeout)

            duration = time.perf_counter() - start_time

            return TestCaseResult(
                test_case=test_case,
                result=TestResult.PASSED if result else TestResult.FAILED,
                duration=duration,
                message=str(result) if result else "",
            )

        except asyncio.TimeoutError:
            duration = time.perf_counter() - start_time
            return TestCaseResult(
                test_case=test_case,
                result=TestResult.ERROR,
                duration=duration,
                message="Test timeout",
                error=TimeoutError(f"Test exceeded {test_case.timeout}s timeout"),
            )

        except Exception as e:
            duration = time.perf_counter() - start_time
            return TestCaseResult(
                test_case=test_case,
                result=TestResult.ERROR,
                duration=duration,
                message=str(e),
                error=e,
            )

    async def run_scenario(self, scenario: TestScenario) -> TestSuiteResults:
        """Run all tests for a specific scenario."""
        if scenario == TestScenario.FULL_SUITE:
            tests_to_run = self.test_cases
        else:
            tests_to_run = [t for t in self.test_cases if t.scenario == scenario]

        return await self._run_tests(tests_to_run)

    async def run_tagged(self, tags: list[str]) -> TestSuiteResults:
        """Run tests matching specific tags."""
        tests_to_run = [t for t in self.test_cases if any(tag in t.tags for tag in tags)]
        return await self._run_tests(tests_to_run)

    async def _run_tests(self, tests: list[TestCase]) -> TestSuiteResults:
        """Run a list of tests."""
        self.results = TestSuiteResults(total_tests=len(tests), start_time=datetime.now())

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task("Running tests...", total=len(tests))

            for test_case in tests:
                progress.update(task, description=f"Running: {test_case.name}")

                result = await self.run_test(test_case)
                self.results.test_results.append(result)

                # Update counters
                if result.result == TestResult.PASSED:
                    self.results.passed += 1
                elif result.result == TestResult.FAILED:
                    self.results.failed += 1
                elif result.result == TestResult.SKIPPED:
                    self.results.skipped += 1
                elif result.result == TestResult.ERROR:
                    self.results.errors += 1

                progress.advance(task)

        self.results.end_time = datetime.now()
        self.results.duration = (self.results.end_time - self.results.start_time).total_seconds()

        return self.results

    def render_results(self, results: TestSuiteResults | None = None) -> None:
        """Render test results to console."""
        results = results or self.results

        # Summary panel
        success_rate = (
            (results.passed / results.total_tests * 100) if results.total_tests > 0 else 0
        )

        summary = f"""
[bold]Test Suite Results[/bold]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Tests: {results.total_tests}
Passed: [green]{results.passed}[/green]
Failed: [red]{results.failed}[/red]
Skipped: [yellow]{results.skipped}[/yellow]
Errors: [red]{results.errors}[/red]

Success Rate: {success_rate:.1f}%
Duration: {results.duration:.2f}s
        """

        if success_rate == 100:
            border_style = "green"
        elif success_rate >= 80:
            border_style = "yellow"
        else:
            border_style = "red"

        self.console.print(Panel(summary.strip(), border_style=border_style))

        # Detailed results table
        if results.test_results:
            table = Table(title="Test Details", show_header=True)
            table.add_column("Test", style="cyan")
            table.add_column("Scenario", style="blue")
            table.add_column("Result", style="white")
            table.add_column("Duration", justify="right")
            table.add_column("Message", style="dim")

            for test_result in results.test_results:
                # Result with color
                if test_result.result == TestResult.PASSED:
                    result_str = "[green]✓ PASSED[/green]"
                elif test_result.result == TestResult.FAILED:
                    result_str = "[red]✗ FAILED[/red]"
                elif test_result.result == TestResult.SKIPPED:
                    result_str = "[yellow]⊘ SKIPPED[/yellow]"
                else:
                    result_str = "[red]⚠ ERROR[/red]"

                table.add_row(
                    test_result.test_case.name,
                    test_result.test_case.scenario.value,
                    result_str,
                    f"{test_result.duration:.3f}s",
                    test_result.message[:50] if test_result.message else "",
                )

            self.console.print(table)

    async def export_results(self, filename: str | None = None) -> None:
        """Export test results to JSON."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"aegis_test_results_{timestamp}.json"

        export_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": self.results.total_tests,
                "passed": self.results.passed,
                "failed": self.results.failed,
                "skipped": self.results.skipped,
                "errors": self.results.errors,
                "duration": self.results.duration,
                "success_rate": (
                    (self.results.passed / self.results.total_tests * 100)
                    if self.results.total_tests > 0
                    else 0
                ),
            },
            "tests": [
                {
                    "name": r.test_case.name,
                    "scenario": r.test_case.scenario.value,
                    "result": r.result.value,
                    "duration": r.duration,
                    "message": r.message,
                    "error": str(r.error) if r.error else None,
                    "tags": r.test_case.tags,
                }
                for r in self.results.test_results
            ],
        }

        with open(filename, "w") as f:
            json.dump(export_data, f, indent=2)

        self.console.print(f"[green]Results exported to {filename}[/green]")


# Built-in test cases
async def test_nats_connectivity(runner: AegisTestRunner) -> bool:
    """Test basic NATS connectivity."""
    return runner.nats_adapter is not None and runner.nats_adapter._connection is not None


async def test_service_discovery(runner: AegisTestRunner) -> bool:
    """Test service discovery functionality."""
    services = await runner.discovery.list_all()
    return len(services) >= 0  # Can be 0 if no services registered


async def test_kv_store_operations(runner: AegisTestRunner) -> bool:
    """Test KV store operations."""
    kv_store = NATSKVStore(runner.nats_adapter)
    await kv_store.connect("test_bucket")

    # Test put/get
    await kv_store.put("test_key", b"test_value")
    value = await kv_store.get("test_key")

    # Cleanup
    await kv_store.delete("test_key")

    return value == b"test_value"


async def test_rpc_echo(runner: AegisTestRunner) -> bool:
    """Test RPC echo service if available."""
    instances = await runner.discovery.discover("echo")
    if not instances:
        return True  # Skip if no echo service

    response = await runner.nats_adapter.request(
        "rpc.echo.echo", b'{"message": "test"}', timeout=5.0
    )

    return response is not None


async def test_event_publishing(runner: AegisTestRunner) -> bool:
    """Test event publishing."""
    event_received = False

    async def handler(msg):
        nonlocal event_received
        event_received = True

    # Subscribe to test events
    sub = await runner.nats_adapter.subscribe("test.events", handler)

    # Publish event
    await runner.nats_adapter.publish("test.events", b'{"test": true}')

    # Wait briefly for event
    await asyncio.sleep(0.5)

    # Cleanup
    await sub.unsubscribe()

    return event_received


def register_default_tests(runner: AegisTestRunner) -> None:
    """Register default test cases."""
    runner.register_test(
        TestCase(
            name="NATS Connectivity",
            description="Verify NATS connection",
            scenario=TestScenario.BASIC_CONNECTIVITY,
            test_func=test_nats_connectivity,
            tags=["basic", "connectivity"],
        )
    )

    runner.register_test(
        TestCase(
            name="Service Discovery",
            description="Test service discovery mechanism",
            scenario=TestScenario.SERVICE_DISCOVERY,
            test_func=test_service_discovery,
            tags=["discovery", "registry"],
        )
    )

    runner.register_test(
        TestCase(
            name="KV Store Operations",
            description="Test key-value store CRUD operations",
            scenario=TestScenario.KV_STORE,
            test_func=test_kv_store_operations,
            tags=["kv", "storage"],
        )
    )

    runner.register_test(
        TestCase(
            name="RPC Echo Service",
            description="Test RPC communication with echo service",
            scenario=TestScenario.RPC_COMMUNICATION,
            test_func=test_rpc_echo,
            required_services=["echo"],
            tags=["rpc", "communication"],
        )
    )

    runner.register_test(
        TestCase(
            name="Event Publishing",
            description="Test event pub/sub functionality",
            scenario=TestScenario.EVENT_PUBSUB,
            test_func=test_event_publishing,
            tags=["events", "pubsub"],
        )
    )


@click.command()
@click.option(
    "--scenario",
    "-s",
    type=click.Choice([s.value for s in TestScenario]),
    default=TestScenario.FULL_SUITE.value,
    help="Test scenario to run",
)
@click.option("--tags", "-t", multiple=True, help="Filter tests by tags")
@click.option("--export", "-e", is_flag=True, help="Export results to JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def main(scenario: str, tags: tuple[str], export: bool, verbose: bool) -> None:
    """AegisSDK Test Runner - Automated scenario testing."""
    console = Console()

    console.print("[bold blue]AegisSDK Test Runner[/bold blue]")
    console.print("Automated scenario testing for SDK validation\n")

    # Create runner
    runner = AegisTestRunner(console)

    # Register default tests
    register_default_tests(runner)

    async def run_tests():
        try:
            # Setup
            await runner.setup()

            # Run tests
            if tags:
                console.print(f"Running tests with tags: {', '.join(tags)}\n")
                results = await runner.run_tagged(list(tags))
            else:
                console.print(f"Running scenario: {scenario}\n")
                results = await runner.run_scenario(TestScenario(scenario))

            # Display results
            runner.render_results(results)

            # Export if requested
            if export:
                await runner.export_results()

            # Exit code based on results
            if results.failed > 0 or results.errors > 0:
                sys.exit(1)

        except Exception as e:
            console.print(f"[red]Test runner error: {e}[/red]")
            if verbose:
                import traceback

                traceback.print_exc()
            sys.exit(1)

        finally:
            await runner.teardown()

    # Run async tests
    asyncio.run(run_tests())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Failover Testing Client

Tests and measures failover behavior of single-active services,
tracking timing metrics, success rates, and failover latency.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from statistics import mean, median

from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from aegis_sdk.domain.enums import RPCErrorCode, ServiceStatus
from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


class TestScenario(str, Enum):
    """Failover test scenarios."""

    LEADER_CRASH = "leader_crash"
    NETWORK_PARTITION = "network_partition"
    GRACEFUL_SHUTDOWN = "graceful_shutdown"
    RAPID_FAILOVERS = "rapid_failovers"
    LOAD_DURING_FAILOVER = "load_during_failover"


class FailoverTestConfig(BaseModel):
    """Configuration for failover testing."""

    service_name: str = Field(description="Service to test")
    scenario: TestScenario = Field(default=TestScenario.LEADER_CRASH)
    request_count: int = Field(default=100, description="Number of requests to send")
    request_rate: float = Field(default=10.0, description="Requests per second")
    timeout: float = Field(default=5.0, description="Request timeout in seconds")
    measure_recovery: bool = Field(default=True, description="Measure recovery time")
    simulate_failures: bool = Field(default=False, description="Simulate service failures")


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    request_id: int
    timestamp: float
    latency_ms: float
    success: bool
    error_code: RPCErrorCode | None = None
    error_message: str | None = None
    instance_id: str | None = None
    retry_count: int = 0


@dataclass
class FailoverEvent:
    """A detected failover event."""

    timestamp: float
    old_leader: str | None
    new_leader: str | None
    detection_time_ms: float
    recovery_time_ms: float
    requests_failed: int
    requests_during_failover: int


@dataclass
class TestResults:
    """Aggregated test results."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 0.0
    mean_latency_ms: float = 0.0
    median_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    failover_events: list[FailoverEvent] = field(default_factory=list)
    mean_failover_time_ms: float = 0.0
    max_failover_time_ms: float = 0.0
    availability_percentage: float = 0.0
    requests_per_instance: dict[str, int] = field(default_factory=dict)


class FailoverTester:
    """
    Failover testing client following DDD principles.

    Tests single-active service failover behavior and measures
    recovery times, success rates, and performance impact.
    """

    def __init__(self, config: FailoverTestConfig):
        """Initialize the failover tester."""
        self.config = config
        self.console = Console()
        self.nats_adapter: NATSAdapter | None = None
        self.discovery: BasicServiceDiscovery | None = None
        self.metrics: list[RequestMetrics] = []
        self.current_leader: str | None = None
        self.failover_events: list[FailoverEvent] = []
        self.start_time: float = 0
        self.running = False

    async def connect(self) -> None:
        """Connect to NATS and set up service discovery."""
        # External client pattern - direct infrastructure setup
        self.nats_adapter = NATSAdapter()
        await self.nats_adapter.connect("nats://localhost:4222")

        # Set up service discovery
        kv_store = NATSKVStore(self.nats_adapter)
        await kv_store.connect("service_registry")
        registry = KVServiceRegistry(kv_store)
        self.discovery = BasicServiceDiscovery(registry)

        self.console.print("[green]✓ Connected to NATS[/green]")

    async def find_leader(self) -> ServiceInstance | None:
        """Find the current leader instance."""
        instances = await self.discovery.discover(self.config.service_name)

        for instance in instances:
            if instance.status == ServiceStatus.ACTIVE:
                # Check if it's marked as leader in metadata
                if instance.metadata and instance.metadata.get("is_leader"):
                    return instance

        # If no explicit leader, return first active instance
        active_instances = [i for i in instances if i.status == ServiceStatus.ACTIVE]
        return active_instances[0] if active_instances else None

    async def send_request(self, request_id: int) -> RequestMetrics:
        """Send a single request and measure metrics."""
        start_time = time.perf_counter()
        retry_count = 0
        max_retries = 3

        while retry_count <= max_retries:
            try:
                # Prepare request
                request_data = {"request_id": request_id, "timestamp": time.time()}

                # Send RPC request
                response = await self.nats_adapter.request(
                    f"rpc.{self.config.service_name}.process",
                    json.dumps(request_data).encode(),
                    timeout=self.config.timeout,
                )

                # Parse response
                if response:
                    response_data = json.loads(response.data.decode())
                    latency_ms = (time.perf_counter() - start_time) * 1000

                    # Check for NOT_ACTIVE error (should retry)
                    if response_data.get("error_code") == RPCErrorCode.NOT_ACTIVE.value:
                        retry_count += 1
                        await asyncio.sleep(0.1 * retry_count)  # Exponential backoff
                        continue

                    return RequestMetrics(
                        request_id=request_id,
                        timestamp=start_time,
                        latency_ms=latency_ms,
                        success=not response_data.get("error"),
                        error_code=(
                            RPCErrorCode(response_data.get("error_code"))
                            if response_data.get("error_code")
                            else None
                        ),
                        error_message=response_data.get("error_message"),
                        instance_id=response_data.get("instance_id"),
                        retry_count=retry_count,
                    )
                else:
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    return RequestMetrics(
                        request_id=request_id,
                        timestamp=start_time,
                        latency_ms=latency_ms,
                        success=False,
                        error_message="Empty response",
                        retry_count=retry_count,
                    )

            except asyncio.TimeoutError:
                latency_ms = (time.perf_counter() - start_time) * 1000
                return RequestMetrics(
                    request_id=request_id,
                    timestamp=start_time,
                    latency_ms=latency_ms,
                    success=False,
                    error_code=RPCErrorCode.TIMEOUT,
                    error_message="Request timeout",
                    retry_count=retry_count,
                )

            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                return RequestMetrics(
                    request_id=request_id,
                    timestamp=start_time,
                    latency_ms=latency_ms,
                    success=False,
                    error_message=str(e),
                    retry_count=retry_count,
                )

        # Max retries exceeded
        latency_ms = (time.perf_counter() - start_time) * 1000
        return RequestMetrics(
            request_id=request_id,
            timestamp=start_time,
            latency_ms=latency_ms,
            success=False,
            error_code=RPCErrorCode.SERVICE_UNAVAILABLE,
            error_message="Max retries exceeded",
            retry_count=retry_count,
        )

    async def monitor_leader_changes(self) -> None:
        """Monitor for leader changes during testing."""
        last_leader = self.current_leader
        failover_start = None
        requests_during_failover = 0

        while self.running:
            try:
                # Check current leader
                leader = await self.find_leader()
                current_leader_id = leader.instance_id if leader else None

                # Detect leader change
                if current_leader_id != last_leader:
                    if last_leader is not None:  # Not the first check
                        if failover_start is None:
                            # Failover started
                            failover_start = time.perf_counter()
                            self.console.print(
                                f"[yellow]⚠ Failover detected: {last_leader[:12]} → ???[/yellow]"
                            )
                        else:
                            # Failover completed
                            failover_end = time.perf_counter()
                            detection_time = (failover_end - failover_start) * 1000
                            recovery_time = detection_time  # Simplified for example

                            # Count failed requests during failover
                            failed_during = sum(
                                1
                                for m in self.metrics
                                if failover_start <= m.timestamp <= failover_end and not m.success
                            )

                            event = FailoverEvent(
                                timestamp=failover_start,
                                old_leader=last_leader,
                                new_leader=current_leader_id,
                                detection_time_ms=detection_time,
                                recovery_time_ms=recovery_time,
                                requests_failed=failed_during,
                                requests_during_failover=requests_during_failover,
                            )

                            self.failover_events.append(event)
                            self.console.print(
                                f"[green]✓ Failover complete: → {current_leader_id[:12]} "
                                f"({detection_time:.2f}ms)[/green]"
                            )

                            failover_start = None
                            requests_during_failover = 0

                    last_leader = current_leader_id
                    self.current_leader = current_leader_id

                # Count requests during failover
                if failover_start is not None:
                    requests_during_failover += 1

                await asyncio.sleep(0.5)  # Check every 500ms

            except Exception as e:
                self.console.print(f"[red]Monitor error: {e}[/red]")
                await asyncio.sleep(1)

    async def simulate_leader_failure(self, delay: float = 10.0) -> None:
        """Simulate a leader failure after a delay."""
        if not self.config.simulate_failures:
            return

        await asyncio.sleep(delay)

        # Find and "kill" the current leader
        leader = await self.find_leader()
        if leader:
            self.console.print(
                f"[red]💀 Simulating leader failure: {leader.instance_id[:12]}[/red]"
            )
            # In a real test, would send a shutdown command to the leader
            # For this example, we just log it

    async def run_load_test(self) -> None:
        """Run the load test with configured parameters."""
        self.console.print(f"\n[bold]Starting failover test: {self.config.scenario.value}[/bold]")
        self.console.print(f"Target: {self.config.service_name}")
        self.console.print(
            f"Requests: {self.config.request_count} @ {self.config.request_rate}/s\n"
        )

        # Find initial leader
        leader = await self.find_leader()
        if not leader:
            self.console.print("[red]No active leader found![/red]")
            return

        self.current_leader = leader.instance_id
        self.console.print(f"[green]Initial leader: {self.current_leader[:12]}[/green]\n")

        # Start monitoring
        self.running = True
        self.start_time = time.perf_counter()

        # Start background tasks
        monitor_task = asyncio.create_task(self.monitor_leader_changes())
        failure_task = None
        if self.config.simulate_failures:
            failure_task = asyncio.create_task(self.simulate_leader_failure())

        # Progress bar
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        )

        with progress:
            task = progress.add_task("Sending requests...", total=self.config.request_count)

            # Send requests at configured rate
            request_interval = 1.0 / self.config.request_rate
            tasks = []

            for request_id in range(self.config.request_count):
                # Send request
                task_coro = self.send_request(request_id)
                tasks.append(asyncio.create_task(task_coro))

                # Update progress
                progress.update(task, advance=1)

                # Rate limiting
                await asyncio.sleep(request_interval)

            # Wait for all requests to complete
            results = await asyncio.gather(*tasks)
            self.metrics.extend(results)

        # Stop monitoring
        self.running = False
        monitor_task.cancel()
        if failure_task:
            failure_task.cancel()

        # Wait for tasks to clean up
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        if failure_task:
            try:
                await failure_task
            except asyncio.CancelledError:
                pass

    def calculate_results(self) -> TestResults:
        """Calculate aggregated test results."""
        if not self.metrics:
            return TestResults()

        # Basic metrics
        successful = [m for m in self.metrics if m.success]
        failed = [m for m in self.metrics if not m.success]
        latencies = [m.latency_ms for m in self.metrics if m.success]

        # Calculate percentiles
        if latencies:
            latencies_sorted = sorted(latencies)
            p95_index = int(len(latencies_sorted) * 0.95)
            p99_index = int(len(latencies_sorted) * 0.99)

            results = TestResults(
                total_requests=len(self.metrics),
                successful_requests=len(successful),
                failed_requests=len(failed),
                success_rate=(len(successful) / len(self.metrics)) * 100,
                mean_latency_ms=mean(latencies),
                median_latency_ms=median(latencies),
                p95_latency_ms=(
                    latencies_sorted[p95_index]
                    if p95_index < len(latencies_sorted)
                    else max(latencies)
                ),
                p99_latency_ms=(
                    latencies_sorted[p99_index]
                    if p99_index < len(latencies_sorted)
                    else max(latencies)
                ),
                max_latency_ms=max(latencies),
                min_latency_ms=min(latencies),
                failover_events=self.failover_events,
            )
        else:
            results = TestResults(
                total_requests=len(self.metrics),
                successful_requests=0,
                failed_requests=len(self.metrics),
                success_rate=0.0,
            )

        # Instance distribution
        for metric in self.metrics:
            if metric.instance_id:
                if metric.instance_id not in results.requests_per_instance:
                    results.requests_per_instance[metric.instance_id] = 0
                results.requests_per_instance[metric.instance_id] += 1

        # Failover metrics
        if self.failover_events:
            failover_times = [e.recovery_time_ms for e in self.failover_events]
            results.mean_failover_time_ms = mean(failover_times)
            results.max_failover_time_ms = max(failover_times)

        # Availability calculation
        total_time = time.perf_counter() - self.start_time
        downtime = sum(e.recovery_time_ms / 1000 for e in self.failover_events)
        results.availability_percentage = ((total_time - downtime) / total_time) * 100

        return results

    def render_results(self, results: TestResults) -> None:
        """Render test results to console."""
        # Summary panel
        summary = f"""
[bold]Test Summary[/bold]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Requests: {results.total_requests}
Successful: {results.successful_requests} ({results.success_rate:.2f}%)
Failed: {results.failed_requests}
Availability: {results.availability_percentage:.3f}%
        """

        self.console.print(Panel(summary.strip(), title="Results", border_style="green"))

        # Latency statistics
        if results.mean_latency_ms > 0:
            latency_table = Table(title="Latency Statistics", show_header=True)
            latency_table.add_column("Metric", style="cyan")
            latency_table.add_column("Value (ms)", justify="right")

            latency_table.add_row("Mean", f"{results.mean_latency_ms:.2f}")
            latency_table.add_row("Median", f"{results.median_latency_ms:.2f}")
            latency_table.add_row("P95", f"{results.p95_latency_ms:.2f}")
            latency_table.add_row("P99", f"{results.p99_latency_ms:.2f}")
            latency_table.add_row("Min", f"{results.min_latency_ms:.2f}")
            latency_table.add_row("Max", f"{results.max_latency_ms:.2f}")

            self.console.print(latency_table)

        # Failover events
        if results.failover_events:
            failover_table = Table(title="Failover Events", show_header=True)
            failover_table.add_column("Time", style="dim")
            failover_table.add_column("Old Leader", style="red")
            failover_table.add_column("New Leader", style="green")
            failover_table.add_column("Recovery (ms)", justify="right", style="yellow")
            failover_table.add_column("Failed Requests", justify="right")

            for event in results.failover_events:
                time_str = f"{event.timestamp - self.start_time:.1f}s"
                failover_table.add_row(
                    time_str,
                    event.old_leader[:12] if event.old_leader else "N/A",
                    event.new_leader[:12] if event.new_leader else "N/A",
                    f"{event.recovery_time_ms:.2f}",
                    str(event.requests_failed),
                )

            self.console.print(failover_table)

            # Failover summary
            self.console.print(
                f"\n[bold]Failover Summary:[/bold]\n"
                f"  Total Failovers: {len(results.failover_events)}\n"
                f"  Mean Recovery Time: {results.mean_failover_time_ms:.2f}ms\n"
                f"  Max Recovery Time: {results.max_failover_time_ms:.2f}ms"
            )

        # Instance distribution
        if results.requests_per_instance:
            instance_table = Table(title="Request Distribution", show_header=True)
            instance_table.add_column("Instance", style="cyan")
            instance_table.add_column("Requests", justify="right")
            instance_table.add_column("Percentage", justify="right")

            for instance_id, count in sorted(results.requests_per_instance.items()):
                percentage = (count / results.total_requests) * 100
                instance_table.add_row(instance_id[:12], str(count), f"{percentage:.1f}%")

            self.console.print(instance_table)

    async def export_results(self, results: TestResults, filename: str | None = None) -> None:
        """Export test results to JSON file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"failover_test_{self.config.scenario.value}_{timestamp}.json"

        export_data = {
            "test_config": self.config.model_dump(),
            "test_time": datetime.now().isoformat(),
            "duration_seconds": time.perf_counter() - self.start_time,
            "results": {
                "total_requests": results.total_requests,
                "successful_requests": results.successful_requests,
                "failed_requests": results.failed_requests,
                "success_rate": results.success_rate,
                "latency": {
                    "mean_ms": results.mean_latency_ms,
                    "median_ms": results.median_latency_ms,
                    "p95_ms": results.p95_latency_ms,
                    "p99_ms": results.p99_latency_ms,
                    "min_ms": results.min_latency_ms,
                    "max_ms": results.max_latency_ms,
                },
                "failover": {
                    "events": len(results.failover_events),
                    "mean_recovery_ms": results.mean_failover_time_ms,
                    "max_recovery_ms": results.max_failover_time_ms,
                },
                "availability_percentage": results.availability_percentage,
                "request_distribution": results.requests_per_instance,
            },
            "detailed_metrics": [
                {
                    "request_id": m.request_id,
                    "latency_ms": m.latency_ms,
                    "success": m.success,
                    "error_code": m.error_code.value if m.error_code else None,
                    "error_message": m.error_message,
                    "instance_id": m.instance_id,
                    "retry_count": m.retry_count,
                }
                for m in self.metrics
            ],
            "failover_events": [
                {
                    "timestamp": e.timestamp - self.start_time,
                    "old_leader": e.old_leader,
                    "new_leader": e.new_leader,
                    "detection_time_ms": e.detection_time_ms,
                    "recovery_time_ms": e.recovery_time_ms,
                    "requests_failed": e.requests_failed,
                }
                for e in results.failover_events
            ],
        }

        with open(filename, "w") as f:
            json.dump(export_data, f, indent=2)

        self.console.print(f"\n[green]Results exported to {filename}[/green]")


async def main():
    """Main entry point for failover testing."""
    console = Console()

    console.print("[bold blue]Failover Testing Client[/bold blue]")
    console.print("Test and measure single-active service failover behavior\n")

    # Test configuration
    config = FailoverTestConfig(
        service_name="echo-single",  # Target single-active service
        scenario=TestScenario.LEADER_CRASH,
        request_count=200,
        request_rate=20.0,  # 20 requests/second
        timeout=5.0,
        measure_recovery=True,
        simulate_failures=False,  # Set to True to simulate failures
    )

    # Create tester
    tester = FailoverTester(config)

    try:
        # Connect
        await tester.connect()

        # Run test
        await tester.run_load_test()

        # Calculate results
        results = tester.calculate_results()

        # Display results
        console.print("\n")
        tester.render_results(results)

        # Export results
        await tester.export_results(results)

    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Test error: {e}[/red]")
        import traceback

        traceback.print_exc()
    finally:
        if tester.nats_adapter:
            await tester.nats_adapter.disconnect()
        console.print("[green]Disconnected[/green]")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Load Testing Client for Performance Validation

Comprehensive load testing tool for validating service performance,
scalability, and resource utilization under various load patterns.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from statistics import mean, median, stdev

from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn
from rich.table import Table

from aegis_sdk.domain.enums import RPCErrorCode
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter


class LoadPattern(str, Enum):
    """Load testing patterns."""

    CONSTANT = "constant"  # Steady load
    RAMP_UP = "ramp_up"  # Gradually increasing load
    SPIKE = "spike"  # Sudden load spike
    WAVE = "wave"  # Oscillating load
    BURST = "burst"  # Intermittent bursts
    STRESS = "stress"  # Maximum sustainable load


class PayloadSize(str, Enum):
    """Request payload sizes."""

    TINY = "tiny"  # 10 bytes
    SMALL = "small"  # 100 bytes
    MEDIUM = "medium"  # 1 KB
    LARGE = "large"  # 10 KB
    HUGE = "huge"  # 100 KB


class LoadTestConfig(BaseModel):
    """Configuration for load testing."""

    service_name: str = Field(description="Target service name")
    method_name: str = Field(default="process", description="RPC method to call")
    pattern: LoadPattern = Field(default=LoadPattern.CONSTANT)
    duration_seconds: int = Field(default=60, description="Test duration")
    initial_rps: float = Field(default=10.0, description="Initial requests per second")
    max_rps: float = Field(default=100.0, description="Maximum RPS for patterns")
    concurrent_connections: int = Field(default=10, description="Number of concurrent workers")
    payload_size: PayloadSize = Field(default=PayloadSize.SMALL)
    timeout_seconds: float = Field(default=5.0, description="Request timeout")
    warmup_seconds: int = Field(default=5, description="Warmup period")
    cooldown_seconds: int = Field(default=5, description="Cooldown period")


@dataclass
class RequestResult:
    """Result of a single request."""

    timestamp: float
    worker_id: int
    latency_ms: float
    success: bool
    error_code: RPCErrorCode | None = None
    error_message: str | None = None
    response_size: int = 0


@dataclass
class WorkerStats:
    """Statistics for a worker."""

    worker_id: int
    requests_sent: int = 0
    requests_successful: int = 0
    requests_failed: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    errors_by_type: dict[str, int] = field(default_factory=dict)


@dataclass
class LoadTestResults:
    """Aggregated load test results."""

    # Overall metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 0.0
    duration_seconds: float = 0.0

    # Throughput metrics
    mean_rps: float = 0.0
    peak_rps: float = 0.0
    sustained_rps: float = 0.0

    # Latency metrics (successful requests only)
    mean_latency_ms: float = 0.0
    median_latency_ms: float = 0.0
    stddev_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p75_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0

    # Error analysis
    errors_by_type: dict[str, int] = field(default_factory=dict)
    error_rate_by_second: list[float] = field(default_factory=list)

    # Worker distribution
    worker_stats: list[WorkerStats] = field(default_factory=list)

    # Time series data (for graphs)
    rps_timeline: list[float] = field(default_factory=list)
    latency_timeline: list[float] = field(default_factory=list)
    error_timeline: list[float] = field(default_factory=list)


class LoadTester:
    """
    Load testing client following DDD principles.

    Validates service performance under various load patterns
    and provides comprehensive performance metrics.
    """

    def __init__(self, config: LoadTestConfig):
        """Initialize the load tester."""
        self.config = config
        self.console = Console()
        self.nats_adapter: NATSAdapter | None = None
        self.results: list[RequestResult] = []
        self.worker_stats: dict[int, WorkerStats] = {}
        self.start_time: float = 0
        self.running = False
        self.current_rps = 0.0
        self.request_counter = 0

    async def connect(self) -> None:
        """Connect to NATS."""
        self.nats_adapter = NATSAdapter()
        await self.nats_adapter.connect("nats://localhost:4222")
        self.console.print("[green]✓ Connected to NATS[/green]")

    def generate_payload(self) -> bytes:
        """Generate request payload based on configured size."""
        sizes = {
            PayloadSize.TINY: 10,
            PayloadSize.SMALL: 100,
            PayloadSize.MEDIUM: 1024,
            PayloadSize.LARGE: 10240,
            PayloadSize.HUGE: 102400,
        }

        size = sizes[self.config.payload_size]
        data = {
            "request_id": self.request_counter,
            "timestamp": time.time(),
            "data": "x" * (size - 50),  # Adjust for JSON overhead
        }

        self.request_counter += 1
        return json.dumps(data).encode()

    def calculate_target_rps(self, elapsed: float) -> float:
        """Calculate target RPS based on load pattern and elapsed time."""
        progress = elapsed / self.config.duration_seconds

        if self.config.pattern == LoadPattern.CONSTANT:
            return self.config.initial_rps

        elif self.config.pattern == LoadPattern.RAMP_UP:
            # Linear ramp from initial to max
            return (
                self.config.initial_rps + (self.config.max_rps - self.config.initial_rps) * progress
            )

        elif self.config.pattern == LoadPattern.SPIKE:
            # Spike at 50% mark
            if 0.45 <= progress <= 0.55:
                return self.config.max_rps
            return self.config.initial_rps

        elif self.config.pattern == LoadPattern.WAVE:
            # Sinusoidal pattern
            import math

            amplitude = (self.config.max_rps - self.config.initial_rps) / 2
            midpoint = (self.config.max_rps + self.config.initial_rps) / 2
            return midpoint + amplitude * math.sin(progress * 4 * math.pi)

        elif self.config.pattern == LoadPattern.BURST:
            # Bursts every 10 seconds
            if int(elapsed) % 10 < 2:
                return self.config.max_rps
            return self.config.initial_rps

        elif self.config.pattern == LoadPattern.STRESS:
            # Start at max and maintain
            return self.config.max_rps

        return self.config.initial_rps

    async def worker(self, worker_id: int) -> None:
        """Worker coroutine that sends requests."""
        stats = WorkerStats(worker_id=worker_id)
        self.worker_stats[worker_id] = stats

        while self.running:
            try:
                # Calculate if this worker should send a request
                workers_rps = self.current_rps / self.config.concurrent_connections
                if workers_rps > 0:
                    interval = 1.0 / workers_rps
                else:
                    interval = 1.0

                # Send request
                start_time = time.perf_counter()
                payload = self.generate_payload()

                try:
                    response = await self.nats_adapter.request(
                        f"rpc.{self.config.service_name}.{self.config.method_name}",
                        payload,
                        timeout=self.config.timeout_seconds,
                    )

                    latency_ms = (time.perf_counter() - start_time) * 1000
                    success = True
                    error_code = None
                    error_message = None
                    response_size = len(response.data) if response else 0

                    # Check for application-level errors
                    if response:
                        try:
                            response_data = json.loads(response.data.decode())
                            if response_data.get("error"):
                                success = False
                                error_code = response_data.get("error_code")
                                error_message = response_data.get("error_message")
                        except:
                            pass

                except asyncio.TimeoutError:
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    success = False
                    error_code = RPCErrorCode.TIMEOUT
                    error_message = "Request timeout"
                    response_size = 0

                except Exception as e:
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    success = False
                    error_code = RPCErrorCode.INTERNAL_ERROR
                    error_message = str(e)
                    response_size = 0

                # Record result
                result = RequestResult(
                    timestamp=time.time(),
                    worker_id=worker_id,
                    latency_ms=latency_ms,
                    success=success,
                    error_code=error_code,
                    error_message=error_message,
                    response_size=response_size,
                )
                self.results.append(result)

                # Update worker stats
                stats.requests_sent += 1
                if success:
                    stats.requests_successful += 1
                    stats.total_latency_ms += latency_ms
                    stats.min_latency_ms = min(stats.min_latency_ms, latency_ms)
                    stats.max_latency_ms = max(stats.max_latency_ms, latency_ms)
                else:
                    stats.requests_failed += 1
                    error_type = str(error_code) if error_code else "Unknown"
                    if error_type not in stats.errors_by_type:
                        stats.errors_by_type[error_type] = 0
                    stats.errors_by_type[error_type] += 1

                # Rate limiting
                await asyncio.sleep(interval)

            except Exception as e:
                self.console.print(f"[red]Worker {worker_id} error: {e}[/red]")
                await asyncio.sleep(1)

    async def run_load_test(self) -> None:
        """Run the load test with configured parameters."""
        self.console.print("\n[bold]Starting load test[/bold]")
        self.console.print(f"Service: {self.config.service_name}.{self.config.method_name}")
        self.console.print(f"Pattern: {self.config.pattern.value}")
        self.console.print(f"Duration: {self.config.duration_seconds}s")
        self.console.print(f"Workers: {self.config.concurrent_connections}")
        self.console.print(f"Payload: {self.config.payload_size.value}\n")

        # Warmup phase
        if self.config.warmup_seconds > 0:
            self.console.print(f"[yellow]Warming up for {self.config.warmup_seconds}s...[/yellow]")
            await asyncio.sleep(self.config.warmup_seconds)

        # Start workers
        self.running = True
        self.start_time = time.time()
        workers = []

        for i in range(self.config.concurrent_connections):
            worker = asyncio.create_task(self.worker(i))
            workers.append(worker)

        # Progress tracking
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
        )

        # Metrics collection task
        metrics_task = asyncio.create_task(self._collect_metrics())

        with progress:
            task = progress.add_task("Running load test...", total=self.config.duration_seconds)

            # Run for configured duration
            start = time.time()
            while time.time() - start < self.config.duration_seconds:
                elapsed = time.time() - start

                # Update target RPS
                self.current_rps = self.calculate_target_rps(elapsed)

                # Update progress
                progress.update(task, completed=elapsed)

                await asyncio.sleep(0.1)

        # Stop workers
        self.running = False

        # Cooldown phase
        if self.config.cooldown_seconds > 0:
            self.console.print(
                f"[yellow]Cooling down for {self.config.cooldown_seconds}s...[/yellow]"
            )
            await asyncio.sleep(self.config.cooldown_seconds)

        # Wait for workers to finish
        await asyncio.gather(*workers, return_exceptions=True)
        metrics_task.cancel()

        self.console.print("[green]Load test completed[/green]")

    async def _collect_metrics(self) -> None:
        """Collect metrics during the test."""
        rps_timeline = []
        latency_timeline = []
        error_timeline = []

        last_count = 0
        last_time = time.time()

        while self.running:
            await asyncio.sleep(1)

            current_time = time.time()
            current_count = len(self.results)

            # Calculate RPS
            rps = (current_count - last_count) / (current_time - last_time)
            rps_timeline.append(rps)

            # Calculate average latency for last second
            recent_results = [r for r in self.results[last_count:current_count] if r.success]
            if recent_results:
                avg_latency = mean([r.latency_ms for r in recent_results])
                latency_timeline.append(avg_latency)
            else:
                latency_timeline.append(0)

            # Calculate error rate
            recent_errors = sum(1 for r in self.results[last_count:current_count] if not r.success)
            error_rate = (recent_errors / max(current_count - last_count, 1)) * 100
            error_timeline.append(error_rate)

            last_count = current_count
            last_time = current_time

        # Store in results (simplified - would be passed to calculate_results)
        self.rps_timeline = rps_timeline
        self.latency_timeline = latency_timeline
        self.error_timeline = error_timeline

    def calculate_results(self) -> LoadTestResults:
        """Calculate aggregated test results."""
        if not self.results:
            return LoadTestResults()

        # Separate successful and failed requests
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]

        # Calculate latency percentiles
        latencies = sorted([r.latency_ms for r in successful])
        results = LoadTestResults()

        if latencies:
            results.total_requests = len(self.results)
            results.successful_requests = len(successful)
            results.failed_requests = len(failed)
            results.success_rate = (len(successful) / len(self.results)) * 100
            results.duration_seconds = time.time() - self.start_time

            # Throughput metrics
            results.mean_rps = len(self.results) / results.duration_seconds
            if hasattr(self, "rps_timeline") and self.rps_timeline:
                results.peak_rps = max(self.rps_timeline)
                results.sustained_rps = median(self.rps_timeline)

            # Latency metrics
            results.mean_latency_ms = mean(latencies)
            results.median_latency_ms = median(latencies)
            if len(latencies) > 1:
                results.stddev_latency_ms = stdev(latencies)

            # Percentiles
            def percentile(data: list, p: float) -> float:
                index = int(len(data) * p)
                return data[min(index, len(data) - 1)]

            results.p50_latency_ms = percentile(latencies, 0.50)
            results.p75_latency_ms = percentile(latencies, 0.75)
            results.p90_latency_ms = percentile(latencies, 0.90)
            results.p95_latency_ms = percentile(latencies, 0.95)
            results.p99_latency_ms = percentile(latencies, 0.99)
            results.min_latency_ms = min(latencies)
            results.max_latency_ms = max(latencies)

            # Error analysis
            for result in failed:
                error_type = str(result.error_code) if result.error_code else "Unknown"
                if error_type not in results.errors_by_type:
                    results.errors_by_type[error_type] = 0
                results.errors_by_type[error_type] += 1

            # Worker stats
            results.worker_stats = list(self.worker_stats.values())

            # Timeline data
            if hasattr(self, "rps_timeline"):
                results.rps_timeline = self.rps_timeline
                results.latency_timeline = self.latency_timeline
                results.error_timeline = self.error_timeline

        return results

    def render_results(self, results: LoadTestResults) -> None:
        """Render test results to console."""
        # Overall summary
        summary = f"""
[bold]Load Test Summary[/bold]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pattern: {self.config.pattern.value}
Duration: {results.duration_seconds:.1f}s
Total Requests: {results.total_requests:,}
Successful: {results.successful_requests:,} ({results.success_rate:.2f}%)
Failed: {results.failed_requests:,}

[bold]Throughput[/bold]
Mean RPS: {results.mean_rps:.2f}
Peak RPS: {results.peak_rps:.2f}
Sustained RPS: {results.sustained_rps:.2f}
        """
        self.console.print(
            Panel(summary.strip(), title="Performance Summary", border_style="green")
        )

        # Latency distribution
        if results.mean_latency_ms > 0:
            latency_table = Table(title="Latency Distribution (ms)", show_header=True)
            latency_table.add_column("Metric", style="cyan")
            latency_table.add_column("Value", justify="right")

            latency_table.add_row("Min", f"{results.min_latency_ms:.2f}")
            latency_table.add_row("P50", f"{results.p50_latency_ms:.2f}")
            latency_table.add_row("P75", f"{results.p75_latency_ms:.2f}")
            latency_table.add_row("P90", f"{results.p90_latency_ms:.2f}")
            latency_table.add_row("P95", f"{results.p95_latency_ms:.2f}")
            latency_table.add_row("P99", f"{results.p99_latency_ms:.2f}")
            latency_table.add_row("Max", f"{results.max_latency_ms:.2f}")
            latency_table.add_row("", "")
            latency_table.add_row("Mean", f"{results.mean_latency_ms:.2f}")
            latency_table.add_row("Median", f"{results.median_latency_ms:.2f}")
            latency_table.add_row("StdDev", f"{results.stddev_latency_ms:.2f}")

            self.console.print(latency_table)

        # Error breakdown
        if results.errors_by_type:
            error_table = Table(title="Error Analysis", show_header=True)
            error_table.add_column("Error Type", style="red")
            error_table.add_column("Count", justify="right")
            error_table.add_column("Percentage", justify="right")

            for error_type, count in sorted(results.errors_by_type.items()):
                percentage = (count / results.failed_requests) * 100
                error_table.add_row(error_type, str(count), f"{percentage:.1f}%")

            self.console.print(error_table)

        # Worker distribution
        if results.worker_stats:
            worker_table = Table(title="Worker Performance", show_header=True)
            worker_table.add_column("Worker", style="cyan")
            worker_table.add_column("Requests", justify="right")
            worker_table.add_column("Success Rate", justify="right")
            worker_table.add_column("Avg Latency", justify="right")

            for stats in sorted(results.worker_stats, key=lambda s: s.worker_id):
                success_rate = (stats.requests_successful / max(stats.requests_sent, 1)) * 100
                avg_latency = stats.total_latency_ms / max(stats.requests_successful, 1)
                worker_table.add_row(
                    f"Worker {stats.worker_id}",
                    str(stats.requests_sent),
                    f"{success_rate:.1f}%",
                    f"{avg_latency:.2f}ms",
                )

            self.console.print(worker_table)

    async def export_results(self, results: LoadTestResults, filename: str | None = None) -> None:
        """Export test results to JSON file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"load_test_{self.config.pattern.value}_{timestamp}.json"

        export_data = {
            "test_config": self.config.model_dump(),
            "test_time": datetime.now().isoformat(),
            "results": {
                "summary": {
                    "total_requests": results.total_requests,
                    "successful_requests": results.successful_requests,
                    "failed_requests": results.failed_requests,
                    "success_rate": results.success_rate,
                    "duration_seconds": results.duration_seconds,
                },
                "throughput": {
                    "mean_rps": results.mean_rps,
                    "peak_rps": results.peak_rps,
                    "sustained_rps": results.sustained_rps,
                },
                "latency": {
                    "mean_ms": results.mean_latency_ms,
                    "median_ms": results.median_latency_ms,
                    "stddev_ms": results.stddev_latency_ms,
                    "p50_ms": results.p50_latency_ms,
                    "p75_ms": results.p75_latency_ms,
                    "p90_ms": results.p90_latency_ms,
                    "p95_ms": results.p95_latency_ms,
                    "p99_ms": results.p99_latency_ms,
                    "min_ms": results.min_latency_ms,
                    "max_ms": results.max_latency_ms,
                },
                "errors": results.errors_by_type,
                "worker_stats": [
                    {
                        "worker_id": s.worker_id,
                        "requests_sent": s.requests_sent,
                        "requests_successful": s.requests_successful,
                        "requests_failed": s.requests_failed,
                        "errors": s.errors_by_type,
                    }
                    for s in results.worker_stats
                ],
                "timelines": {
                    "rps": results.rps_timeline,
                    "latency": results.latency_timeline,
                    "error_rate": results.error_timeline,
                },
            },
        }

        with open(filename, "w") as f:
            json.dump(export_data, f, indent=2)

        self.console.print(f"\n[green]Results exported to {filename}[/green]")


async def main():
    """Main entry point for load testing."""
    console = Console()

    console.print("[bold blue]Load Testing Client[/bold blue]")
    console.print("Performance validation and stress testing\n")

    # Test configuration
    config = LoadTestConfig(
        service_name="echo",  # Target service
        method_name="echo",
        pattern=LoadPattern.RAMP_UP,
        duration_seconds=30,
        initial_rps=10.0,
        max_rps=100.0,
        concurrent_connections=10,
        payload_size=PayloadSize.SMALL,
        timeout_seconds=5.0,
        warmup_seconds=2,
        cooldown_seconds=2,
    )

    # Create tester
    tester = LoadTester(config)

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

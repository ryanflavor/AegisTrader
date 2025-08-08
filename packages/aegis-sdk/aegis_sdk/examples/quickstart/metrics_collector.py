#!/usr/bin/env python3
"""
Metrics Collector Service - Demonstrates metadata enrichment for observability.

This example shows:
- Enriching ServiceInstance.metadata with metrics
- Collecting performance data (latency, throughput, errors)
- Exposing metrics through service discovery
- Real-time metric updates in the registry

Run multiple instances to see distributed metrics:
    python metrics_collector.py --instance 1
    python metrics_collector.py --instance 2

Then use the metrics reader to view aggregated metrics.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from aegis_sdk.application.services import Service
from aegis_sdk.developer.bootstrap import quick_setup
from aegis_sdk.domain.models import ServiceInstance

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - [%(instance)s] - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)


class ServiceMetrics(BaseModel):
    """Metrics data structure for service observability."""

    # Performance metrics
    requests_total: int = Field(default=0, description="Total requests processed")
    requests_per_second: float = Field(default=0.0, description="Current request rate")
    average_latency_ms: float = Field(default=0.0, description="Average response time")
    p95_latency_ms: float = Field(default=0.0, description="95th percentile latency")
    p99_latency_ms: float = Field(default=0.0, description="99th percentile latency")

    # Error metrics
    errors_total: int = Field(default=0, description="Total errors encountered")
    error_rate: float = Field(default=0.0, description="Error percentage")
    last_error_time: datetime | None = Field(default=None, description="Last error timestamp")

    # Resource metrics
    memory_usage_mb: float = Field(default=0.0, description="Memory usage in MB")
    cpu_usage_percent: float = Field(default=0.0, description="CPU usage percentage")
    active_connections: int = Field(default=0, description="Active connections")

    # Business metrics
    business_value: dict[str, Any] = Field(
        default_factory=dict, description="Custom business metrics"
    )

    # Metadata
    uptime_seconds: float = Field(default=0.0, description="Service uptime")
    last_updated: datetime = Field(
        default_factory=datetime.utcnow, description="Last metric update"
    )


class MetricsCollectorService(Service):
    """
    Service that collects and exposes metrics through metadata.

    Demonstrates how to:
    - Collect real-time performance metrics
    - Update service metadata for observability
    - Make metrics discoverable through the registry
    """

    def __init__(self, instance_id: int):
        self.instance_id = str(instance_id)
        self.logger = logging.getLogger(f"MetricsCollector-{instance_id}")
        self.start_time = time.time()

        # Metrics storage
        self.metrics = ServiceMetrics()
        self.latency_history = deque(maxlen=1000)  # Keep last 1000 latencies
        self.request_timestamps = deque(maxlen=100)  # For calculating RPS

        # Add instance to log records
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.instance = instance_id
            return record

        logging.setLogRecordFactory(record_factory)

        super().__init__(
            name=f"metrics-collector-{instance_id}",
            service_type="metrics-collector",
            instance_id=self.instance_id,
        )

    async def on_startup(self) -> None:
        """Initialize service and start metrics collection."""
        await super().on_startup()
        self.logger.info(f"📊 Metrics Collector {self.instance_id} started")

        # Start background metrics updater
        asyncio.create_task(self._update_metrics_loop())

        # Start simulated workload generator
        asyncio.create_task(self._simulate_workload())

    async def _update_metrics_loop(self) -> None:
        """Continuously update metrics in service metadata."""
        while True:
            try:
                # Update metrics
                self._calculate_metrics()

                # Enrich service metadata with metrics
                metadata = {
                    "metrics": self.metrics.model_dump(),
                    "health_score": self._calculate_health_score(),
                    "performance_grade": self._get_performance_grade(),
                }

                # Update service instance metadata in registry
                await self._update_service_metadata(metadata)

                self.logger.debug(
                    f"📊 Updated metrics: {self.metrics.requests_total} requests, "
                    f"{self.metrics.average_latency_ms:.1f}ms avg latency"
                )

            except Exception as e:
                self.logger.error(f"Error updating metrics: {e}")

            await asyncio.sleep(5)  # Update every 5 seconds

    async def _update_service_metadata(self, metadata: dict[str, Any]) -> None:
        """Update service metadata in the registry."""
        # This would normally update the service registry
        # For demo, we're just logging
        if hasattr(self, "service_registry"):
            # Update our instance in the registry
            ServiceInstance(
                service_name=self.name,
                service_type=self.service_type,
                instance_id=self.instance_id,
                metadata=metadata,
                health_status="healthy",
                last_heartbeat=datetime.utcnow(),
            )
            # In real implementation, this would update the registry
            self.logger.debug(f"Updated service metadata: {metadata}")

    def _calculate_metrics(self) -> None:
        """Calculate current metrics from collected data."""
        current_time = time.time()

        # Calculate uptime
        self.metrics.uptime_seconds = current_time - self.start_time

        # Calculate requests per second
        recent_requests = [
            t for t in self.request_timestamps if current_time - t < 60
        ]  # Last minute
        if len(recent_requests) > 1:
            time_span = current_time - recent_requests[0]
            self.metrics.requests_per_second = (
                len(recent_requests) / time_span if time_span > 0 else 0
            )
        else:
            self.metrics.requests_per_second = 0

        # Calculate latency percentiles
        if self.latency_history:
            sorted_latencies = sorted(self.latency_history)
            self.metrics.average_latency_ms = sum(sorted_latencies) / len(sorted_latencies)
            self.metrics.p95_latency_ms = sorted_latencies[int(len(sorted_latencies) * 0.95)]
            self.metrics.p99_latency_ms = sorted_latencies[int(len(sorted_latencies) * 0.99)]

        # Calculate error rate
        if self.metrics.requests_total > 0:
            self.metrics.error_rate = (
                self.metrics.errors_total / self.metrics.requests_total
            ) * 100

        # Simulate resource metrics
        self.metrics.memory_usage_mb = 100 + random.uniform(-20, 50)
        self.metrics.cpu_usage_percent = 20 + random.uniform(-10, 30)
        self.metrics.active_connections = random.randint(5, 50)

        # Update timestamp
        self.metrics.last_updated = datetime.utcnow()

    def _calculate_health_score(self) -> float:
        """Calculate overall health score (0-100)."""
        score = 100.0

        # Deduct for high error rate
        if self.metrics.error_rate > 5:
            score -= min(30, self.metrics.error_rate * 2)

        # Deduct for high latency
        if self.metrics.average_latency_ms > 100:
            score -= min(20, (self.metrics.average_latency_ms - 100) / 10)

        # Deduct for high resource usage
        if self.metrics.cpu_usage_percent > 80:
            score -= 10
        if self.metrics.memory_usage_mb > 500:
            score -= 10

        return max(0, score)

    def _get_performance_grade(self) -> str:
        """Get performance grade based on metrics."""
        if self.metrics.average_latency_ms < 10 and self.metrics.error_rate < 1:
            return "A+"
        elif self.metrics.average_latency_ms < 50 and self.metrics.error_rate < 2:
            return "A"
        elif self.metrics.average_latency_ms < 100 and self.metrics.error_rate < 5:
            return "B"
        elif self.metrics.average_latency_ms < 200 and self.metrics.error_rate < 10:
            return "C"
        else:
            return "D"

    async def _simulate_workload(self) -> None:
        """Simulate workload to generate metrics."""
        while True:
            try:
                # Simulate a request
                start_time = time.time()

                # Random processing time
                processing_time = random.uniform(0.001, 0.1)
                await asyncio.sleep(processing_time)

                # Random chance of error
                if random.random() < 0.05:  # 5% error rate
                    self.metrics.errors_total += 1
                    self.metrics.last_error_time = datetime.utcnow()
                    self.logger.debug("❌ Simulated error occurred")

                # Record metrics
                latency_ms = (time.time() - start_time) * 1000
                self.latency_history.append(latency_ms)
                self.request_timestamps.append(time.time())
                self.metrics.requests_total += 1

                # Update business metrics
                self.metrics.business_value = {
                    "transactions_processed": self.metrics.requests_total * 10,
                    "revenue_generated": self.metrics.requests_total * random.uniform(1, 10),
                    "users_served": int(self.metrics.requests_total / 5),
                }

                # Random delay between requests
                await asyncio.sleep(random.uniform(0.1, 0.5))

            except Exception as e:
                self.logger.error(f"Error in workload simulation: {e}")
                await asyncio.sleep(1)

    async def get_metrics(self, params: dict[str, Any]) -> dict[str, Any]:
        """RPC handler to get current metrics."""
        return {
            "instance_id": self.instance_id,
            "metrics": self.metrics.model_dump(),
            "health_score": self._calculate_health_score(),
            "performance_grade": self._get_performance_grade(),
        }

    async def reset_metrics(self, params: dict[str, Any]) -> dict[str, Any]:
        """RPC handler to reset metrics."""
        self.metrics = ServiceMetrics()
        self.latency_history.clear()
        self.request_timestamps.clear()
        self.start_time = time.time()

        self.logger.info("🔄 Metrics reset")
        return {"status": "success", "message": "Metrics reset successfully"}

    async def simulate_load(self, params: dict[str, Any]) -> dict[str, Any]:
        """RPC handler to simulate load spike."""
        duration = params.get("duration", 10)
        intensity = params.get("intensity", "medium")

        self.logger.info(f"🚀 Simulating {intensity} load for {duration} seconds")

        # Adjust workload based on intensity
        delays = {"low": 0.5, "medium": 0.1, "high": 0.01}
        delay = delays.get(intensity, 0.1)

        # Generate load
        end_time = time.time() + duration
        request_count = 0

        while time.time() < end_time:
            # Simulate request
            latency = random.uniform(1, 100) if intensity == "high" else random.uniform(1, 50)
            self.latency_history.append(latency)
            self.request_timestamps.append(time.time())
            self.metrics.requests_total += 1
            request_count += 1

            # Random errors during high load
            if intensity == "high" and random.random() < 0.1:
                self.metrics.errors_total += 1

            await asyncio.sleep(delay)

        return {
            "status": "success",
            "requests_generated": request_count,
            "duration": duration,
            "intensity": intensity,
        }


async def main():
    """Run the metrics collector service."""
    import argparse

    parser = argparse.ArgumentParser(description="Metrics Collector Service")
    parser.add_argument("--instance", type=int, default=1, help="Instance number")

    args = parser.parse_args()

    # Create and configure the service
    service = MetricsCollectorService(args.instance)

    # Use quick_setup for auto-configuration
    configured_service = await quick_setup(
        f"metrics-collector-{args.instance}", service_instance=service
    )

    # Register RPC handlers
    configured_service.register_rpc_handler("get_metrics", service.get_metrics)
    configured_service.register_rpc_handler("reset_metrics", service.reset_metrics)
    configured_service.register_rpc_handler("simulate_load", service.simulate_load)

    # Start the service
    try:
        print(f"\n📊 Starting Metrics Collector Service - Instance {args.instance}")
        print("🎯 Pattern: Base Service with metadata enrichment")
        print("💡 Metrics are updated in service metadata every 5 seconds")
        print("\nFeatures:")
        print("  - Real-time performance metrics (latency, throughput)")
        print("  - Error tracking and health scoring")
        print("  - Resource usage monitoring")
        print("  - Business metrics collection")
        print("\nRun metrics_reader.py to view aggregated metrics")
        print("Press Ctrl+C to stop...\n")

        await configured_service.start()

        # Keep running
        while True:
            await asyncio.sleep(10)
            # Print current metrics summary
            print(f"\n📊 Instance {args.instance} Metrics Summary:")
            print(f"  Requests: {service.metrics.requests_total}")
            print(f"  RPS: {service.metrics.requests_per_second:.2f}")
            print(f"  Avg Latency: {service.metrics.average_latency_ms:.1f}ms")
            print(f"  Error Rate: {service.metrics.error_rate:.1f}%")
            print(f"  Health Score: {service._calculate_health_score():.0f}/100")
            print(f"  Performance: {service._get_performance_grade()}")

    except KeyboardInterrupt:
        print(f"\n⏹️  Stopping metrics collector {args.instance}...")
        await configured_service.stop()


if __name__ == "__main__":
    asyncio.run(main())

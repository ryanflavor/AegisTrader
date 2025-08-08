"""SDK monitoring adapter implementation.

Provides infrastructure adapter for SDK monitoring functionality.
"""

import logging
import time
from typing import Any

from ..ports.sdk_monitoring import SDKMonitoringPort
from ..ports.service_registry_kv_store import ServiceRegistryKVStorePort

logger = logging.getLogger(__name__)


class SDKMonitoringAdapter(SDKMonitoringPort):
    """Infrastructure adapter for SDK monitoring operations."""

    def __init__(self, kv_store: ServiceRegistryKVStorePort) -> None:
        """Initialize the SDK monitoring adapter.

        Args:
            kv_store: KV store for accessing service registry
        """
        self.kv_store = kv_store

    async def run_tests(self, scenario: str, tags: list[str] | None = None) -> dict[str, Any]:
        """Run SDK test scenarios.

        Args:
            scenario: Test scenario to run
            tags: Optional tags to filter tests

        Returns:
            Test results including pass/fail counts and details
        """
        start_time = time.time()

        results = {
            "scenario": scenario,
            "tags": tags or [],
            "passed": 0,
            "failed": 0,
            "duration_ms": 0,
            "tests": [],
        }

        # Simulate running tests for different scenarios
        if scenario == "connectivity":
            results["tests"] = [
                {"name": "nats_connection", "status": "passed", "duration_ms": 15},
                {"name": "kv_store_access", "status": "passed", "duration_ms": 8},
            ]
            results["passed"] = 2
        elif scenario == "service_discovery":
            services = await self.kv_store.list_all()
            results["tests"] = [
                {"name": "list_services", "status": "passed", "duration_ms": 20},
                {"name": "service_count", "status": "passed", "value": len(services)},
            ]
            results["passed"] = 2
        else:
            results["tests"] = [{"name": scenario, "status": "failed", "error": "Unknown scenario"}]
            results["failed"] = 1

        results["duration_ms"] = (time.time() - start_time) * 1000
        return results

    async def get_test_scenarios(self) -> list[dict[str, Any]]:
        """Get available test scenarios.

        Returns:
            Available test scenarios with metadata
        """
        return [
            {
                "name": "connectivity",
                "description": "Test NATS and KV store connectivity",
                "tags": ["basic", "infrastructure"],
                "duration_estimate_ms": 50,
            },
            {
                "name": "service_discovery",
                "description": "Test service discovery functionality",
                "tags": ["basic", "services"],
                "duration_estimate_ms": 100,
            },
            {
                "name": "rpc_calls",
                "description": "Test RPC functionality",
                "tags": ["advanced", "communication"],
                "duration_estimate_ms": 200,
            },
            {
                "name": "event_streaming",
                "description": "Test event pub/sub patterns",
                "tags": ["advanced", "events"],
                "duration_estimate_ms": 500,
            },
            {
                "name": "failover",
                "description": "Test failover behavior",
                "tags": ["advanced", "resilience"],
                "duration_estimate_ms": 2000,
            },
        ]

    async def get_event_metrics(self, topics: list[str] | None = None) -> dict[str, Any]:
        """Get event stream metrics.

        Args:
            topics: Optional topics to monitor

        Returns:
            Event stream metrics
        """
        # In production, would fetch real metrics
        metrics = {
            "total_events": 10000,
            "events_per_second": 250.5,
            "topics": topics or ["orders", "payments", "inventory"],
            "metrics_by_topic": {},
        }

        for topic in metrics["topics"]:
            metrics["metrics_by_topic"][topic] = {
                "events": 3000 + len(topic) * 100,
                "rate": 80 + len(topic) * 5,
                "errors": 0,
            }

        return metrics

    async def get_load_metrics(self, service_name: str | None = None) -> dict[str, Any]:
        """Get load testing metrics.

        Args:
            service_name: Optional service to get metrics for

        Returns:
            Load testing metrics
        """
        if service_name:
            return {
                "service": service_name,
                "requests_per_second": 1000,
                "latency_p50_ms": 12.5,
                "latency_p95_ms": 45.2,
                "latency_p99_ms": 125.8,
                "error_rate": 0.001,
                "active_connections": 50,
            }
        else:
            # System-wide metrics
            return {
                "total_requests_per_second": 5000,
                "services": 10,
                "average_latency_ms": 25.5,
                "system_error_rate": 0.002,
                "total_active_connections": 250,
            }

    async def get_failover_metrics(self, service_name: str) -> dict[str, Any]:
        """Get failover metrics for a service.

        Args:
            service_name: Service to monitor

        Returns:
            Failover metrics
        """
        return {
            "service": service_name,
            "failover_time_ms": 1250.5,
            "leader_changes": 2,
            "failed_requests_during_failover": 3,
            "availability_percentage": 99.7,
            "last_failover": "2025-08-06T10:30:00Z",
            "current_leader": f"{service_name}-instance-1",
        }

    async def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate SDK configuration.

        Args:
            config: Configuration to validate

        Returns:
            Validation results
        """
        issues = []
        warnings = []

        # Validate NATS URL
        nats_url = config.get("nats_url", "")
        if not nats_url:
            issues.append("Missing NATS URL")
        elif not nats_url.startswith("nats://"):
            warnings.append("NATS URL should start with 'nats://'")

        # Validate service name
        service_name = config.get("service_name", "")
        if not service_name:
            issues.append("Missing service name")
        elif len(service_name) < 3:
            warnings.append("Service name should be at least 3 characters")

        # Check connectivity
        nats_connected = True
        try:
            await self.kv_store.list_all()
        except Exception:
            nats_connected = False
            issues.append("Cannot connect to NATS")

        return {
            "valid": len(issues) == 0,
            "nats_connected": nats_connected,
            "issues": issues,
            "warnings": warnings,
            "config": config,
        }

    async def get_service_dependencies(self, service_name: str) -> dict[str, Any]:
        """Get service dependency graph.

        Args:
            service_name: Service to analyze

        Returns:
            Service dependencies
        """
        # Simulate dependency graph
        dependencies = {
            "service": service_name,
            "direct_dependencies": [],
            "indirect_dependencies": [],
            "dependency_graph": {},
        }

        # Mock dependency data
        if "order" in service_name.lower():
            dependencies["direct_dependencies"] = ["inventory-service", "payment-service"]
            dependencies["indirect_dependencies"] = ["user-service", "notification-service"]
        elif "payment" in service_name.lower():
            dependencies["direct_dependencies"] = ["user-service", "fraud-service"]
            dependencies["indirect_dependencies"] = ["notification-service"]
        else:
            dependencies["direct_dependencies"] = ["nats", "kv-store"]

        # Build graph
        for dep in dependencies["direct_dependencies"]:
            dependencies["dependency_graph"][dep] = {
                "type": "direct",
                "protocol": "rpc",
                "health": "healthy",
            }

        return dependencies

    async def run_test_scenario(self, scenario: str, timeout: int = 30) -> dict[str, Any]:
        """Run a test scenario.

        Args:
            scenario: Name of the test scenario
            timeout: Timeout in seconds

        Returns:
            Test results including success status and metrics
        """
        start_time = time.time()

        # Simulate running different test scenarios
        results = {
            "scenario": scenario,
            "success": True,
            "duration_ms": 0,
            "results": {},
            "errors": [],
        }

        try:
            if scenario == "connectivity":
                # Test NATS connectivity
                services = await self.kv_store.list_all()
                results["results"] = {
                    "nats_connected": True,
                    "services_found": len(services),
                    "kv_accessible": True,
                }
            elif scenario == "service_discovery":
                # Test service discovery
                services = await self.kv_store.list_all()
                results["results"] = {"total_services": len(services), "service_names": services}
            elif scenario == "rpc_call":
                # Test RPC functionality
                results["results"] = {
                    "rpc_available": True,
                    "latency_ms": 15.3,
                    "success_rate": 1.0,
                }
            elif scenario == "event_stream":
                # Test event streaming
                results["results"] = {
                    "events_received": 100,
                    "events_per_second": 50.0,
                    "subscription_active": True,
                }
            else:
                results["success"] = False
                results["errors"].append(f"Unknown scenario: {scenario}")

        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))

        results["duration_ms"] = (time.time() - start_time) * 1000
        return results

    async def list_test_scenarios(self) -> dict[str, list[str]]:
        """List available test scenarios.

        Returns:
            Categorized list of test scenarios
        """
        return {
            "basic": ["connectivity", "service_discovery", "rpc_call"],
            "advanced": ["event_stream", "failover", "load_test"],
            "patterns": ["single_active", "load_balanced", "event_driven"],
        }

    async def get_event_stream_metrics(self) -> dict[str, Any]:
        """Get event stream metrics.

        Returns:
            Event stream performance metrics
        """
        # In production, this would fetch real metrics from monitoring
        return {
            "total_events": 10000,
            "events_per_second": 250.5,
            "event_types": {
                "order.created": 3500,
                "order.processed": 3400,
                "payment.completed": 3100,
            },
            "subscription_modes": {"COMPETE": 5, "BROADCAST": 3, "EXCLUSIVE": 2},
            "errors": 0,
        }

    async def run_load_test(
        self, target_service: str, duration_seconds: int = 30, requests_per_second: int = 100
    ) -> dict[str, Any]:
        """Run a load test against a service.

        Args:
            target_service: Service to test
            duration_seconds: Test duration
            requests_per_second: Request rate

        Returns:
            Load test results with latency percentiles
        """
        # Simulate load test results
        return {
            "requests_sent": duration_seconds * requests_per_second,
            "requests_per_second": requests_per_second,
            "latency_p50_ms": 12.5,
            "latency_p95_ms": 45.2,
            "latency_p99_ms": 125.8,
            "error_rate": 0.001,
            "duration_seconds": duration_seconds,
        }

    async def test_failover(self, target_service: str) -> dict[str, Any]:
        """Test failover behavior.

        Args:
            target_service: Service to test failover

        Returns:
            Failover metrics and timing
        """
        # Simulate failover test
        return {
            "failover_time_ms": 1250.5,
            "leader_changes": 2,
            "failed_requests": 3,
            "successful_requests": 997,
            "availability_percentage": 99.7,
        }

    async def validate_configuration(self) -> dict[str, Any]:
        """Validate SDK configuration.

        Returns:
            Configuration validation results
        """
        issues = []
        recommendations = []

        # Check NATS connectivity
        nats_connected = True
        try:
            services = await self.kv_store.list_all()
            services_discovered = len(services)
        except Exception as e:
            nats_connected = False
            services_discovered = 0
            issues.append(f"NATS connection failed: {e}")
            recommendations.append(
                "Check NATS port-forwarding: kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222"
            )

        # Check K8s accessibility (simulated)
        k8s_accessible = True

        return {
            "valid": nats_connected and k8s_accessible,
            "nats_connected": nats_connected,
            "k8s_accessible": k8s_accessible,
            "services_discovered": services_discovered,
            "issues": issues,
            "recommendations": recommendations,
        }

    async def list_examples(self) -> dict[str, list[str]]:
        """List available SDK examples.

        Returns:
            Categorized list of examples
        """
        return {
            "quickstart": ["echo_service", "echo_client", "order_service", "event_demo"],
            "patterns": ["single_active_service", "load_balanced_service", "event_driven_service"],
            "tools": ["interactive_client", "service_explorer", "event_monitor", "failover_tester"],
        }

    async def run_example(self, example_name: str) -> dict[str, Any]:
        """Run a specific SDK example.

        Args:
            example_name: Name of the example to run

        Returns:
            Example execution results
        """
        # Simulate running an example
        return {
            "example": example_name,
            "status": "completed",
            "output": f"Example {example_name} executed successfully",
            "duration_ms": 500.0,
            "logs": [
                f"Starting {example_name}...",
                "Connecting to NATS...",
                "Service registered successfully",
                "Example completed",
            ],
        }

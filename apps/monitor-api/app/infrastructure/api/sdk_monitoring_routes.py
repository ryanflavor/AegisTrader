"""SDK monitoring API routes.

Routes for SDK developer experience tools monitoring and testing.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...application.sdk_monitoring_service import SDKMonitoringService
from .dependencies import get_sdk_monitoring_service

logger = logging.getLogger(__name__)


# Request/Response models
class TestScenarioRequest(BaseModel):
    """Request to run a test scenario."""

    scenario: str = Field(..., description="Test scenario to run")
    timeout: int = Field(default=30, description="Timeout in seconds")


class TestScenarioResponse(BaseModel):
    """Response from running a test scenario."""

    scenario: str
    success: bool
    duration_ms: float
    results: dict[str, Any]
    errors: list[str]


class EventStreamMetrics(BaseModel):
    """Event stream monitoring metrics."""

    total_events: int
    events_per_second: float
    event_types: dict[str, int]
    subscription_modes: dict[str, int]
    errors: int


class LoadTestMetrics(BaseModel):
    """Load test execution metrics."""

    requests_sent: int
    requests_per_second: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    error_rate: float
    duration_seconds: float


class FailoverMetrics(BaseModel):
    """Failover testing metrics."""

    failover_time_ms: float
    leader_changes: int
    failed_requests: int
    successful_requests: int
    availability_percentage: float


class ConfigValidationResult(BaseModel):
    """Configuration validation result."""

    valid: bool
    nats_connected: bool
    k8s_accessible: bool
    services_discovered: int
    issues: list[str]
    recommendations: list[str]


# Create router with prefix
router = APIRouter(prefix="/sdk", tags=["SDK Monitoring"])


@router.post("/test/scenario", response_model=TestScenarioResponse)
async def run_test_scenario(
    request: TestScenarioRequest,
    service: SDKMonitoringService = Depends(get_sdk_monitoring_service),
) -> TestScenarioResponse:
    """Run a predefined SDK test scenario."""
    try:
        result = await service.run_test_scenario(scenario=request.scenario, timeout=request.timeout)
        return TestScenarioResponse(
            scenario=result["scenario"],
            success=result["success"],
            duration_ms=result["duration_ms"],
            results=result.get("results", {}),
            errors=result.get("errors", []),
        )
    except Exception as e:
        logger.error(f"Failed to run test scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test/scenarios")
async def list_test_scenarios(
    service: SDKMonitoringService = Depends(get_sdk_monitoring_service),
) -> dict[str, list[str]]:
    """List available test scenarios."""
    try:
        return await service.list_test_scenarios()
    except Exception as e:
        logger.error(f"Failed to list test scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/events", response_model=EventStreamMetrics)
async def get_event_stream_metrics(
    service: SDKMonitoringService = Depends(get_sdk_monitoring_service),
) -> EventStreamMetrics:
    """Get event stream monitoring metrics."""
    try:
        metrics = await service.get_event_stream_metrics()
        return EventStreamMetrics(
            total_events=metrics["total_events"],
            events_per_second=metrics["events_per_second"],
            event_types=metrics["event_types"],
            subscription_modes=metrics["subscription_modes"],
            errors=metrics["errors"],
        )
    except Exception as e:
        logger.error(f"Failed to get event stream metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/load", response_model=LoadTestMetrics)
async def run_load_test(
    target_service: str,
    duration_seconds: int = 30,
    requests_per_second: int = 100,
    service: SDKMonitoringService = Depends(get_sdk_monitoring_service),
) -> LoadTestMetrics:
    """Run a load test against a service."""
    try:
        result = await service.run_load_test(
            target_service=target_service,
            duration_seconds=duration_seconds,
            requests_per_second=requests_per_second,
        )
        return LoadTestMetrics(
            requests_sent=result["requests_sent"],
            requests_per_second=result["requests_per_second"],
            latency_p50_ms=result["latency_p50_ms"],
            latency_p95_ms=result["latency_p95_ms"],
            latency_p99_ms=result["latency_p99_ms"],
            error_rate=result["error_rate"],
            duration_seconds=result["duration_seconds"],
        )
    except Exception as e:
        logger.error(f"Failed to run load test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/failover", response_model=FailoverMetrics)
async def test_failover(
    target_service: str,
    service: SDKMonitoringService = Depends(get_sdk_monitoring_service),
) -> FailoverMetrics:
    """Test failover behavior of a service."""
    try:
        result = await service.test_failover(target_service)
        return FailoverMetrics(
            failover_time_ms=result["failover_time_ms"],
            leader_changes=result["leader_changes"],
            failed_requests=result["failed_requests"],
            successful_requests=result["successful_requests"],
            availability_percentage=result["availability_percentage"],
        )
    except Exception as e:
        logger.error(f"Failed to test failover: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/validate", response_model=ConfigValidationResult)
async def validate_configuration(
    service: SDKMonitoringService = Depends(get_sdk_monitoring_service),
) -> ConfigValidationResult:
    """Validate SDK configuration and environment."""
    try:
        result = await service.validate_configuration()
        return ConfigValidationResult(
            valid=result["valid"],
            nats_connected=result["nats_connected"],
            k8s_accessible=result["k8s_accessible"],
            services_discovered=result["services_discovered"],
            issues=result.get("issues", []),
            recommendations=result.get("recommendations", []),
        )
    except Exception as e:
        logger.error(f"Failed to validate configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/examples")
async def list_examples(
    service: SDKMonitoringService = Depends(get_sdk_monitoring_service),
) -> dict[str, list[str]]:
    """List available SDK examples."""
    try:
        return await service.list_examples()
    except Exception as e:
        logger.error(f"Failed to list examples: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/examples/run")
async def run_example(
    example_name: str,
    service: SDKMonitoringService = Depends(get_sdk_monitoring_service),
) -> dict[str, Any]:
    """Run a specific SDK example."""
    try:
        return await service.run_example(example_name)
    except Exception as e:
        logger.error(f"Failed to run example: {e}")
        raise HTTPException(status_code=500, detail=str(e))

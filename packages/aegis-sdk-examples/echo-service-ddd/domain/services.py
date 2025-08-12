"""Domain services for Echo Service.

Domain services contain business logic that doesn't naturally fit within a single entity.
They orchestrate operations across multiple entities and value objects.
"""

from __future__ import annotations

import asyncio
import base64
import codecs
import time
from typing import Any

from .entities import EchoRequest, EchoResponse, ServiceMetrics
from .value_objects import EchoMode, MessagePriority, TransformationType


class EchoProcessor:
    """Domain service for processing echo requests.

    Contains the core business logic for transforming messages based on mode.
    """

    def __init__(self, instance_id: str):
        """Initialize the echo processor.

        Args:
            instance_id: Unique identifier for this service instance
        """
        self.instance_id = instance_id
        self._sequence_counter = 0

    async def process_echo(self, request: EchoRequest) -> EchoResponse:
        """Process an echo request according to its mode.

        Args:
            request: The echo request to process

        Returns:
            The processed echo response
        """
        start_time = time.time()
        self._sequence_counter += 1

        # Apply delay if needed
        if request.requires_delay():
            await asyncio.sleep(request.delay)

        # Process based on mode
        echoed_message = await self._apply_transformation(request)

        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000

        return EchoResponse(
            original=request.message,
            echoed=echoed_message,
            mode=request.mode,
            instance_id=self.instance_id,
            processing_time_ms=processing_time_ms,
            sequence_number=self._sequence_counter,
            metadata=request.metadata,
            request_id=request.request_id,
        )

    async def _apply_transformation(self, request: EchoRequest) -> str:
        """Apply the appropriate transformation based on mode.

        Args:
            request: The echo request

        Returns:
            The transformed message
        """
        if request.mode == EchoMode.SIMPLE:
            return request.message
        elif request.mode == EchoMode.REVERSE:
            return request.message[::-1]
        elif request.mode == EchoMode.UPPERCASE:
            return request.message.upper()
        elif request.mode == EchoMode.DELAYED:
            # Delay is already applied, just return the message
            return request.message
        elif request.mode == EchoMode.TRANSFORM:
            return await self._apply_custom_transformation(request.message, request.transform_type)
        else:
            # Default to simple echo for unknown modes
            return request.message

    async def _apply_custom_transformation(self, message: str, transform_type: str | None) -> str:
        """Apply custom transformation to the message.

        Args:
            message: The message to transform
            transform_type: The type of transformation to apply

        Returns:
            The transformed message
        """
        if not transform_type:
            return message

        try:
            if transform_type == TransformationType.BASE64_ENCODE.value:
                return base64.b64encode(message.encode()).decode()
            elif transform_type == TransformationType.BASE64_DECODE.value:
                return base64.b64decode(message.encode()).decode()
            elif transform_type == TransformationType.ROT13.value:
                return codecs.encode(message, "rot_13")
            elif transform_type == TransformationType.LEETSPEAK.value:
                return self._to_leetspeak(message)
            elif transform_type == TransformationType.WORD_REVERSE.value:
                return " ".join(word[::-1] for word in message.split())
            elif transform_type == TransformationType.CAPITALIZE_WORDS.value:
                return " ".join(word.capitalize() for word in message.split())
            else:
                return message
        except Exception:
            # If transformation fails, return original message
            return message

    def _to_leetspeak(self, text: str) -> str:
        """Convert text to leetspeak.

        Args:
            text: The text to convert

        Returns:
            The leetspeak version of the text
        """
        leet_map = {
            "a": "4",
            "A": "4",
            "e": "3",
            "E": "3",
            "i": "1",
            "I": "1",
            "o": "0",
            "O": "0",
            "s": "5",
            "S": "5",
            "t": "7",
            "T": "7",
            "l": "1",
            "L": "1",
        }
        return "".join(leet_map.get(char, char) for char in text)

    async def process_batch(self, requests: list[EchoRequest]) -> list[EchoResponse]:
        """Process multiple echo requests in batch.

        Args:
            requests: List of echo requests to process

        Returns:
            List of echo responses
        """
        # Process requests concurrently
        tasks = [self.process_echo(req) for req in requests]
        return await asyncio.gather(*tasks)


class MetricsCollector:
    """Domain service for collecting and managing service metrics.

    Handles metric collection, aggregation, and analysis.
    """

    def __init__(self, instance_id: str):
        """Initialize the metrics collector.

        Args:
            instance_id: Unique identifier for this service instance
        """
        self.metrics = ServiceMetrics(instance_id=instance_id)
        self._start_time = time.time()

    def record_request(
        self, mode: EchoMode, priority: MessagePriority, latency_ms: float, success: bool = True
    ) -> None:
        """Record a processed request in metrics.

        Args:
            mode: The echo mode used
            priority: The message priority
            latency_ms: Processing latency in milliseconds
            success: Whether the request was successful
        """
        self.metrics.record_request(mode, priority, latency_ms, success)

    def get_current_metrics(self) -> ServiceMetrics:
        """Get current service metrics.

        Returns:
            Current metrics snapshot
        """
        # Update uptime
        self.metrics.uptime_seconds = time.time() - self._start_time
        return self.metrics

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get a summary of current metrics.

        Returns:
            Dictionary containing metric summary
        """
        metrics = self.get_current_metrics()
        return {
            "instance_id": metrics.instance_id,
            "total_requests": metrics.total_requests,
            "success_rate": metrics.get_success_rate(),
            "average_latency_ms": metrics.average_latency_ms,
            "uptime_seconds": metrics.uptime_seconds,
            "mode_distribution": {
                mode.value: count for mode, count in metrics.mode_distribution.items()
            },
            "priority_distribution": {
                priority.value: count for priority, count in metrics.priority_distribution.items()
            },
        }

    def reset_metrics(self) -> None:
        """Reset all metrics to initial state."""
        self.metrics = ServiceMetrics(instance_id=self.metrics.instance_id)
        self._start_time = time.time()


class HealthChecker:
    """Domain service for health checking.

    Monitors and reports on service health status.
    """

    def __init__(self, instance_id: str, version: str):
        """Initialize the health checker.

        Args:
            instance_id: Unique identifier for this service instance
            version: Service version
        """
        self.instance_id = instance_id
        self.version = version
        self._checks: dict[str, bool] = {}

    def add_check(self, name: str, status: bool) -> None:
        """Add a health check result.

        Args:
            name: Name of the health check
            status: Whether the check passed
        """
        self._checks[name] = status

    def is_healthy(self) -> bool:
        """Check if all health checks are passing.

        Returns:
            True if all checks pass, False otherwise
        """
        return all(self._checks.values()) if self._checks else True

    def get_health_status(self) -> dict[str, Any]:
        """Get current health status.

        Returns:
            Dictionary containing health status information
        """
        overall_status = "healthy" if self.is_healthy() else "unhealthy"

        return {
            "status": overall_status,
            "instance_id": self.instance_id,
            "version": self.version,
            "checks": self._checks.copy(),
        }

    async def check_dependencies(self) -> dict[str, bool]:
        """Check health of external dependencies.

        Returns:
            Dictionary of dependency health status
        """
        checks = {}

        # Check NATS connectivity (placeholder - would check actual connection)
        checks["nats"] = True

        # Check monitor-api availability (placeholder)
        checks["monitor_api"] = True

        # Update internal checks
        for name, status in checks.items():
            self.add_check(name, status)

        return checks


class PriorityManager:
    """Domain service for managing request priorities.

    Handles priority-based request ordering and processing decisions.
    """

    @staticmethod
    def should_prioritize(request: EchoRequest) -> bool:
        """Determine if a request should be prioritized.

        Args:
            request: The echo request

        Returns:
            True if request should be prioritized
        """
        return request.is_high_priority()

    @staticmethod
    def sort_by_priority(requests: list[EchoRequest]) -> list[EchoRequest]:
        """Sort requests by priority.

        Args:
            requests: List of echo requests

        Returns:
            Sorted list with highest priority first
        """
        return sorted(
            requests,
            key=lambda r: r.priority.get_weight() if isinstance(r.priority, MessagePriority) else 0,
            reverse=True,
        )

    @staticmethod
    def get_processing_timeout(priority: MessagePriority) -> float:
        """Get processing timeout based on priority.

        Args:
            priority: Message priority

        Returns:
            Timeout in seconds
        """
        timeouts = {
            MessagePriority.LOW: 30.0,
            MessagePriority.NORMAL: 10.0,
            MessagePriority.HIGH: 5.0,
            MessagePriority.CRITICAL: 2.0,
        }
        return timeouts.get(priority, 10.0)

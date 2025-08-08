"""Domain services for Echo Service.

This module contains domain services that encapsulate business logic
not naturally belonging to any single entity or value object.
"""

from __future__ import annotations

import asyncio
import time

from .models import EchoMode, EchoRequest, EchoResponse


class EchoProcessor:
    """Domain service for processing echo requests."""

    def __init__(self, instance_id: str):
        """Initialize the echo processor.

        Args:
            instance_id: Unique instance identifier
        """
        self.instance_id = instance_id
        self.sequence_counter = 0

    async def process_echo(self, request: EchoRequest) -> EchoResponse:
        """Process an echo request based on the specified mode.

        Args:
            request: Echo request to process

        Returns:
            Processed echo response
        """
        start_time = time.time()
        self.sequence_counter += 1

        # Process based on mode
        if request.mode == EchoMode.SIMPLE:
            echoed_message = request.message
        elif request.mode == EchoMode.REVERSE:
            echoed_message = request.message[::-1]
        elif request.mode == EchoMode.UPPERCASE:
            echoed_message = request.message.upper()
        elif request.mode == EchoMode.DELAYED:
            # Apply delay if specified
            if request.delay > 0:
                await asyncio.sleep(request.delay)
            echoed_message = f"[Delayed {request.delay}s] {request.message}"
        elif request.mode == EchoMode.TRANSFORM:
            echoed_message = self._transform_message(request.message, request.transform_type)
        elif request.mode == EchoMode.BATCH:
            # For batch mode, repeat the message
            echoed_message = " | ".join([request.message] * 3)
        else:
            echoed_message = request.message

        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000

        # Build response
        response = EchoResponse(
            original=request.message,
            echoed=echoed_message,
            mode=request.mode,
            instance_id=self.instance_id,
            processing_time_ms=processing_time_ms,
            sequence_number=self.sequence_counter,
            metadata={
                "priority": request.priority.value,
                "request_metadata": request.metadata,
            },
        )

        return response

    def _transform_message(self, message: str, transform_type: str | None) -> str:
        """Apply transformation to the message.

        Args:
            message: Original message
            transform_type: Type of transformation to apply

        Returns:
            Transformed message
        """
        if not transform_type:
            return message.upper()

        transformations = {
            "uppercase": message.upper(),
            "lowercase": message.lower(),
            "reverse": message[::-1],
            "leetspeak": self._to_leetspeak(message),
            "emoji": self._add_emojis(message),
        }

        return transformations.get(transform_type, message.upper())

    def _to_leetspeak(self, text: str) -> str:
        """Convert text to leetspeak."""
        leet_map = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7"}
        result = text.lower()
        for char, leet in leet_map.items():
            result = result.replace(char, leet)
        return result

    def _add_emojis(self, text: str) -> str:
        """Add emojis to text."""
        emoji_map = {
            "happy": "😊",
            "sad": "😢",
            "love": "❤️",
            "hello": "👋",
            "goodbye": "👋",
            "thanks": "🙏",
        }
        result = text
        for word, emoji in emoji_map.items():
            if word in text.lower():
                result = f"{result} {emoji}"
        return result


class MetricsCollector:
    """Domain service for collecting and aggregating metrics."""

    def __init__(self):
        """Initialize the metrics collector."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.latencies: list[float] = []
        # Initialize mode counts properly
        self.mode_counts: dict[EchoMode, int] = {}
        for mode in EchoMode:
            self.mode_counts[mode] = 0
        self.start_time = time.time()

    def record_request(self, mode: EchoMode, latency_ms: float, success: bool = True) -> None:
        """Record a request for metrics.

        Args:
            mode: Echo mode used
            latency_ms: Request latency in milliseconds
            success: Whether the request was successful
        """
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        self.latencies.append(latency_ms)
        if len(self.latencies) > 1000:  # Keep only last 1000 for average
            self.latencies.pop(0)

        self.mode_counts[mode] += 1

    def get_average_latency(self) -> float:
        """Get average latency in milliseconds."""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    def get_uptime_seconds(self) -> float:
        """Get service uptime in seconds."""
        return time.time() - self.start_time

    def get_success_rate(self) -> float:
        """Get request success rate as percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100

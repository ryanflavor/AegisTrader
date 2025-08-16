"""
Circuit Breaker pattern implementation for connection resilience
Prevents cascading failures by stopping attempts when failure rate is high
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import TypeVar

from pydantic import BaseModel, Field


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Circuit is open, requests fail immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker"""

    failure_threshold: int = Field(
        default=5, description="Number of failures before opening circuit"
    )
    success_threshold: int = Field(
        default=2, description="Number of successes in half-open before closing"
    )
    timeout: float = Field(
        default=60.0, description="Seconds to wait before trying half-open state"
    )
    failure_rate_threshold: float = Field(
        default=0.5, description="Failure rate to open circuit (0.0-1.0)"
    )
    sample_size: int = Field(
        default=10, description="Number of requests to sample for failure rate"
    )


class CircuitBreakerStats(BaseModel):
    """Statistics for circuit breaker monitoring"""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    total_requests: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    last_state_change: datetime = Field(default_factory=datetime.now)
    consecutive_failures: int = 0
    consecutive_successes: int = 0


T = TypeVar("T")


class CircuitBreaker:
    """
    Circuit breaker implementation to prevent cascading failures

    The circuit breaker has three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: Testing if the service has recovered
    """

    def __init__(self, config: CircuitBreakerConfig | None = None):
        """
        Initialize circuit breaker

        Args:
            config: Circuit breaker configuration
        """
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        self._request_history: list[bool] = []  # True for success, False for failure

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        return self.stats.state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open"""
        return self.stats.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed"""
        return self.stats.state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open"""
        return self.stats.state == CircuitState.HALF_OPEN

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function through the circuit breaker

        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitOpenError: If circuit is open
            Exception: Any exception from func
        """
        async with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self.is_open:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    raise CircuitOpenError(
                        f"Circuit breaker is OPEN. Last failure: {self.stats.last_failure_time}"
                    )

        # Execute the function
        try:
            result = (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
            await self._on_success()
            return result
        except Exception:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Handle successful execution"""
        async with self._lock:
            self.stats.success_count += 1
            self.stats.total_requests += 1
            self.stats.last_success_time = datetime.now()
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0

            # Track in history
            self._request_history.append(True)
            if len(self._request_history) > self.config.sample_size:
                self._request_history.pop(0)

            # State transitions
            if self.is_half_open:
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to_closed()

    async def _on_failure(self) -> None:
        """Handle failed execution"""
        async with self._lock:
            self.stats.failure_count += 1
            self.stats.total_requests += 1
            self.stats.last_failure_time = datetime.now()
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0

            # Track in history
            self._request_history.append(False)
            if len(self._request_history) > self.config.sample_size:
                self._request_history.pop(0)

            # State transitions
            if self.is_half_open:
                # Any failure in half-open state opens the circuit
                self._transition_to_open()
            elif self.is_closed:
                # Check if we should open the circuit
                if self._should_open_circuit():
                    self._transition_to_open()

    def _should_open_circuit(self) -> bool:
        """Determine if circuit should be opened based on failure rate"""
        # Check consecutive failures threshold
        if self.stats.consecutive_failures >= self.config.failure_threshold:
            return True

        # Check failure rate if we have enough samples
        if len(self._request_history) >= self.config.sample_size:
            failure_rate = sum(1 for success in self._request_history if not success) / len(
                self._request_history
            )
            if failure_rate >= self.config.failure_rate_threshold:
                return True

        return False

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.stats.last_failure_time is None:
            return True

        time_since_failure = (datetime.now() - self.stats.last_failure_time).total_seconds()
        return time_since_failure >= self.config.timeout

    def _transition_to_open(self) -> None:
        """Transition to OPEN state"""
        self.stats.state = CircuitState.OPEN
        self.stats.last_state_change = datetime.now()
        self.stats.consecutive_successes = 0

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state"""
        self.stats.state = CircuitState.CLOSED
        self.stats.last_state_change = datetime.now()
        self.stats.consecutive_failures = 0
        self._request_history.clear()  # Reset history on close

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state"""
        self.stats.state = CircuitState.HALF_OPEN
        self.stats.last_state_change = datetime.now()
        self.stats.consecutive_successes = 0
        self.stats.consecutive_failures = 0

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state"""
        self.stats = CircuitBreakerStats()
        self._request_history.clear()

    def get_stats(self) -> dict:
        """
        Get circuit breaker statistics

        Returns:
            Dictionary containing circuit breaker stats
        """
        failure_rate = 0.0
        if self.stats.total_requests > 0:
            failure_rate = self.stats.failure_count / self.stats.total_requests

        return {
            "state": self.stats.state.value,
            "failure_count": self.stats.failure_count,
            "success_count": self.stats.success_count,
            "total_requests": self.stats.total_requests,
            "failure_rate": failure_rate,
            "consecutive_failures": self.stats.consecutive_failures,
            "consecutive_successes": self.stats.consecutive_successes,
            "last_failure_time": (
                self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None
            ),
            "last_success_time": (
                self.stats.last_success_time.isoformat() if self.stats.last_success_time else None
            ),
            "last_state_change": self.stats.last_state_change.isoformat(),
        }


class CircuitOpenError(Exception):
    """Exception raised when circuit breaker is open"""

    pass

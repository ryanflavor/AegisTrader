"""Configuration objects for infrastructure layer following DDD principles."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.value_objects import InstanceId, ServiceName


class NATSConnectionConfig(BaseModel):
    """Strongly-typed configuration for NATS connections.

    This configuration object encapsulates all connection-related settings,
    providing type safety and validation for NATS adapter initialization.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        strict=True,
        validate_assignment=True,
    )

    # Connection settings
    servers: list[str] = Field(
        default_factory=lambda: ["nats://localhost:4222"],
        min_length=1,
        description="List of NATS server URLs",
    )
    pool_size: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of connections in the pool",
    )
    max_reconnect_attempts: int = Field(
        default=10,
        ge=0,
        description="Maximum reconnection attempts",
    )
    reconnect_time_wait: float = Field(
        default=2.0,
        gt=0,
        description="Time to wait between reconnection attempts in seconds",
    )

    # JetStream settings
    js_domain: str | None = Field(
        default=None,
        description="JetStream domain for multi-tenancy",
    )
    enable_jetstream: bool = Field(
        default=True,
        description="Whether to initialize JetStream",
    )

    # Service identification
    service_name: ServiceName | None = Field(
        default=None,
        description="Service name for queue groups and identification",
    )
    instance_id: InstanceId | None = Field(
        default=None,
        description="Instance ID for unique identification",
    )

    # Serialization settings
    use_msgpack: bool = Field(
        default=True,
        description="Use MessagePack for serialization (faster than JSON)",
    )

    @field_validator("servers")
    @classmethod
    def validate_servers(cls, v: list[str]) -> list[str]:
        """Validate server URLs format."""
        for server in v:
            if not server.startswith(("nats://", "tls://", "ws://", "wss://")):
                raise ValueError(
                    f"Invalid server URL: {server}. "
                    "Must start with nats://, tls://, ws://, or wss://"
                )
        return v

    @field_validator("service_name", mode="before")
    @classmethod
    def parse_service_name(cls, v: Any) -> ServiceName | None:
        """Parse service name from string or ServiceName object."""
        if v is None:
            return None
        if isinstance(v, ServiceName):
            return v
        if isinstance(v, str):
            return ServiceName(value=v)
        raise ValueError(f"Invalid service name type: {type(v)}")

    @field_validator("instance_id", mode="before")
    @classmethod
    def parse_instance_id(cls, v: Any) -> InstanceId | None:
        """Parse instance ID from string or InstanceId object."""
        if v is None:
            return None
        if isinstance(v, InstanceId):
            return v
        if isinstance(v, str):
            return InstanceId(value=v)
        raise ValueError(f"Invalid instance ID type: {type(v)}")

    def to_connection_params(self) -> dict[str, Any]:
        """Convert to parameters for NATS connection."""
        return {
            "servers": self.servers,
            "max_reconnect_attempts": self.max_reconnect_attempts,
            "reconnect_time_wait": self.reconnect_time_wait,
        }


class KVStoreConfig(BaseModel):
    """Configuration for KV store operations.

    Encapsulates settings specific to key-value store behavior.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        strict=True,
        validate_assignment=True,
    )

    bucket: str = Field(
        ...,
        min_length=1,
        description="KV store bucket name",
    )
    enable_ttl: bool = Field(
        default=True,
        description="Enable per-message TTL support",
    )
    sanitize_keys: bool = Field(
        default=True,
        description="Sanitize keys for NATS compatibility",
    )
    max_value_size: int = Field(
        default=1024 * 1024,  # 1MB
        gt=0,
        description="Maximum value size in bytes",
    )
    history_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of historical revisions to keep",
    )

    @field_validator("bucket")
    @classmethod
    def validate_bucket_name(cls, v: str) -> str:
        """Validate bucket name format."""
        import re

        # NATS KV bucket names should be alphanumeric with underscores only
        # Hyphens, dots, and spaces are not allowed in NATS bucket names
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                f"Invalid bucket name: {v}. "
                "Must contain only alphanumeric characters and underscores"
            )
        return v


class LogContext(BaseModel):
    """Strongly-typed context for structured logging.

    Provides a consistent way to pass context information to loggers,
    ensuring all relevant metadata is captured for debugging and monitoring.
    """

    model_config = ConfigDict(
        extra="allow",  # Allow additional fields for flexibility
        str_strip_whitespace=True,
        strict=False,  # Allow coercion for convenience
        validate_assignment=True,
    )

    # Core context fields
    service_name: str | None = Field(
        default=None,
        description="Service name for log correlation",
    )
    instance_id: str | None = Field(
        default=None,
        description="Instance ID for log correlation",
    )
    trace_id: str | None = Field(
        default=None,
        description="Distributed trace ID",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for request tracking",
    )

    # Operation context
    operation: str | None = Field(
        default=None,
        description="Current operation being performed",
    )
    component: str | None = Field(
        default=None,
        description="Component or module generating the log",
    )

    # Error context
    error_code: str | None = Field(
        default=None,
        description="Structured error code",
    )
    error_type: str | None = Field(
        default=None,
        description="Type of error encountered",
    )

    # Performance context
    duration_ms: float | None = Field(
        default=None,
        ge=0,
        description="Operation duration in milliseconds",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging frameworks."""
        return {k: v for k, v in self.model_dump().items() if v is not None}

    def with_error(self, error: Exception) -> LogContext:
        """Create a new context with error information."""
        return LogContext(
            **{
                **self.model_dump(),
                "error_code": error.__class__.__name__,
                "error_type": type(error).__module__ + "." + type(error).__name__,
            }
        )

    def with_operation(self, operation: str, component: str | None = None) -> LogContext:
        """Create a new context with operation information."""
        return LogContext(
            **{
                **self.model_dump(),
                "operation": operation,
                "component": component or self.component,
            }
        )


class StickyActiveConfig(BaseModel):
    """Client-side configuration for sticky behavior with SingleActiveService.

    This configuration enables clients to automatically retry when receiving
    NOT_ACTIVE errors, achieving sticky session behavior without requiring
    a separate StickyActiveService class. The stickiness comes from the
    client persistently retrying until finding the active leader.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        strict=True,
        validate_assignment=True,
    )

    # Retry configuration
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts for NOT_ACTIVE errors",
    )
    initial_retry_delay_ms: int = Field(
        default=100,
        ge=10,
        le=10000,
        description="Initial retry delay in milliseconds",
    )
    backoff_multiplier: float = Field(
        default=2.0,
        gt=1.0,
        le=10.0,
        description="Exponential backoff multiplier for retries",
    )
    max_retry_delay_ms: int = Field(
        default=5000,
        ge=100,
        le=30000,
        description="Maximum retry delay in milliseconds",
    )
    jitter_factor: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Random jitter factor (0.0 to 1.0) to prevent thundering herd",
    )

    # Performance settings
    enable_metrics: bool = Field(
        default=True,
        description="Enable detailed metrics for sticky active calls",
    )
    enable_debug_logging: bool = Field(
        default=False,
        description="Enable debug logging for retry attempts",
    )

    # Failover detection
    failover_timeout_ms: int = Field(
        default=10000,
        ge=1000,
        le=60000,
        description="Maximum time to wait for failover completion in milliseconds",
    )

    @field_validator("max_retry_delay_ms")
    @classmethod
    def validate_max_delay(cls, v: int, info) -> int:
        """Ensure max delay is greater than initial delay."""
        if "initial_retry_delay_ms" in info.data:
            initial_delay = info.data["initial_retry_delay_ms"]
            if v <= initial_delay:
                raise ValueError("Max retry delay must be greater than initial retry delay")
        return v

    def to_retry_policy(self) -> Any:
        """Convert configuration to RetryPolicy value object.

        Returns:
            RetryPolicy configured according to this configuration
        """
        # Import here to avoid circular imports
        from ..domain.value_objects import Duration, RetryPolicy

        return RetryPolicy(
            max_retries=self.max_retries,
            initial_delay=Duration.from_milliseconds(self.initial_retry_delay_ms),
            backoff_multiplier=self.backoff_multiplier,
            max_delay=Duration.from_milliseconds(self.max_retry_delay_ms),
            jitter_factor=self.jitter_factor,
            retryable_errors=["NOT_ACTIVE"],  # Specific to sticky active pattern
        )

    def should_log_debug(self) -> bool:
        """Check if debug logging is enabled."""
        return self.enable_debug_logging

    def should_track_metrics(self) -> bool:
        """Check if metrics tracking is enabled."""
        return self.enable_metrics

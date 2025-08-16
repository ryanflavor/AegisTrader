"""
Base configuration classes for infrastructure components.

Provides common configuration patterns and validation following DDD principles.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BaseInfraConfig(BaseModel):
    """Base configuration for all infrastructure components."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    @classmethod
    def from_env(cls, prefix: str = "") -> BaseInfraConfig:
        """Create configuration from environment variables.

        Args:
            prefix: Environment variable prefix (e.g., "CTP_", "NATS_")

        Returns:
            Configuration instance populated from environment
        """
        env_data = {}
        for field_name, field_info in cls.model_fields.items():
            env_key = f"{prefix}{field_name.upper()}"
            env_value = os.getenv(env_key)

            if env_value is not None:
                # Convert string to appropriate type
                field_type = field_info.annotation
                if field_type == bool:
                    env_data[field_name] = env_value.lower() in ("true", "1", "yes")
                elif field_type == int:
                    env_data[field_name] = int(env_value)
                elif field_type == float:
                    env_data[field_name] = float(env_value)
                else:
                    env_data[field_name] = env_value

        return cls(**env_data)


class ConnectionConfig(BaseInfraConfig):
    """Base configuration for connection-based components."""

    host: str = Field(description="Host address")
    port: int = Field(description="Port number", gt=0, le=65535)
    timeout: int = Field(default=30, description="Connection timeout in seconds", gt=0)
    retry_attempts: int = Field(default=3, description="Number of retry attempts", ge=0)
    retry_delay: int = Field(default=5, description="Delay between retries in seconds", gt=0)

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host is not empty."""
        if not v or not v.strip():
            raise ValueError("Host cannot be empty")
        return v.strip()


class GatewayConnectionConfig(BaseInfraConfig):
    """Base configuration for gateway connections."""

    # Authentication
    user_id: str = Field(description="User identifier")
    password: str = Field(description="User password")

    # Connection settings
    heartbeat_interval: int = Field(default=30, description="Heartbeat interval in seconds", gt=0)
    reconnect_interval: int = Field(default=5, description="Reconnect interval in seconds", gt=0)
    max_reconnect_attempts: int = Field(
        default=3, description="Maximum reconnection attempts", ge=0
    )

    # Flow control
    enable_flow_control: bool = Field(default=True, description="Enable flow control")
    max_requests_per_second: int = Field(default=10, description="Max requests per second", gt=0)

    @field_validator("user_id", "password")
    @classmethod
    def validate_credentials(cls, v: str, info) -> str:
        """Validate credentials are not empty."""
        if not v:
            raise ValueError(f"{info.field_name} cannot be empty")
        return v


class ServiceConfig(BaseInfraConfig):
    """Base configuration for services."""

    service_name: str = Field(description="Service name")
    instance_id: str | None = Field(default=None, description="Instance identifier")
    version: str = Field(default="1.0.0", description="Service version")

    # Health check settings
    health_check_interval: int = Field(default=30, description="Health check interval", gt=0)
    health_check_timeout: int = Field(default=5, description="Health check timeout", gt=0)

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        """Validate service name format."""
        if not v or not v.strip():
            raise ValueError("Service name cannot be empty")
        # Ensure valid DNS-like name
        import re

        if not re.match(r"^[a-z0-9-]+$", v.lower()):
            raise ValueError(
                "Service name must contain only lowercase letters, numbers, and hyphens"
            )
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v_upper


class RepositoryConnectionConfig(ConnectionConfig):
    """Configuration for database repository connections."""

    database: str = Field(description="Database name")
    user: str = Field(default="default", description="Database user")
    password: str = Field(default="", description="Database password")

    # Connection pool settings
    pool_size: int = Field(default=10, description="Connection pool size", gt=0)
    max_overflow: int = Field(default=20, description="Max overflow connections", ge=0)

    # Query settings
    query_timeout: int = Field(default=30, description="Query timeout in seconds", gt=0)

    def get_connection_string(self) -> str:
        """Build database connection string.

        Returns:
            Connection string for the database
        """
        if self.password:
            return f"{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        return f"{self.user}@{self.host}:{self.port}/{self.database}"
